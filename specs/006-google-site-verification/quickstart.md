# Quickstart: Google Search Console 所有権確認の検証手順

## 1. ビルド確認（ローカル）
```powershell
cd frontend
npm run build
```

## 2. デプロイ後の動作確認
1. ブラウザのシークレットウィンドウ（未ログイン状態）または `curl` で `/google6f17d6e6785211dc.html` にアクセスする。
2. `/login` へリダイレクトされず、`google-site-verification: google6f17d6e6785211dc.html` が表示されることを確認する。
3. Google Search Console の「所有権の確認」画面で「HTML ファイル」の「確認」ボタンをクリックし、所有権が確認されることを確認する。
