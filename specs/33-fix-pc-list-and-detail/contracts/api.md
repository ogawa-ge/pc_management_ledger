# API Contracts: PC一覧の表示不整合修正およびPC詳細画面の実装

**Feature**: Issue #33 (`specs/33-fix-pc-list-and-detail`)  
**Base Runtime**: Amazon ECS (FastAPI) via Lambda Proxy (`/api/*`)

---

## 1. `GET /api/pcs`（既存エンドポイント拡張）

全 PC 一覧（またはステータス絞り込み一覧）を取得し、各 PC に解決済みの `ownerName` を付与して返却する。

- **Query Parameters**:
  - `status` (optional): `InUse` | `Unused` | `PendingDisposal` | `Disposed`
- **Response (`200 OK`)**: `Pc[]`
  ```json
  [
    {
      "pcId": "N-001",
      "ownerId": "google-sub-123",
      "ownerName": "山田 太郎",
      "type": "Notebook",
      "status": "InUse",
      "pcName": "DEV-LAPTOP-01",
      "cpu": "Intel Core i7-1365U",
      "memory": "16.0",
      "storage": "512.0",
      "os": "Microsoft Windows 11 Pro",
      "manufacturer": "Lenovo",
      "model": "ThinkPad X1 Carbon Gen 11",
      "gpu": "Intel Iris Xe Graphics",
      "serialNumber": "PF123456",
      "createdAt": "2026-11-19T05:00:00.000000",
      "updatedAt": "2026-11-19T05:00:00.000000"
    }
  ]
  ```
- **`ownerName` 解決仕様**:
  - `ownerId` が未設定（空文字または `null`）、または `status != "InUse"`（`Unused` / `PendingDisposal` / `Disposed`）の場合: `ownerName` は `null`（フロントエンドで「未割り当て」表示）
  - `status == "InUse"` かつ `ownerId` が `Users` に存在: `user.name`（未設定の場合は `user.email`、いずれも未設定なら `"不明なユーザー"`）
  - `status == "InUse"` かつ `ownerId` が `Users` に存在しない: `ownerName` は `"不明なユーザー"`
- **Error Responses**:
  - `500 Internal Server Error`: DynamoDB 取得失敗時
  - `503 Service Unavailable` (`status: "starting"`): ECS コールドスタート中（Lambda プロキシ応答、フロントエンドが自動再試行）

---

## 2. `GET /api/pcs/{pc_id}`（新規エンドポイント）

指定された管理番号（`pc_id`）に一致する単一 PC の詳細情報を、`ownerName` を解決した状態で返却する。

- **Path Parameters**:
  - `pc_id` (required): 管理番号（例: `N-001`）
- **Response (`200 OK`)**: `Pc`
  ```json
  {
    "pcId": "N-001",
    "ownerId": "google-sub-123",
    "ownerName": "山田 太郎",
    "type": "Notebook",
    "status": "InUse",
    "pcName": "DEV-LAPTOP-01",
    "cpu": "Intel Core i7-1365U",
    "memory": "16.0",
    "storage": "512.0",
    "os": "Microsoft Windows 11 Pro",
    "manufacturer": "Lenovo",
    "model": "ThinkPad X1 Carbon Gen 11",
    "gpu": "Intel Iris Xe Graphics",
    "serialNumber": "PF123456",
    "createdAt": "2026-11-19T05:00:00.000000",
    "updatedAt": "2026-11-19T05:00:00.000000"
  }
  ```
- **Error Responses**:
  - `404 Not Found`: 指定された `pc_id` が `PCs` テーブルに存在しない場合
    ```json
    { "detail": "PC not found: N-999" }
    ```
  - `500 Internal Server Error`: 予期しないサーバーエラー
  - `503 Service Unavailable` (`status: "starting"`): ECS コールドスタート中

---

## 3. `POST /api/pcs/{pc_id}/return`（既存エンドポイント・フロントエンド認証ヘッダー修正）

詳細画面から遷移する返却手続き画面が呼び出す既存エンドポイント。バックエンドは `get_request_principal` により `Authorization` ヘッダーを必須としているため、フロントエンド（`frontend/src/services/pc-api.ts` の `returnPC`）から `Authorization: Bearer <userId>` を送信するよう修正する（バックエンド仕様変更なし）。

- **Headers**:
  - `Authorization: Bearer <userId>` (required)
  - `Idempotency-Key: <UUID>` (required)
- **備考**: `POST /api/pcs`（新規 PC 登録）については、モデル名必須化をフロントエンド画面のみで実施するため API 契約変更は行わない。

---

## 4. `PATCH /api/pcs/{pc_id}/status`（既存エンドポイント・詳細画面から利用）

管理者が PC 詳細画面からステータスを更新する際に呼び出す既存エンドポイント（バックエンド仕様変更なし）。

- **Headers**:
  - `Authorization: Bearer <adminUserId>` (required, Admin role)
  - `Idempotency-Key: <UUID>` (required)
- **Request Body**:
  ```json
  {
    "newStatus": "PendingDisposal",
    "reason": "画面破損のため廃棄予定"
  }
  ```
- **Response (`200 OK`)**:
  ```json
  {
    "status": "success",
    "pcId": "N-001",
    "previousStatus": "InUse",
    "newStatus": "PendingDisposal",
    "updatedAt": "2026-11-25T08:30:00.000000"
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: 不正なステータス値 / `Idempotency-Key` 欠如・形式不正
  - `401 Unauthorized` / `403 Forbidden`: 未認証または管理者以外
  - `404 Not Found`: 対象 PC が存在しない
