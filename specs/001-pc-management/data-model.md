# Phase 1: Data Model

## Entities

### User (DynamoDB Table: `Users`)

| Field | Type | Description |
|---|---|---|
| `userId` | String (PK) | Microsoftアカウントのメールアドレスまたは一意のID |
| `name` | String | ユーザー名 |
| `role` | String | `Admin` または `User` |
| `createdAt` | String | 登録日時 (ISO 8601) |
| `updatedAt` | String | 更新日時 (ISO 8601) |

### PC (DynamoDB Table: `PCs`)

| Field | Type | Description |
|---|---|---|
| `pcId` | String (PK) | 管理番号 (N-XXX または D-XXX) |
| `ownerId` | String | 所有者の `userId` (未割り当ての場合は空または特定の値) |
| `type` | String | `Notebook` または `Desktop` |
| `status` | String | `InUse` (利用中), `Unused` (未使用), `PendingDisposal` (廃棄待ち), `Disposed` (廃棄済み) |
| `cpu` | String | CPU情報 |
| `memory` | String | メモリ容量 |
| `storage` | String | ストレージ容量 |
| `os` | String | OSバージョン |
| `manufacturer` | String | メーカー名 |
| `model` | String | モデル名 |
| `createdAt` | String | 登録日時 (ISO 8601) |
| `updatedAt` | String | 更新日時 (ISO 8601) |

### Return Record (DynamoDB Table: `ReturnRecords`)

| Field | Type | Description |
|---|---|---|
| `recordId` | String (PK) | 返却記録の一意のID (UUID等) |
| `pcId` | String | 返却対象のPC管理番号 |
| `userId` | String | 返却申請者の `userId` |
| `returnDate` | String | 返却日 (YYYY-MM-DD) |
| `reason` | String | 返却理由 |
| `condition` | String | PCの状態 (例: `Initialized`, `Broken`, etc.) |
| `createdAt` | String | 申請日時 (ISO 8601) |

### PC Usage History (DynamoDB Table: `PCUsageHistories`)

| Field | Type | Description |
|---|---|---|
| `historyId` | String (PK) | 履歴の一意のID (UUID等) |
| `pcId` | String (GSI PK) | 対象のPC管理番号 |
| `userId` | String | 利用者の `userId` |
| `status` | String | 履歴記録時のステータス (`InUse`, `Unused`, `PendingDisposal`, `Disposed`) |
| `reason` | String | 返却理由（返却時など） |
| `date` | String | 履歴の日付 (ISO 8601) |

## State Transitions (PC Status)

1. **新規登録時**:
   - ユーザー登録: `InUse`
   - 管理者登録: `InUse` または `Unused`
2. **返却時**:
   - `InUse` -> `Unused` (通常返却) または `PendingDisposal` (故障等の場合)
3. **管理者操作**:
   - `PendingDisposal` -> `Disposed` (廃棄完了時)
   - `Unused` -> `InUse` (新規ユーザーへの割り当て時)
