# トラブルシューティングガイド

このファイルは、開発中に発生した問題とその解決方法を記録するために使用されます。

## 解決済みの問題

### 問題: Python 3.14 と google-generativeai の互換性
#### 概要
- 発生した日時: 2026-06-02
- 問題の詳細: `google-generativeai` ライブラリが Python 3.14 で "Metaclasses with custom tp_new are not supported" エラーを吐く。
- 影響範囲: `gemini-service.py` による API 呼び出し。
#### 解決方法
- 解決手順: `urllib.request` を使用した直接的な REST API 呼び出しに実装を変更し、外部ライブラリ依存を排除した。

### 問題: Next.js ビルドエラー (pages and app directories)
#### 概要
- 発生した日時: 2026-06-05
- 問題の詳細: `pages` ディレクトリと `app` ディレクトリが混在している際に、同一のルートフォルダに配置されていないとビルドエラーになる。
- 影響範囲: フロントエンドのビルド。
#### 解決方法
- 解決手順: `pages/` ディレクトリを `src/pages/` へ移動し、ディレクトリ構造を統一した。

### 問題: ESM と CommonJS の混在エラー
#### 概要
- 発生した日時: 2026-06-05
- 問題の詳細: `package.json` が `commonjs` 指定の状態で ESM の `import/export` を使用したため Turbopack ビルドが失敗。
- 影響範囲: フロントエンドのビルド。
#### 解決方法
- 解決手順: `package.json` に `"type": "module"` を追加し、`next.config.js` を `export default` 形式に変更した。

### 問題: Amplify 環境変数キー末尾のスペース混入による Google OAuth 認証エラー
#### 概要
- 発生した日時: 2026-11-12
- 問題の詳細: AWS Amplify の Web コンソールで環境変数（`GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`、`NEXTAUTH_URL`）を設定した際、キー名の末尾に半角スペース（例: `GOOGLE_CLIENT_ID `）が混入していた。AWS コンソール画面上では見た目上スペースが判別しづらく、アプリケーション側から環境変数が参照できずに認証エラーとなった。
- 影響範囲: フロントエンドの NextAuth.js（Google Workspace OAuth ログイン）。
#### 解決方法
- 解決手順: AWS CLI / SDK（`amplify get-app` / `update-app`）で環境変数の正確なキー名を確認し、末尾スペースを除去したキー名に再設定するとともに、不要な旧 `AZURE_AD_*` 変数の削除および `NEXTAUTH_SECRET` の新規ランダム値へのローテーションを実施した。

### 問題: Amplify 共有ドメイン上での Google セーフ ブラウジング誤検知（赤画面警告）
#### 概要
- 発生した日時: 2026-11-12
- 問題の詳細: `*.amplifyapp.com` ドメイン上で Google Workspace ログインを実行した際、Chrome の Google セーフ ブラウジング機能により「危険なサイト（フィッシング検出）」の赤画面警告が誤検知（False Positive）で表示された。
- 影響範囲: フロントエンド（ログイン画面および `/api/auth/callback/google`）。
#### 解決方法
- 解決手順（Issue #29）:
  1. 担当者の Google アカウントで Google Search Console を開き、「URL プレフィックス」に対象の Amplify URL（`https://<branch>.<app-id>.amplifyapp.com/`）を追加して所有権確認用 HTML ファイル（`google*.html`）を取得。
  2. `frontend/public/` に確認用 HTML ファイルを配置し、未ログインの Google 確認ボットが `/login` へリダイレクトされないよう `frontend/src/middleware.ts` の `config.matcher` から `google.*\.html`（および `robots\.txt`）を除外してデプロイ。
  3. Search Console で「所有権の確認」を完了後、「セキュリティと手動による対策」＞「セキュリティの問題」＞「審査をリクエスト」から、社内用業務アプリであり正規の Google Workspace OAuth 2.0（NextAuth.js GoogleProvider）を使用している旨を記載して解除申請を送信した。
