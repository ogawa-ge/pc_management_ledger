# API Contracts — ログイン方式のGoogle Workspaceへの変更

**Feature**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

## Authentication (Lambda)

### POST `/api/auth/sync-user`（新規）

- **Description**: ログイン時に、Google アカウントの情報で Users を upsert し、ロールを返す。NextAuth の `signIn` コールバック（サーバー側）からのみ呼び出す。ブラウザからは呼ばないため、Next.js の `rewrites` には追加しない。
- **実行場所**: Lambda（ECS へプロキシしない。`proxy_to_ecs` のキャッチオールルートより前に定義する）
- **Request**:
  ```json
  {
    "userId": "string（Google の sub）",
    "email": "string",
    "name": "string | null"
  }
  ```
- **Response 200**:
  ```json
  {
    "userId": "string",
    "role": "Admin | User",
    "created": true
  }
  ```
  `created` は今回のリクエストで新規作成した場合に `true`、既存ユーザーの更新なら `false`。
- **Response 400**: `userId` または `email` が空・不正な形式
  ```json
  { "detail": "userId and email are required" }
  ```
- **Response 403**: `email` のドメインが `ALLOWED_EMAIL_DOMAIN` と一致しない（Users には書き込まない。拒否ログを出力する）
  ```json
  { "detail": "Email domain is not allowed" }
  ```
- **Response 500**: `ALLOWED_EMAIL_DOMAIN` が未設定、または DynamoDB への書き込み失敗
  ```json
  { "detail": "Failed to sync user" }
  ```
- **Behavior**:
  - 未登録: `role = User`、`createdAt = updatedAt = 現在時刻` で作成する
  - 登録済み: `email`・`name`・`updatedAt` のみ更新し、`role`・`createdAt` は保持する
  - 同じリクエストを複数回送っても結果は同じ（冪等）

### POST `/api/auth/user-permissions`（変更なし）

既存のまま。`userId` に Google の `sub` が入るようになるだけで、入出力は変わらない。

## Frontend (NextAuth)

### 認証プロバイダ

| 項目 | 変更前 | 変更後 |
|---|---|---|
| プロバイダ ID（`signIn()` の第 1 引数） | `azure-ad` | `google` |
| コールバック URL | `/api/auth/callback/azure-ad` | `/api/auth/callback/google` |
| `session.user.id` | Azure AD の `oid` | Google の `sub` |
| `session.accessToken` | Azure AD のアクセストークン | 削除（利用箇所なし） |

`session.user` の型（`id`・`role`・`permissions`・`name`・`email`）は変更しない。

### ログイン画面のエラー表示（`/login?error=<code>`）

| `error` | 表示メッセージ |
|---|---|
| `DomainNotAllowed` | 会社のGoogleアカウントでログインしてください |
| `RegistrationFailed` | ログインに失敗しました。しばらくしてから再度お試しください |
| キャンセル時の値（実装時に確定） | 表示しない |
| 上記以外 | ログインに失敗しました。しばらくしてから再度お試しください |

### 拒否ログの形式（FR-012）

フロントエンド（Amplify SSR）・Lambda のどちらで拒否した場合も、次の形式で 1 行の JSON を出力する。

```json
{
  "event": "login_rejected",
  "reason": "domain_not_allowed | email_not_verified",
  "email": "string",
  "timestamp": "ISO 8601 (UTC)",
  "source": "frontend | lambda"
}
```
