# Phase 1: Data Model - ECSコスト最適化

## 1. スコープと保存方針

PC、User、Return Record、PC Usage History の業務スキーマは [../001-pc-management/data-model.md](../001-pc-management/data-model.md) を一次ソースとし、本機能では変更しない。

新規のランタイム制御項目は、既存 DynamoDB テーブル `SystemActivity` のパーティションキー `entityId` を用いて保存する。専用テーブルを増やさず、以下のキー空間で項目種別を分離する。

| キー形式 | 項目種別 | 多重度 |
|---|---|---|
| `global` | Backend Runtime Control | 1件 |
| `request#{idempotencyKey}` | Idempotent Request | 要求ごとに1件 |

Cost Evaluation、Adoption Decision、Validation Record は運用ドキュメントとして `specs/003-optimize-ecs-costs/` 配下へ記録し、アプリケーションDBには保存しない。

## 2. Backend Runtime Control（バックエンド稼働制御）

**保存先**: `SystemActivity` / `entityId = "global"`

| Field | Type | Required | Description |
|---|---|---:|---|
| `entityId` | String (PK) | Yes | 固定値 `global` |
| `runtimeState` | String | Yes | `STOPPED`, `STARTING`, `RUNNING`, `STOPPING`, `START_FAILED` |
| `generation` | Number (integer >= 0) | Yes | 起動・停止競合を検出する単調増加世代 |
| `lastAcceptedAt` | String (ISO 8601 UTC) | No | 対象操作を最後に受け付けた時刻 |
| `lastActivityAt` | String (ISO 8601 UTC) | No | 対象操作が最後に成功完了した時刻。アイドル判定の基準 |
| `inFlightCount` | Number (integer >= 0) | Yes | ECSへ転送済みで応答未完了の操作数 |
| `startRequestedAt` | String (ISO 8601 UTC) | No | 現世代の起動要求時刻 |
| `stopRequestedAt` | String (ISO 8601 UTC) | No | 現世代の停止要求時刻 |
| `lastStateChangedAt` | String (ISO 8601 UTC) | Yes | 最後の状態遷移時刻 |
| `lastErrorCode` | String | No | 起動・停止・判定異常の機械可読コード |
| `lastErrorAt` | String (ISO 8601 UTC) | No | 最後に異常を記録した時刻 |

### Validation rules

- `generation` と `inFlightCount` は負数不可。
- 時刻はタイムゾーン付き ISO 8601 UTC とする。
- `lastActivityAt` が欠落、不正、未来時刻の場合は即時停止せず、`lastErrorCode` とCloudWatch Logsへ記録する。
- `inFlightCount` が欠落、不正、負数の場合も停止しない。
- `STARTING` が3分を超えた場合、利用者への自動再試行は終了する。ただし実際のECS状態を照合するまで制御項目だけで `STOPPED` と決めない。

### State transitions

```text
STOPPED ------ valid operation ------> STARTING
START_FAILED -- valid operation ------> STARTING
RUNNING ------ desired/running=0 -----> STARTING
STARTING ----- task ready ------------> RUNNING
STARTING ----- terminal failure ------> START_FAILED
RUNNING ------ idle gate acquired ----> STOPPING
STOPPING ----- no newer generation ---> STOPPED
STOPPING ----- valid operation -------> STARTING
STOPPED <----- deploy / idle stop ----- STOPPING
```

### Transition guards

1. **Start ownership**: 状態と世代への条件付き更新に成功した1呼び出しだけが `UpdateService(desiredCount=1)` を実行する。
2. **Ready**: ECSタスクが `RUNNING` で、公開IP取得後のヘルス確認が成功した場合のみ `RUNNING` とする。
3. **Stop ownership**: `runtimeState=RUNNING`、`inFlightCount=0`、読み取った `generation` が不変、`lastActivityAt <= now - 2 hours` を満たす場合のみ `STOPPING` へ遷移する。
4. **Stop cancellation/restart**: `STOPPING` 中の新規操作は `generation` を増やして `STARTING` とし、停止API実行後の世代再確認でも新世代を検出した場合は `desiredCount=1` を再適用する。
5. **Completion**: 2xx応答の成功完了時だけ `lastActivityAt` を更新する。4xx/5xx/通信失敗は更新しないが `inFlightCount` は必ず減らす。

## 3. Idempotent Request（冪等要求）

**保存先**: `SystemActivity` / `entityId = "request#{idempotencyKey}"`

| Field | Type | Required | Description |
|---|---|---:|---|
| `entityId` | String (PK) | Yes | `request#` + UUID形式の `Idempotency-Key` |
| `requestFingerprint` | String | Yes | HTTPメソッド、正規化パス、本文ハッシュのSHA-256 |
| `operation` | String | Yes | `PC_LIST`, `PC_REGISTER`, `PC_RETURN` 等の契約済み操作名 |
| `status` | String | Yes | `PROCESSING`, `SUCCEEDED`, `FAILED_RETRYABLE` |
| `ownerRequestId` | String | Yes | 処理所有権を取得した内部要求ID |
| `startedAt` | String (ISO 8601 UTC) | Yes | 初回処理開始時刻 |
| `completedAt` | String (ISO 8601 UTC) | No | 成功完了時刻 |
| `responseStatus` | Number | No | 再利用する成功HTTPステータス |
| `responseBody` | String | No | 小容量の成功JSON応答。機密情報を保存しない |
| `resultReference` | String | No | `pcId` または返却記録ID等の結果参照。定義済み業務IDのみ |
| `expiresAt` | Number (epoch seconds) | Yes | DynamoDB TTL。成功結果保持期限 |

### Validation rules

- 状態変更操作は `Idempotency-Key` 必須。参照系操作では任意だが、再試行クライアントは常に付与する。
- 同じキーで `requestFingerprint` が異なる場合は `409 Conflict`。キーの使い回しを許可しない。
- 新規キーは条件式 `attribute_not_exists(entityId)` で `PROCESSING` を作成し、成功した要求だけが業務処理を開始する。
- `SUCCEEDED` の同一キー・同一fingerprintは保存済みレスポンスを返し、業務処理を再実行しない。
- `PROCESSING` の同一要求は `409` と `Retry-After` を返し、別所有者へ処理権を渡さない。
- `responseBody` はDynamoDB項目上限を考慮し、PC一覧等の大きなGET応答は保存しない。状態変更の小さな成功応答だけを対象とする。
- TTL削除は即時ではないため、`expiresAt <= now` の項目はアプリケーション側でも期限切れとして扱う。

### State transitions

```text
(absent) -------- claim --------> PROCESSING
PROCESSING ------ success ------> SUCCEEDED
PROCESSING ------ retryable ----> FAILED_RETRYABLE
FAILED_RETRYABLE - reclaim -----> PROCESSING
SUCCEEDED -------- TTL ---------> (expired/deleted)
```

PC登録・PC返却では、業務項目の条件付き作成/更新、履歴または返却記録の作成、Idempotent Request の `PROCESSING -> SUCCEEDED` 更新を1回の DynamoDB `TransactWriteItems` で原子的に確定する。トランザクション失敗時は成功応答を返さず、同じキーの安全な再試行を可能にする。既存業務項目へ `Idempotency-Key` 等の属性追加が必要になった場合は、実装前に本モデルと `001` のモデル契約を更新し、推測でカラムを追加しない。

## 4. Configuration Candidate（構成候補）

**保存先**: [contracts/cost-evaluation.md](./contracts/cost-evaluation.md) に従う運用記録

| Field | Type | Required | Description |
|---|---|---:|---|
| `candidateId` | String | Yes | 候補の一意名 |
| `networkPattern` | String | Yes | NAT、public subnet、VPC endpoint等の構成 |
| `runtimePolicy` | String | Yes | 初期数、起動条件、停止条件 |
| `connectivity` | Map | Yes | Gemini/DynamoDB/ECR/Logsそれぞれの可否と根拠 |
| `fixedCostItems` | List | Yes | 時間固定費項目 |
| `usageCostItems` | List | Yes | 稼働・通信量連動費項目 |
| `advantages` | List | Yes | 利点 |
| `constraints` | List | Yes | 運用制約 |
| `risks` | List | Yes | 既知のリスク |
| `decision` | String | Yes | `ADOPTED` または `REJECTED` |

## 5. Cost Estimate（コスト見積り）

| Field | Type | Required | Description |
|---|---|---:|---|
| `pricingDate` | Date | Yes | 価格基準日 |
| `region` | String | Yes | `ap-northeast-1` |
| `sourceUrl` | String | Yes | AWS公式価格根拠 |
| `currency` | String | Yes | 元単価通貨（通常USD） |
| `exchangeRate` | Number | Conditional | 円換算時のレート |
| `exchangeRateSource` | String | Conditional | 為替根拠 |
| `monthlyHours` | Number | Yes | 通常730時間 |
| `taskRuntimeHours` | Number | Yes | シナリオ別ECS稼働時間 |
| `dataVolumeGb` | Map | Yes | 通信先別月間GB |
| `lineItems` | List | Yes | 単価、数量、式、月額 |
| `totalUsd` | Number | Yes | USD合計 |
| `totalJpy` | Number | Yes | 円合計 |
| `includedItems` | List | Yes | 含めた費用 |
| `excludedItems` | List | Yes | 除外費用と理由 |

## 6. Adoption Decision（採用判断）

| Field | Type | Required | Description |
|---|---|---:|---|
| `adoptedCandidateId` | String | Yes | 採用候補 |
| `rationale` | List | Yes | 採用理由 |
| `rejectedCandidates` | List | Yes | 候補別の却下理由 |
| `knownRisks` | List | Yes | リスクと緩和策 |
| `reviewTriggers` | List | Yes | 月額3,000円超、見積差20%超、通信失敗等 |
| `approvedAt` | DateTime | Yes | 判断日時 |
| `approver` | String | Yes | 運用責任者。個人情報ではなく組織上の識別子を使用 |

## 7. Validation Record（検証記録）

| Field | Type | Required | Description |
|---|---|---:|---|
| `validationId` | String | Yes | 検証の一意ID |
| `scenario` | String | Yes | 通信、起動、操作、停止、コスト等 |
| `executedAt` | DateTime | Yes | 実施日時 |
| `environment` | String | Yes | AWSアカウント実値を含めず環境名を記録 |
| `preconditions` | List | Yes | desired/running count等 |
| `requestId` | String | No | 追跡用ID。トークンや本文は記録しない |
| `idempotencyKey` | String | No | 状態変更の重複確認用 |
| `expected` | String | Yes | 期待結果 |
| `actual` | String | Yes | 実結果 |
| `durationSeconds` | Number | No | 起動から操作完了まで |
| `result` | String | Yes | `PASS` / `FAIL` |
| `failureReason` | String | No | 失敗理由 |
| `evidenceReference` | String | Yes | CloudWatch、CLI出力、請求レポート等。秘密情報は除外 |

## 8. Relationships

- 1つの Configuration Candidate は1つ以上の Cost Estimate を持つ（利用シナリオ別）。
- 1つの Adoption Decision は1つの採用候補と1つ以上の却下候補を参照する。
- Backend Runtime Control は複数の Idempotent Request を制御するが、DynamoDB上の直接参照制約は持たない。
- 1つの利用操作は1つの Idempotent Request と、受付・処理中・成功完了による Backend Runtime Control 更新を持つ。
- Validation Record は候補、操作、稼働世代、コスト期間のいずれかを証跡参照で関連付ける。