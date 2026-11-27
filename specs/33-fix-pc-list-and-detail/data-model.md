# Data Model: PC一覧の表示不整合修正およびPC詳細画面の実装

**Feature**: Issue #33 (`specs/33-fix-pc-list-and-detail`)  
**Reference**: `specs/001-pc-management/data-model.md`, `backend/ecs/src/models/pc.py`, `backend/ecs/src/models/user.py`

> [!NOTE]
> DynamoDB テーブル（`PCs`, `Users`, `PCUsageHistories`）のスキーマ変更は行いません。本ドキュメントでは API レスポンスモデルおよびフロントエンド型定義における拡張・バリデーションルールを定義します。

---

## 1. Entities

### 1.1 PC（レスポンス / 画面表示モデル）

DynamoDB `PCs` テーブルのレコードに、`Users` テーブルから解決した `ownerName` を結合して表現する。

| Field (JSON / camelCase) | Python Field (`Pc`) | Type | Required | Description / Display Rule |
| :--- | :--- | :--- | :--- | :--- |
| `pcId` | `pc_id` | `string` | Yes | 管理番号（例: `N-001`, `D-001`）。主キー |
| `ownerId` | `owner_id` | `string \| null` | No | オーナーのユーザーID（`Users.userId`）。未使用時は空/null の場合あり |
| `ownerName` | `owner_name` | `string \| null` | No | **追加フィールド**。`Users` テーブルから解決したオーナー氏名（`name` 優先、未設定時は `email`）。`ownerId` 未設定時および `status !== "InUse"`（`Unused` / `PendingDisposal` / `Disposed`）時は `null`（UIで「未割り当て」表示）。`status === "InUse"` かつ `ownerId` が `Users` に存在しない場合は `"不明なユーザー"` |
| `type` | `type` | `string` | Yes | PC種別（`Notebook` / `Desktop`）。UI では「ノートパソコン」「デスクトップパソコン」と表示 |
| `status` | `status` | `'InUse' \| 'Unused' \| 'PendingDisposal' \| 'Disposed'` | Yes | 現在のステータス（UI で日本語バッジ表示） |
| `pcName` | `pc_name` | `string \| null` | No | PC名（ホスト名等）。未設定/`Unknown` は `-` |
| `manufacturer` | `manufacturer` | `string \| null` | No | メーカー名。未設定/`Unknown` は `-` |
| `model` | `model` | `string \| null` | Yes (新規登録時) | モデル名。一覧・詳細で表示。既存データの未設定/`Unknown` は `-` |
| `cpu` | `cpu` | `string \| null` | No | CPU。未設定/`Unknown` は `-` |
| `memory` | `memory` | `string \| null` | No | メモリ容量。未設定/`Unknown` は `-` |
| `storage` | `storage` | `string \| null` | No | ストレージ容量。未設定/`Unknown` は `-` |
| `os` | `os` | `string \| null` | No | OS。未設定/`Unknown` は `-` |
| `gpu` | `gpu` | `string \| null` | No | GPU。未設定/`Unknown` は `-` |
| `serialNumber` | `serial_number` | `string \| null` | No | シリアル番号。未設定/`Unknown` は `-` |
| `createdAt` | `created_at` | `string` (ISO 8601) | Yes | 登録日時 |
| `updatedAt` | `updated_at` | `string` (ISO 8601) | Yes | 更新日時 |

### 1.2 User（参照専用）

`Users` テーブルから `ownerName` を解決するために参照する既存エンティティ。

| Field (JSON / camelCase) | Python Field (`User`) | Type | Description |
| :--- | :--- | :--- | :--- |
| `userId` | `user_id` | `string` | ユーザーの一意識別子（Google `sub`） |
| `name` | `name` | `string \| null` | 表示用氏名（オーナー名解決の第一優先） |
| `email` | `email` | `string \| null` | メールアドレス（`name` 未設定時のフォールバック） |
| `role` | `role` | `'Admin' \| 'User'` | 権限ロール |

---

## 2. Validation Rules

### 2.1 PC 新規登録（モデル名必須化：画面必須）
- **対象フィールド**: `model`
- **ルール**:
  - フロントエンド（`frontend/src/app/pcs/register/page.tsx`）: `model.trim().length > 0` を必須とする。空または空白のみの場合（AI 抽出でモデル名が取得できなかった場合を含む）は登録リクエストを送信せず、画面に必須入力エラーを表示して手入力を促す。
  - バックエンド（`POST /api/pcs`）: 既存仕様を維持し、API 側でのモデル名必須チェックは追加しない。

### 2.2 表示値の正規化ルール（一覧・詳細共通）
- `value == null`、`value.trim() === ""`、または `value.trim().toLowerCase() === "unknown"` の場合は、`"-"` を表示する。

---

## 3. State Transitions（PC 詳細画面での操作条件）

### 3.1 返却手続き導線の表示条件
- `pc.status === "InUse"` **かつ**（`currentUser.id === pc.ownerId` **または** `currentUser.role === "Admin"`）の場合のみ「返却手続き」導線を表示する。
- 返却完了時は既存の返却画面（`/pcs/[pcId]/return`）により `InUse` → `Unused` へ遷移する。

### 3.2 管理者向けステータス更新
- `currentUser.role === "Admin"` の場合のみ操作可能。
- 遷移可能値: `InUse` / `Unused` / `PendingDisposal` / `Disposed`（現在のステータスと同一値の送信は画面上で無効化または警告）。
- 更新成功時は `PCs.status`、`PCs.updatedAt` の更新および `PCUsageHistories` への履歴追加（既存トランザクション処理）が実行される。
