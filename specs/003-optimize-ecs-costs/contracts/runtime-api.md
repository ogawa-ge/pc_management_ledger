# Runtime API Contract - ECS自動起動・再送・停止

## 1. 適用範囲

既存のPC管理APIの業務リクエスト/成功レスポンスは [../../001-pc-management/contracts/api.md](../../001-pc-management/contracts/api.md) および後続機能契約を維持する。本契約は、それらのAPIが ECS 停止中・起動中の場合の共通応答、再送、冪等性、内部プロキシ境界を追加定義する。

対象操作:

- 参照系: `GET /api/pcs`
- 状態変更: `POST /api/pcs`
- 状態変更: `POST /api/pcs/{pcId}/return`
- 同じLambda→ECSプロキシを通る他のPC管理APIにも起動状態契約を適用する

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

### 同じキーで成功済み

- 初回成功と同じHTTPステータスおよび業務結果を返す。
- レスポンスヘッダー `Idempotency-Replayed: true` を付与する。
- PC登録、返却記録、ステータス遷移を再実行しない。
- 状態変更の業務書込みと成功記録は DynamoDB トランザクションで同時に確定し、一方だけを成功させない。

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
| `X-Internal-Signature` | 下記canonical requestのHMAC-SHA256 hex |

Canonical request:

```text
{METHOD}\n{NORMALIZED_PATH_WITH_QUERY}\n{BODY_SHA256}\n{IDEMPOTENCY_KEY}\n{INTERNAL_REQUEST_ID}\n{TIMESTAMP}
```

### Verification

- 共有秘密は Secrets Manager から取得し、コード、ログ、レスポンスへ出力しない。
- ECSは時刻窓（実装定数、推奨±60秒）、本文ハッシュ、定数時間比較による署名一致を検証する。
- 欠落、不正、期限切れは `403 Forbidden`。
- 内部署名成功後も既存の利用者認証・認可を実行する。
- `X-Internal-Request-Id`、操作名、結果は監査ログへ出せるが、Authorization、署名、秘密、PCスペック本文は記録しない。

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