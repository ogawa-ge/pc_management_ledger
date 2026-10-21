# Google Workspace ログイン 事前設定一覧

**対象**: Issue #19（ログインを Microsoft から Google Workspace に変更）
**関連**: [spec.md](./spec.md)、[plan.md](./plan.md)

Google Workspace ログインに切り替えるときに、事前に設定・変更が必要な箇所の一覧です。

- 実際の値（クライアント ID、シークレットなど）はこのファイルやリポジトリに書かず、各設定画面に直接入力してください。
- `<新AmplifyのURL>` は新しい Amplify アプリのルート URL（例: `https://<ブランチ名>.<アプリID>.amplifyapp.com`）に置き換えてください。
- 「対応」列の意味: **追加** = 新しく設定する / **削除** = 設定を消す / **継続** = 今の設定をそのまま使う / **修正** = 値を変える / **不要** = 設定しなくてよい / **範囲外** = この Issue では対応しない

---

## 1. Google Cloud Console（OAuth クライアント）

**担当**: Google Workspace 管理者

| 項目 | 設定する値 | 対応 | 備考 |
|---|---|---|---|
| OAuth 同意画面のユーザーの種類 | 内部 | 追加 | `@genuine-pt.jp` の人だけが使えるようになる |
| アプリ名 | PC管理台帳 | 追加 | Google のログイン画面に表示される |
| アプリケーションの種類 | ウェブ アプリケーション | 追加 | |
| 承認済みの JavaScript 生成元（本番） | `<新AmplifyのURL>` | 追加 | |
| 承認済みの JavaScript 生成元（ローカル） | `http://localhost:3000` | 追加 | |
| 承認済みのリダイレクト URI（本番） | `<新AmplifyのURL>/api/auth/callback/google` | 追加 | 1 文字でも違うとログインできない。末尾の `/` の有無に注意 |
| 承認済みのリダイレクト URI（ローカル） | `http://localhost:3000/api/auth/callback/google` | 追加 | |
| クライアント ID | （発行される） | 追加 | 開発者が受け取り、2・3 に設定する |
| クライアントシークレット | （発行される） | 追加 | **機密**。チャットやメールに平文で貼らない |

## 2. 新 Amplify の環境変数

**担当**: 開発者　**設定場所**: Amplify コンソール →「ホスティング」→「環境変数」

| 変数名 | 設定する値 | 対応 | 備考 |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | 1 で発行されたクライアント ID | 追加 | |
| `GOOGLE_CLIENT_SECRET` | 1 で発行されたクライアントシークレット | 追加 | **機密** |
| `ALLOWED_EMAIL_DOMAIN` | `genuine-pt.jp` | 追加 | ログインを許可するドメイン |
| `NEXTAUTH_URL` | `<新AmplifyのURL>` | 修正 | **ルート URL のみ**。`/login` などのパスを含めるとコールバック URL がおかしくなる（過去に発生済み） |
| `NEXTAUTH_SECRET` | ランダムな文字列 | 継続 | **機密**。ログインセッションの暗号化に使う。新 Amplify 用に新しく生成してもよい |
| `NEXT_PUBLIC_API_URL` | バックエンド API の URL | 継続 | |
| `AZURE_AD_CLIENT_ID` | – | 削除 | |
| `AZURE_AD_CLIENT_SECRET` | – | 削除 | |
| `AZURE_AD_TENANT_ID` | – | 削除 | |
| `AZURE_AD_TENANT_NAME` | – | 削除 | |
| `AZURE_AD_OBJECT_ID` | – | 削除 | |
| ビルド設定（amplify.yml） | ビルドコマンドに `env \| grep -e GOOGLE_ -e ALLOWED_EMAIL_DOMAIN -e NEXTAUTH_ >> .env.production` を追加 | 修正（必要な場合のみ） | Amplify の Next.js では、環境変数がビルド時にしか読めず、ログイン処理の実行時に読めないことがある。その場合だけ対応する。amplify.yml はリポジトリになく Amplify コンソール側で管理されている |

## 3. ローカル開発の `.env.local`

**担当**: 各開発者　**設定場所**: `frontend/.env.local`（git 管理外）

| 変数名 | 設定する値 | 対応 | 備考 |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | 1 で発行されたクライアント ID | 追加 | |
| `GOOGLE_CLIENT_SECRET` | 1 で発行されたクライアントシークレット | 追加 | **機密** |
| `ALLOWED_EMAIL_DOMAIN` | `genuine-pt.jp` | 追加 | |
| `NEXTAUTH_URL` | `http://localhost:3000` | 継続 | |
| `NEXTAUTH_SECRET` | ランダムな文字列 | 継続 | **機密** |
| `NEXT_PUBLIC_API_URL` | バックエンド API の URL | 継続 | |
| `AZURE_AD_CLIENT_ID` | – | 削除 | |
| `AZURE_AD_CLIENT_SECRET` | – | 削除 | |
| `AZURE_AD_TENANT_ID` | – | 削除 | |
| `AZURE_AD_TENANT_NAME` | – | 削除 | リポジトリ直下の `.env.local` にのみ存在 |
| `AZURE_AD_OBJECT_ID` | – | 削除 | リポジトリ直下の `.env.local` にのみ存在 |

## 4. バックエンドの CORS 許可オリジン

**担当**: 新 Amplify への移行担当

| 対象 | 設定する値 | 対応 | 備考 |
|---|---|---|---|
| [backend/lambda/src/main.py](../../backend/lambda/src/main.py) の `allow_origins` | `<新AmplifyのURL>` | 範囲外 | 今は旧 Amplify の URL がコードに直接書かれている。ログイン処理はサーバー間通信で、ブラウザからの API 呼び出しも Next.js の転送（同一オリジン）経由のため、ログイン機能には影響しない（research.md R-11） |
| [backend/ecs/src/main.py](../../backend/ecs/src/main.py) の `allow_origins` | `<新AmplifyのURL>` | 範囲外 | 同上 |

## 5. AWS Lambda（CDK）/ Secrets Manager

**担当**: 開発者

| 対象 | 設定する値 | 対応 | 備考 |
|---|---|---|---|
| Lambda の環境変数 `ALLOWED_EMAIL_DOMAIN` | `genuine-pt.jp` | 追加 | ログイン時のユーザー登録 API でもドメインを再チェックするために使う（research.md R-5）。CDK のデプロイを実行する端末で、環境変数 `ALLOWED_EMAIL_DOMAIN` を設定してからデプロイする。未設定でもデプロイは成功するが、ログインできなくなる（デプロイ時に警告が出る） |
| Google のクライアント ID / シークレット | – | 不要 | Google での認証はフロントエンド（Amplify）側で完結するため、Lambda や Secrets Manager に登録する必要はない |
| [infrastructure/stacks/lambda_stack.py](../../infrastructure/stacks/lambda_stack.py) の `AzureAdSecrets` 参照（環境変数 `AZURE_AD_SECRET_NAME`） | – | 削除 | Lambda のコードからは使われていない。本 Issue の実装でコードから削除する |
| Secrets Manager 上の `AzureAdSecrets` | – | 削除（CDK デプロイ後） | 上の参照を削除した CDK をデプロイした後に、手動で削除する。先に消すと CDK のデプロイが失敗する |
