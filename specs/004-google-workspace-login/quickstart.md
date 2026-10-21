# Quickstart — ログイン方式のGoogle Workspaceへの変更

**Feature**: [spec.md](./spec.md) | **Contracts**: [contracts/api.md](./contracts/api.md) | **Data Model**: [data-model.md](./data-model.md)

本機能が動いていることを確認するための手順です。

## 1. 前提

- Google Cloud Console の OAuth クライアントと環境変数の設定が済んでいること。設定する項目は [environment-setup.md](./environment-setup.md) を参照。
- 動作確認用に、次の 2 種類の Google アカウントを用意すること。
  - `@genuine-pt.jp` のアカウント（許可される側）
  - 個人の Gmail アカウント（拒否される側）

## 2. ローカルでの起動

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env.local` に、environment-setup.md の「3. ローカル開発の `.env.local`」の変数を設定しておきます。

Lambda 側の確認をするときは、Lambda の実行環境に `ALLOWED_EMAIL_DOMAIN=genuine-pt.jp` を設定します。

## 3. 自動テスト（Lambda）

```bash
cd backend
pytest tests -k sync_user
```

期待結果: 次のケースがすべて成功すること。

| ケース | 期待 |
|---|---|
| `@genuine-pt.jp` の新規ユーザー | 200、`role = User`、`created = true` |
| 登録済みユーザー（`role = Admin`）の再ログイン | 200、`role = Admin` のまま、`created = false` |
| `@gmail.com` | 403、Users に書き込まれない |
| `@sub.genuine-pt.jp`、`@genuine-pt.jp.example.com`、`@xgenuine-pt.jp` | 403 |
| `@GENUINE-PT.JP`（大文字） | 200（大文字・小文字は同一扱い） |
| `email` が空 | 400 |
| `ALLOWED_EMAIL_DOMAIN` 未設定 | 500 |

## 4. 手動での確認シナリオ

| # | 操作 | 期待結果 | 対応 |
|---|---|---|---|
| 1 | ログイン画面を開く | 「Googleアカウントでログイン」のボタンだけが表示され、Microsoft の表記がない | US1-4、SC-003 |
| 2 | `@genuine-pt.jp` のアカウントでログインする | PC 一覧画面が表示され、ヘッダーに「一般ユーザー (User)」と表示される | US1-1、US1-2 |
| 3 | DynamoDB の `Users` を確認する | `userId`（数字の文字列）・`email`・`name`・`role = User` のアイテムが 1 件ある | US1-2、FR-006 |
| 4 | ログアウトする | ログイン画面に戻る | US1-5 |
| 5 | ログアウト状態で `/pcs` に直接アクセスする | ログイン画面にリダイレクトされる | US1-3 |
| 6 | 個人の Gmail アカウントでログインを試みる | ログイン画面に「会社のGoogleアカウントでログインしてください」と表示される。`Users` にアイテムが増えない | US2-1、US2-3、SC-002 |
| 7 | 6 の直後にログを確認する（ローカルはターミナル、本番は CloudWatch Logs） | `"event":"login_rejected"` と、日時・メールアドレスを含む 1 行が出ている | FR-012 |
| 8 | Google のアカウント選択画面でキャンセルする | ログイン画面に戻り、エラーメッセージは表示されない | Edge Cases |
| 9 | ログイン処理中に、ECS のタスクを確認する | ECS が起動していない（停止中のままである） | FR-010、SC-004 |

## 5. 本番（新 Amplify）への切り替え手順

1. environment-setup.md の 1〜3・5 を設定する。
2. **`NEXTAUTH_SECRET` を新しい値に変更する。** 旧 Microsoft ログインのセッションが無効になる（research.md R-8）。
3. CDK をデプロイする（Lambda の環境変数 `ALLOWED_EMAIL_DOMAIN` が設定され、`AzureAdSecrets` の参照が外れる）。デプロイを実行する端末で、環境変数 `ALLOWED_EMAIL_DOMAIN` を設定しておくこと。未設定だとデプロイは成功するが、ログイン時のユーザー登録が失敗してログインできない。デプロイ時の警告を確認すること。
4. 既存データを削除する（下記「6. 既存データの削除」）。
5. Amplify を再デプロイする。
6. 手動での確認シナリオ 1〜9 を本番 URL で実施する。
7. 最初の管理者を設定する（下記「7. 最初の管理者の設定」）。

### Amplify のログ確認

シナリオ 7 を本番で確認するときは、Amplify コンソール →「ホスティング」→「モニタリング」→「ホスティングコンピューティングログ」から CloudWatch Logs を開きます。ログが出ていない場合は、Amplify アプリにサービスロール（CloudWatch Logs への書き込み権限付き）が設定されているか確認してください。

## 6. 既存データの削除

対象は `Users`・`PCs`・`ReturnRecords`・`PCUsageHistories` の 4 テーブルです。`SystemActivity` は削除しません（data-model.md 参照）。

開発中でデータ件数が少ないため、AWS コンソールで削除します。

1. DynamoDB →「テーブル」→ 対象テーブル →「テーブルアイテムの探索」を開く
2. 全件を表示して、すべて選択する
3. 「アクション」→「項目を削除」を実行する
4. 4 テーブルすべてで繰り返す

## 7. 最初の管理者の設定

1. 管理者にする人が、`@genuine-pt.jp` のアカウントで一度ログインする（`Users` に `role = User` で登録される）
2. DynamoDB →「テーブル」→ `Users` →「テーブルアイテムの探索」で、その人の `email` のアイテムを開く
3. `role` を `Admin` に変更して保存する
4. 本人がログアウトして再ログインし、ヘッダーに「管理者 (Admin)」と表示されることを確認する
