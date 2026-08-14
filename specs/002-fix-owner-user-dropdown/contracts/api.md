# API Contracts

既存契約を基礎とする差分契約。認証トークンの具体的な検証方式は既存認証実装の決定に従い、未定義のトークン形式を本資料で推測しない。

## GET `/api/users`

- **用途**: PC新規登録画面で表示する登録済みユーザー候補を取得する。
- **権限**: Admin。未認証またはUserは拒否する。
- **成功（200）**:
  ```json
  [
    {"userId":"string","name":"string","email":"string","role":"Admin | User"}
  ]
  ```
- **0件（200）**: `[]`。UIは「登録済みユーザーなし」を表示する。
- **失敗**: 非2xxのHTTPレスポンスと、ユーザー一覧を取得できないことを示す `detail` 等の既存エラー形式。UIは空配列として扱わない。

## POST `/api/pcs`

- **用途**: 選択した所有者でPCを新規登録する。既存のスペック解析と管理番号採番を維持する。
- **Request**:
  ```json
  {"ownerId":"string","specsText":"string","pcType":"N | D"}
  ```
- **Server validation**: `ownerId` がUsersに存在し利用可能であることを確認する。Adminは任意の利用可能な `ownerId` を指定できる。一般ユーザーは認証主体本人の `userId` と一致する `ownerId` だけを指定でき、他ユーザー指定は4xxで拒否する。未認証、owner未指定、owner不存在、権限不一致、Users再確認失敗ではPCを保存しない。
- **成功**: 既存 `/api/pcs` のPCレスポンス形式を維持する。少なくとも登録結果の `pcId` と `ownerId` が選択値と一致する。
- **既存動作**: `specsText` の解析、`N-XXX`/`D-XXX` 採番、PC保存は `001-pc-management/contracts/api.md` に従う。

## Lambda proxy

`backend/lambda/src/main.py` の既存プロキシ経由で `/api/users` と `/api/pcs` をECSへ転送する。今回、別の経路や新規エンドポイントは追加しない。