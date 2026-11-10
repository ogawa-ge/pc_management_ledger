# Interface Contracts: API & Routing Gate

**Feature**: `005-prevent-bot-ecs-wakeup`  
**Status**: Completed  
**Last Updated**: 2026-11-06  

---

## 1. ルーティングゲート仕様

### 1.1 エンドポイント一覧と振る舞い

| パスパターン | HTTPメソッド | 処理方式 | ECS起動トリガー | 期待レスポンス |
|---|---|---|---|---|
| `/` | GET | Lambda 直接応答 | **なし** | 200 OK (`{"Hello": "World"}`) |
| `/api/auth/me` | GET | Lambda 直接応答 (JWT認証) | **なし** | 200 OK または 401/403 |
| `/api/auth/validate` | GET | Lambda 直接応答 (トークン検証) | **なし** | 200 OK |
| `/api/auth/user-permissions` | POST | Lambda 直接応答 (権限取得) | **なし** | 200 OK |
| `/api/{path:path}` | GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD | **ECS リバースプロキシ** | **あり (停止時のみ)** | 503 (起動中通知) または 2xx/4xx/5xx (ECS転送結果) |
| `/robots.txt`, `/favicon.ico`, その他非 `/api/*` パス | ANY | FastAPI ルーティング対象外 | **なし (完全遮断)** | **404 Not Found** (`{"detail": "Not Found"}`) |

---

## 2. コントラクト詳細

### 2.1 非業務パス・ボットアクセスの遮断コントラクト

- **対象パス**: `/api/` プレフィックスを持たないすべての未定義パス（例: `GET /robots.txt`, `GET /favicon.ico`, `POST /xmlrpc.php`）
- **HTTP ステータスコード**: `404 Not Found`
- **レスポンスヘッダー**:
  - `content-type`: `application/json`
- **レスポンスボディ**:
  ```json
  {
    "detail": "Not Found"
  }
  ```
- **内部動作制約**:
  - `ecs_manager.ensure_ecs_running()` は **絶対に呼び出されない** こと。
  - `ecs_manager.record_request_accepted()` は **絶対に呼び出されない** こと。
  - DynamoDB `SystemActivity` レコードへの書き込みが一切発生しないこと。

---

### 2.2 正規業務 API リクエストのプロキシコントラクト

#### 2.2.1 ECS スリープ中（初回アクセス・起動中）

- **リクエスト**: `GET /api/pcs` など
- **HTTP ステータスコード**: `503 Service Unavailable`
- **レスポンスヘッダー**:
  - `Retry-After`: `15`
  - `Cache-Control`: `no-store`
  - `Content-Type`: `application/json`
- **レスポンスボディ**:
  ```json
  {
    "status": "starting",
    "message": "バックエンドを起動しています。操作は自動的に再試行されます。",
    "requestId": "550e8400-e29b-41d4-a716-446655440000",
    "retryAfterSeconds": 15,
    "maxWaitSeconds": 180
  }
  ```
- **内部動作**:
  - `SystemActivity` の `lastActivityAt` が現在時刻（ISO8601）で初期化される。
  - `runtimeState` が `STARTING` へ遷移し、ECS タスクの起動指示（DesiredCount=1）が行われる。

#### 2.2.2 ECS 稼働中

- **リクエスト**: `GET /api/pcs?sort=asset_number` など
- **転送先**: `http://{public_ip}:80/api/pcs?sort=asset_number`
- **内部署名ヘッダー**:
  - `X-Internal-Signature`, `X-Internal-Timestamp`, `Idempotency-Key`, `X-Internal-Request-Id`
- **レスポンス**:
  - ECS から返却されたステータスコード、ボディ、ヘッダーをそのままクライアントへ透過返却。
  - 成功時 (2xx) は `lastActivityAt` が最新時刻に更新される。

---

### 2.3 定期監視パトロール（TimeoutCheckLambda）コントラクト

- **実行トリガー**: EventBridge ルール（15分間隔）
- **ハンドラー**: `lambda_handler_cloudwatch_timeout_check`
- **判定処理結果レスポンス**:
  - **自動停止実行時**:
    ```json
    {
      "status": "auto_slept",
      "idle_time_seconds": 7245.0,
      "action_result": {
        "status": "stopped",
        "message": "ECS service stopped (sleeping)",
        "desired_count": 0
      }
    }
    ```
  - **稼働継続（アイドル未満）時**:
    ```json
    {
      "status": "active",
      "idle_time_seconds": 1200.0,
      "remaining_until_auto_sleep": 6000.0
    }
    ```
  - **すでにスリープ中**:
    ```json
    {
      "status": "already_sleeping",
      "message": "ECS is already in sleep state"
    }
    ```
