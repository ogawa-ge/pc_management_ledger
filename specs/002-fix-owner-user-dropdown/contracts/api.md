# API Contracts

既存契約を基礎とする差分契約。認証トークンの具体的な検証方式は既存認証実装の決定に従い、未定義のトークン形式を本資料で推測しない。

## Authentication subject

- NextAuth が Azure AD `oid` を JWT `sub` として保持し、session の user ID として公開する。
- Frontend は対象 API へ `Authorization: Bearer <userId>` を付与する。Next.js rewrite と Lambda プロキシはこのヘッダーを ECS へ変更せず転送する。
- ECS は Bearer 資格情報を認証主体の `userId` として Users に照合し、Users に保存された role で Admin/User を判定する。クライアントが送る role や `ownerId` だけでは認可しない。

## GET `/api/users`

- **用途**: PC新規登録画面で表示する登録済みユーザー候補を取得する。
- **権限**: Admin。未認証またはUserは拒否する。
- **成功（200）**:
  ```json
  [
    {
      "userId":"string",
      "name":"string | null",
      "email":"string | null",
      "role":"Admin | User",
      "createdAt":"string | null",
      "updatedAt":"string | null"
    }
  ]
  ```
- DynamoDB scan は `LastEvaluatedKey` がなくなるまで継続し、最初に取得した同一 `userId` だけを返す。`name` または `email` が欠落していても候補から除外しない。
- **0件（200）**: `[]`。UIは「登録済みユーザーなし」を表示する。
- **失敗**: FastAPI 標準の `{"detail":"string"}` 形式を返し、UIは空配列として扱わない。
  - **401 Unauthorized**: Authorization ヘッダーなし、Bearer 形式不正、または認証主体がUsersに存在しない。
  - **403 Forbidden**: 認証済みの一般ユーザーがAdmin専用の候補一覧を要求した。
  - **503 Service Unavailable**: Usersからの認証主体確認または一覧取得を完了できない。

## POST `/api/pcs`

- **用途**: 選択した所有者でPCを新規登録する。既存のスペック解析と管理番号採番を維持する。
- **Request**:
  ```json
  {"ownerId":"string","specsText":"string","pcType":"N | D"}
  ```
- **Server validation**: `ownerId` がUsersに存在し利用可能であることを確認する。Adminは任意の利用可能な `ownerId` を指定できる。一般ユーザーは認証主体本人の `userId` と一致する `ownerId` だけを指定でき、他ユーザー指定は4xxで拒否する。未認証、owner未指定、owner不存在、権限不一致、Users再確認失敗ではPCを保存しない。
- **成功（200）**: 既存 `Pc` response model を camelCase で返す。`pcId`、選択値と一致する `ownerId`、`type`、`status`、既存スペック項目、`createdAt`、`updatedAt` を含む。
- **失敗**: FastAPI 標準の `{"detail":"string"}` 形式を返し、いずれもPCを保存しない。
  - **401 Unauthorized**: Authorization ヘッダーなし、Bearer 形式不正、または認証主体がUsersに存在しない。
  - **403 Forbidden**: 一般ユーザーが認証主体本人以外の `ownerId` を指定した。
  - **404 Not Found**: 指定した `ownerId` が登録時点でUsersに存在しない。body は `{"detail":"Owner not found"}`。
  - **422 Unprocessable Entity**: 必須の `ownerId` が欠落しているなど、リクエスト形式が検証に失敗した。
  - **503 Service Unavailable**: Usersからの認証主体確認またはowner存在確認を完了できない。owner再確認失敗時のbodyは `{"detail":"Failed to verify owner"}`。
  - **500 Internal Server Error**: 上記以外の予期しないPC作成処理の失敗。
- **既存動作**: `specsText` の解析、`N-XXX`/`D-XXX` 採番、PC保存は `001-pc-management/contracts/api.md` に従う。

## Lambda proxy

`backend/lambda/src/main.py` の既存プロキシ経由で `/api/users` と `/api/pcs` をECSへ転送する。ECSが返したstatus/bodyは変更せずクライアントへ転送する。ECS停止中は既存どおり503、ECSへの転送失敗は502を返す。今回、別の経路や新規エンドポイントは追加しない。