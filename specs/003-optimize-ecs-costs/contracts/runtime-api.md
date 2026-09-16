# Runtime API Contract - ECS自動起動・再送・停止

## 1. 適用範囲

既存のPC管理APIの業務リクエスト/成功レスポンスは [../../001-pc-management/contracts/api.md](../../001-pc-management/contracts/api.md) および後続機能契約を維持する。本契約は、それらのAPIが ECS 停止中・起動中の場合の共通応答、再送、冪等性、内部プロキシ境界を追加定義する。

対象操作:

- 参照系: `GET /api/pcs`
- 状態変更（冪等ガード必須）: `POST /api/pcs`
- 状態変更（冪等ガード必須）: `POST /api/pcs/{pcId}/return`
- 状態変更（冪等ガード必須）: `PATCH /api/pcs/{pcId}/status`
- 非永続処理: `POST /api/pcs/parse-specs`（内部署名と既存認証は必須だが、冪等成功結果保存は対象外）
- 同じLambda→ECSプロキシを通る他のPC管理APIにも起動状態契約を適用する

現行コードの`POST`、`PUT`、`PATCH`、`DELETE`ルートを実装時に機械的に棚卸しし、上記以外の永続状態変更ルートが見つかった場合は、実装前に本一覧へ追加して冪等ガード対象または対象外理由を確定する。分類されていない状態変更ルートをリリースしない。

## 2. 共通リクエストヘッダー

### `Idempotency-Key`

- 形式: UUID文字列
- フロントエンドは1つの利用者操作につき1回生成する。
- 起動待ち・通信再試行では同じ値を維持する。
- 新しい手動操作では新しい値を生成する。
- `POST`, `PUT`, `PATCH`, `DELETE` は必須。欠落時は `400`。
- `GET`, `HEAD` は任意だが、共通クライアントは付与してよい。

### `Authorization`

既存APIの認証・認可要件を維持する。`Idempotency-Key` や内部署名は利用者認証の代替ではない。

## 3. 起動中レスポンス

ECSタスクが利用可能でない場合、Lambdaは起動を集約し、次を返す。

```http
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
Retry-After: 15
Cache-Control: no-store
```

```json
{
  "status": "starting",
  "message": "バックエンドを起動しています。操作は自動的に再試行されます。",
  "requestId": "opaque-request-id",
  "retryAfterSeconds": 15,
  "waitedSeconds": 0,
  "maxWaitSeconds": 180
}
```

### Rules

- `Retry-After` は秒数形式で1〜30秒。
- 10件同時要求でも `UpdateService(desiredCount=1)` の実行所有者は1件だけ。他は同じ `starting` または利用可能応答を受ける。
- レスポンスは元操作が完了したことを意味しない。
- フロントエンドは起動中表示を開始し、同じ操作を自動再送する。
- 通常のECS業務エラー `503` と区別するため、JSON `status=starting` と `Retry-After` の両方を満たす場合だけ起動待ちとして扱う。

## 4. 最大待機時間超過

フロントエンドで初回要求から180秒を超えた場合、自動再送を終了する。追加のAPI呼び出しでタイムアウト応答を生成する必要はないが、UIは次を示す。

```json
{
  "status": "start_timeout",
  "message": "バックエンドの起動が3分以内に完了しませんでした。操作は完了していません。",
  "canRetry": true
}
```

- 利用者が「再試行」を選んだ場合、未完了が確認できた同じ操作には同じ `Idempotency-Key` を再利用してよい。
- 入力内容を変更して新規操作として送る場合は新しいキーを生成する。
- タイムアウトを通常の業務失敗や認証失敗として表示しない。

## 5. 冪等性レスポンス

### 同じキーで処理中

```http
HTTP/1.1 409 Conflict
Retry-After: 3
```

```json
{
  "status": "processing",
  "message": "同じ操作を処理中です。",
  "retryAfterSeconds": 3
}
```

フロントエンドは最大待機時間内で同じキーを再送する。

- `PROCESSING`取得から5分未満は、同じfingerprintでも後続要求へ処理権を渡さない。
- 5分以上更新がなく成功未確定の場合だけ、後続要求は旧`ownerRequestId`、旧`startedAt`、`status=PROCESSING`を条件に処理権を回収できる。
- 同時回収では条件付き更新に成功した1要求だけが新所有者となる。
- 回収後の旧所有者は、業務書込みと成功記録を確定するトランザクションの所有者条件に失敗し、業務変更を残さない。

### 同じキーで成功済み

- 初回成功と同じHTTPステータスおよび業務結果を返す。
- レスポンスヘッダー `Idempotency-Replayed: true` を付与する。
- PC登録、返却記録、ステータス遷移を再実行しない。
- 状態変更の業務書込みと成功記録は DynamoDB トランザクションで同時に確定し、一方だけを成功させない。
- トランザクション内の冪等成功更新は`status=PROCESSING`、現`ownerRequestId`、現`startedAt`を条件とし、処理権回収後の旧所有者による遅延確定を拒否する。
- 成功結果は成功完了から7日間再利用する。7日経過後はDynamoDB TTLによる物理削除を待たず、期限条件付きで新しい`PROCESSING`へ置換して新規要求として扱う。

### 同じキーで異なる要求

```http
HTTP/1.1 409 Conflict
```

```json
{
  "status": "idempotency_conflict",
  "message": "同じIdempotency-Keyを異なる要求には使用できません。"
}
```

自動再試行は禁止し、新しい操作としてやり直す案内を表示する。

## 6. フロントエンド再試行契約

共通APIクライアントは以下を満たす。

1. 初回送信前に、メソッド、URL、ヘッダー、直列化済み本文、`Idempotency-Key` を固定する。
2. `503 + status=starting` または `409 + status=processing` のみ自動再送対象とする。
3. `Retry-After` を優先し、不正・欠落時は契約既定値15秒（processingは3秒）を使う。
4. 180秒経過、利用者キャンセル、画面アンマウント時に停止する。
5. 同一操作に複数のタイマーを作らない。
6. 2xx受信後は再送を停止し、起動中表示を閉じて元の成功処理を続行する。
7. 4xx認証・認可・入力エラー、通常の5xx、ネットワーク断は既存エラーとして扱い、無制限再送しない。

## 7. LambdaからECSへの内部転送ヘッダー

利用者/ブラウザは以下のヘッダーを生成してはならない。Lambdaは外部入力の同名ヘッダーを削除して再生成する。

| Header | Description |
|---|---|
| `X-Internal-Request-Id` | Lambdaが生成した一意要求ID |
| `X-Internal-Timestamp` | Unix epoch seconds |
| `X-Internal-Body-SHA256` | 生リクエスト本文のSHA-256 hex |
| `X-Internal-Key-Id` | 署名に使った現行秘密世代の非機密識別子 |
| `X-Internal-Signature` | 下記canonical requestのHMAC-SHA256 hex |

Canonical request:

```text
{METHOD}\n{NORMALIZED_PATH_WITH_QUERY}\n{BODY_SHA256}\n{IDEMPOTENCY_KEY}\n{INTERNAL_REQUEST_ID}\n{TIMESTAMP}\n{KEY_ID}
```

### Verification

- 共有秘密は Secrets Manager から取得し、コード、ログ、レスポンスへ出力しない。
- ECSは受信時刻との差が±60秒以内であること、本文ハッシュ、定数時間比較による署名一致を検証する。60秒を超える差は署名が一致しても拒否する。
- 欠落、不正、期限切れは `403 Forbidden`。
- 内部署名成功後も既存の利用者認証・認可を実行する。
- `X-Internal-Request-Id`、操作名、結果は監査ログへ出せるが、Authorization、署名、秘密、PCスペック本文は記録しない。

### Secret rotation

1. 通常時、Lambdaは`current`として指定された1世代だけで署名し、ECSは同じ世代を検証する。
2. 移行開始時、次期秘密と一意な`keyId`をSecrets Managerへ追加し、ECSだけを先に更新して現行・次期の2世代を検証可能にする。3世代以上を同時に有効化しない。
3. Lambdaを次期`keyId`へ切り替え、正常な内部転送が成功することを確認する。Lambdaは1要求を複数秘密で署名しない。
4. 切替確認後、ECSの検証対象から旧`keyId`を削除し、Secrets Manager上の旧秘密を失効させる。
5. 未登録または失効済み`keyId`、`keyId`と秘密が一致しない署名は業務処理前に`403`とする。エラー応答から有効な世代一覧を公開しない。
6. 各段階で既存利用者認証・認可を省略せず、正当な要求の中断0件と旧秘密失効後の拒否を検証記録へ残す。

Secrets Managerの秘密は、非機密の`keyId`と秘密値を対応付けた現行・次期の最大2世代、およびLambdaが署名に使う現行`keyId`を表現する。秘密値をCloudFormation出力、通常の環境変数、ログ、レスポンスへ含めない。LambdaとECSの実行ロールには対象秘密の読取だけを許可する。

## 8. アクティビティ更新契約

1. Lambda受付時: `lastAcceptedAt=now`。停止競合中なら世代を進めて起動へ遷移。
2. ECS転送直前: `inFlightCount += 1`。
3. 2xx成功応答: `lastActivityAt=completion time`, `inFlightCount -= 1`。
4. 非2xxまたは転送失敗: `inFlightCount -= 1`、`lastActivityAt` は変更しない。
5. すべての終了経路で減算を試みる。負数になる更新は条件式で拒否し、異常ログを残す。
6. 停止判定は処理中件数が0でなければ停止しない。

## 9. 稼働状態の外部表現

利用者向けには以下だけを公開する。

| Internal State | Public status | User experience |
|---|---|---|
| `STOPPED` | `starting` | 自動起動開始・待機表示 |
| `STARTING` | `starting` | 待機継続 |
| `RUNNING` | 通常業務応答 | 元操作完了 |
| `STOPPING` + 新規操作 | `starting` | 停止中止または再起動 |
| `START_FAILED` | `starting`（180秒内の再起動中）または `start_timeout` | 安全な再試行案内 |

内部のAWS ARN、IP、例外文字列、シークレット名は公開レスポンスに含めない。