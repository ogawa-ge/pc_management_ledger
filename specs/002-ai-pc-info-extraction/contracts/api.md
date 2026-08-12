# API Contracts (差分)

本ファイルは[001-pc-management/contracts/api.md](../../001-pc-management/contracts/api.md)の`POST /api/pcs/parse-specs`および`POST /api/pcs`を、実コード調査で判明した不整合を是正した上で再定義するものである。他のエンドポイント（認証、返却等）は001の契約から変更しない。

## PC Management (ECS)

### POST `/api/pcs/parse-specs`

- **Description**: 貼り付けられたターミナル出力テキストをGemini APIに送信し、構造化されたスペック情報を返す（プレビュー専用、DynamoDBへの書き込みなし）。
- **変更点**: 001の契約書は`{"rawText": "string"}`と記載していたが、実装（`PcParseRequest`）は`specs_text`（camelCaseエイリアス`specsText`）を使用しているため、実装に合わせて是正する。レスポンスも実際の抽出対象6項目に統一する（旧: `gpu`/`motherboard`を誤って抽出していたバグを修正）。
- **Request**:
  ```json
  {
    "specsText": "string"
  }
  ```
- **Response（成功時）**:
  ```json
  {
    "cpu": "string | null",
    "memory": "string | null",
    "storage": "string | null",
    "os": "string | null",
    "manufacturer": "string | null",
    "model": "string | null"
  }
  ```
- **Response（Gemini API呼び出しが3回のリトライ後も失敗した場合、FR-007）**:
  ```json
  {
    "error": "string",
    "retriesExhausted": true
  }
  ```
- **Response（貼り付け内容がJSONとして解析不能な場合、FR-006。クライアント側で事前チェックし、本APIを呼ばないことを推奨）**:
  - HTTP 400、`{"error": "Invalid JSON"}`

### POST `/api/pcs`

- **Description**: 新しいPCを登録する（管理番号は自動採番）。
- **変更点（[research.md](../research.md) Decision 4）**: 従来は`specsText`（生テキスト）を受け取りサーバー側で再度Gemini抽出していたが、これではユーザーの手動編集（FR-005）が登録直前に上書きされてしまう。本機能から、クライアントで確定済みの構造化フィールドを直接受け取る方式に変更する。
- **Request**:
  ```json
  {
    "ownerId": "string (optional)",
    "pcType": "N | D",
    "cpu": "string | null",
    "memory": "string | null",
    "storage": "string | null",
    "os": "string | null",
    "manufacturer": "string | null",
    "model": "string | null"
  }
  ```
- **Response**:
  ```json
  {
    "pcId": "string",
    "status": "success"
  }
  ```

## 変更しないエンドポイント

`GET /api/pcs`、`POST /api/pcs/{pcId}/return`、`PATCH /api/pcs/{pcId}/status`、認証系エンドポイントは[001-pc-management/contracts/api.md](../../001-pc-management/contracts/api.md)の定義から変更しない。
