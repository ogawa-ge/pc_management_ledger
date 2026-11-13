# Quickstart & 手動対応記録: Google Search Console 所有権確認・赤画面対策

## 1. ビルド確認（ローカル）
```powershell
cd frontend
npm run build
```

---

## 2. 本番環境での手動対応ログ（時系列・機密情報マスキング済み）

### Step 1: AWS Amplify 環境変数の不整合修正（事前対応）
Google Workspace ログインの動作確認にあたり、AWS Amplify Hosting の環境変数設定に以下の問題が確認されたため修正を実施した。
1. **キー名末尾の半角スペース除去**:
   - Web コンソールからのコピー＆ペースト時に `GOOGLE_CLIENT_ID `、`GOOGLE_CLIENT_SECRET `、`NEXTAUTH_URL ` の変数名（Key）末尾に半角スペースが混入していた（Web コンソール上ではトリミング表示され判別困難）。
   - AWS CLI / SDK よりスペースなしの正しいキー名へ更新し、スペース付きの旧キーを削除。
2. **不要な旧認証変数の削除**:
   - 旧 Microsoft Entra ID（Azure AD）認証時代の名残である `AZURE_AD_CLIENT_ID`、`AZURE_AD_CLIENT_SECRET`、`AZURE_AD_TENANT_ID` を削除。
3. **`NEXTAUTH_SECRET` のローテーション**:
   - 旧環境から引き継がれていた `NEXTAUTH_SECRET` を、暗号学的に安全な新しいランダム文字列（32バイト base64url）へ更新し、再デプロイを実施。
   - これにより Google Workspace OAuth ログイン自体が正常に完了することを確認。

### Step 2: Google Search Console での所有権確認ファイルの取得
Google ログイン後のコールバック（`/api/auth/callback/google`）および画面遷移時に、Chrome の Google セーフ ブラウジング機能により「危険なサイト（フィッシング検出）」の赤画面警告（共有ドメイン `*.amplifyapp.com` 上のログイン画面に対する誤検知）が表示されたため、以下の手順で対策を実施した。
1. 社内 Google アカウントで [Google Search Console](https://search.google.com/search-console/welcome) にアクセス（※独自ドメイン管理用のアカウントではなく、担当者自身の Google アカウントで登録可能）。
2. プロパティタイプの選択で **「URL プレフィックス」** を選択し、Amplify の公開 URL（`https://<branch>.<app-id>.amplifyapp.com/`）を入力。
3. 「所有権の確認」＞「その他の確認方法」＞ **「HTML ファイル」** を選択し、確認用ファイル（`google6f17d6e6785211dc.html`）を発行。

### Step 3: コード反映・Amplify デプロイ（Issue #29）
1. `frontend/public/google6f17d6e6785211dc.html` を配置。
2. 未ログイン状態の Google クローラーが `/login` へリダイレクト（HTTP 307）されるのを防ぐため、`frontend/src/middleware.ts` の `config.matcher` に `google.*\.html` と `robots\.txt` の除外設定を追加。
3. `main` ブランチへマージ・プッシュし、Amplify の自動デプロイを完了。

### Step 4: 所有権の確認完了と「審査をリクエスト」送信
1. Amplify デプロイ完了後、Google Search Console の「所有権の確認（HTML ファイル）」で **「確認」** をクリックし、所有権の証明に成功。
2. 左メニュー **「セキュリティと手動による対策」** ＞ **「セキュリティの問題」** を開く（「不正なページ」が1件検出されている状態を確認）。
3. **「審査をリクエスト」** をクリックし、「問題をすべて修正しました」にチェックを入れたうえで、以下の趣旨の説明文を記載して **「リクエストを送信」** を完了：
   > 当サイトは自社の社内向けPC資産管理システム（業務アプリ）であり、社員認証のために Google Workspace の正規の OAuth 2.0 ログイン（NextAuth.js GoogleProvider）を使用しています。フィッシングや不正なコンテンツは一切存在せず、誤検知であるため警告の解除をお願いいたします。
4. 「審査がリクエストされました」の受付完了を確認。

### Step 5: Google セキュリティ審査の通過・赤画面警告の解除完了
1. Google Search Console Team より「審査が問題なく完了しました（有害なサイトやダウンロードへのリンクが含まれていないことを確認できました。サイトのユーザーに対して表示されていた警告は削除させていただきます）」の通知メールを受領。
2. Google セーフ ブラウジングの誤検知警告（赤画面）の解除が正式に承認され、本対応（Issue #29）はすべて完了（※確認用ファイル `frontend/public/google6f17d6e6785211dc.html` は所有権維持のため引き続き配置しておく）。
