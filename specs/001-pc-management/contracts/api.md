# API Contracts

## Authentication (Lambda)

### POST `/api/auth/login`
- **Description**: Microsoftアカウントのトークンを検証し、セッショントークンとユーザー権限を返す。
- **Request**:
  ```json
  {
    "accessToken": "string"
  }
  ```
- **Response**:
  ```json
  {
    "token": "string",
    "user": {
      "userId": "string",
      "name": "string",
      "role": "Admin | User"
    }
  }
  ```

## PC Management (ECS)

### GET `/api/pcs`
- **Description**: PCの一覧を取得する。
- **Response**:
  ```json
  {
    "pcs": [
      {
        "pcId": "string",
        "ownerId": "string",
        "type": "Notebook | Desktop",
        "status": "InUse | Unused | PendingDisposal | Disposed",
        "cpu": "string",
        "memory": "string",
        "storage": "string",
        "os": "string",
        "manufacturer": "string",
        "model": "string"
      }
    ]
  }
  ```

### POST `/api/pcs/parse-specs`
- **Description**: ターミナルから取得したテキストデータをGemini APIに送信し、構造化されたスペック情報を返す。
- **Request**:
  ```json
  {
    "rawText": "string"
  }
  ```
- **Response**:
  ```json
  {
    "cpu": "string",
    "memory": "string",
    "storage": "string",
    "os": "string",
    "manufacturer": "string",
    "model": "string"
  }
  ```

### POST `/api/pcs`
- **Description**: 新しいPCを登録する（管理番号は自動採番）。
- **Request**:
  ```json
  {
    "ownerId": "string (optional)",
    "type": "Notebook | Desktop",
    "cpu": "string",
    "memory": "string",
    "storage": "string",
    "os": "string",
    "manufacturer": "string",
    "model": "string"
  }
  ```
- **Response**:
  ```json
  {
    "pcId": "string",
    "status": "success"
  }
  ```

### POST `/api/pcs/{pcId}/return`
- **Description**: PCの返却手続きを行う。
- **Request**:
  ```json
  {
    "returnDate": "YYYY-MM-DD",
    "reason": "string",
    "condition": "string"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success"
  }
  ```
### PATCH `/api/pcs/{pcId}/status`
- **Description**: PC のステータスを更新する。管理者のみ実行可能。
- **Permissions**: Admin role required
- **Request**:
  ```json
  {
    "newStatus": "InUse | Unused | PendingDisposal | Disposed"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "pcId": "string",
    "previousStatus": "string",
    "newStatus": "string",
    "updatedAt": "ISO 8601 timestamp"
  }
  ```