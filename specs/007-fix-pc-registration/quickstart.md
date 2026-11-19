# Quickstart: PC新規登録時の登録失敗・画面固まり解消の検証・デプロイ手順

> 機密情報（アカウントID、ユーザーID、ロール名など）は記録せず `<...>` に置換する。

## 0. 原因の実証（実装前 / T000・読み取り専用）
`Force_MFA` ポリシーのため、MFA セッション（`aws sts get-session-token`）の認証情報を設定した状態で実施する。

1. **ECS タスクロールのポリシー確認**
   ```powershell
   aws ecs describe-services --cluster PCManagementCluster --services PCManagementService --query "services[0].taskDefinition"
   aws ecs describe-task-definition --task-definition <task-definition-arn> --query "taskDefinition.taskRoleArn"
   aws iam list-role-policies --role-name <task-role-name>
   aws iam get-role-policy --role-name <task-role-name> --policy-name <policy-name>
   ```
   → `PCs` / `PCUsageHistories` / `ReturnRecords` / `SystemActivity` はあるが、**`Users` がない**ことを確認する。
2. **ECS ログ確認**
   ```powershell
   aws logs describe-log-groups --log-group-name-prefix EcsStack
   aws logs filter-log-events --log-group-name <ecs-log-group> --filter-pattern "AccessDenied"
   ```
   → `Users` テーブルへの `dynamodb:GetItem`（または `Scan`）の `AccessDeniedException` を確認する（ログがない場合は PC 登録操作を 1 回試行して再確認する）。
3. **ApiLambda ログ確認**
   - ロググループ `/aws/lambda/LambdaStack-ApiLambda…` で、PC 登録操作時刻（2026-11-17 夕方）の `POST /api/pcs 503` を確認する。
4. 結果を `research.md` の Decision 3 配下に追記する。**確認できない場合は実装を止めて再分析する。**

## 1. CDK 単体テスト（ローカル）
- **前提**: `.venv` に `pytest` が未導入の場合は先に開発用依存を導入する：
  ```powershell
  .\.venv\Scripts\pip.exe install -r infrastructure/requirements-dev.txt
  ```
- **実行コマンド**:
  ```powershell
  .\.venv\Scripts\pytest.exe infrastructure/tests/unit/
  ```
- **確認内容**:
  - `EcsStack` のタスクロールに `Users` テーブルの読み取り権限（`dynamodb:GetItem` / `Scan` 等）が付与され、書き込み権限（`dynamodb:PutItem` / `DeleteItem` / `UpdateItem`）が付与されていないこと。
  - 既存の CDK 単体テストが全件パスすること。

## 2. フロントエンド ビルド・型チェック確認
- ローカルに `frontend/node_modules` が存在する場合：
  ```powershell
  cd frontend
  npm run build
  ```
- ローカルに `frontend/node_modules` が未導入の場合は、`git diff` による構文・型整合性の目視検証を行い、`main` へのプッシュ後の AWS Amplify 自動ビルド（`next build`）の成功をもってビルド検証を完了とする。

## 3. 前提条件（デプロイ・実機検証の前に）
- **Docker Desktop を起動**しておく（`EcsStack` は `backend/ecs` から Docker イメージをビルドするため）。
- **MFA セッションの認証情報**を設定する（§0 と同様）。
- `.venv`（`infrastructure/requirements.txt` 導入済み）と `cdk` CLI が使えること。
- **コンテキストを変更しない**: `-c internalProxyKeyId=...` は指定しない（既定の `current` のまま。内部署名キーの世代を変えないため）。
- **管理者アカウント（任意）**: 初回ログインのユーザーは常に一般ユーザー（`role=User`）で作成される。管理者の代理登録を検証する場合は、事前に対象ユーザーの `Users` テーブルの `role` を `Admin` へ手動変更する（対象は `<user-id>` / `<email>` で特定し、記録時はマスクする）。管理者アカウントがない場合、管理者系の検証は実施せず一般ユーザーの検証のみ行う。

## 4. デプロイ手順
1. 差分確認:
   ```powershell
   cd infrastructure
   cdk diff EcsStack
   ```
   - **想定される差分**（実際の出力で確認する）:
     - ECS タスクロールの IAM ポリシーに `Users` テーブルの読み取り権限が追加される。
     - `backend/ecs` の最新コードを反映した Docker イメージとタスク定義の新リビジョンが含まれる可能性がある（`ContainerImage.from_asset` のため。IAM のみの変更とは限らない）。
     - `DesiredCount: 0` がテンプレートに固定されているため、**稼働中の ECS タスクは停止する可能性がある**（Lambda が ECS の実状態と照合して再起動するため許容）。
   - 上記以外の想定外の差分（VPC / ネットワーク / 他スタックなど）がある場合は**デプロイを中止**して原因を確認する。
   - `ALLOWED_EMAIL_DOMAIN` 未設定の警告は `LambdaStack` 由来であり、`EcsStack` のデプロイには影響しない。
2. デプロイ: `cdk deploy EcsStack`
3. フロントエンド: 変更を `main` にプッシュし、Amplify のデプロイ完了を待つ。

## 5. 本番実機検証
1. 本番サイトに一般ユーザーでログインし、`/pcs/register` で PC 情報を入力して「PCを登録」をクリックする。
2. エラーにならず「PCの登録が完了しました。」が表示され、`/pcs` に遷移して登録した PC が一覧に表示されることを確認する。
3. （管理者アカウントがある場合）管理者でログインし、オーナー候補一覧が表示されること、オーナーを選択して代理登録できることを確認する。ECS 停止直後であれば、ECS起動待機表示が出て自動待機のうえ候補が表示されることも確認する。
4. 登録失敗を意図的に再現できる場合は、ECS起動待機表示が解除され、ボタン直上に日本語の赤字エラーが表示されることを確認する。
