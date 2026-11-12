# Research: Google Search Console 所有権確認対応

## Decision 1: 所有権確認用ファイルの配信方式
- **Decision**: `frontend/public/google6f17d6e6785211dc.html` に `google-site-verification: google6f17d6e6785211dc.html` を配置する。
- **Rationale**: Next.js では `public/` 配下のファイルがルートパス（`/google6f17d6e6785211dc.html`）としてそのまま配信されるため、追加のルーティング実装が不要。
- **Alternatives considered**: Route Handler での動的レスポンス（静的ファイル1つのため不要）。

## Decision 2: 未認証アクセス時の `/login` リダイレクト回避
- **Decision**: `frontend/src/middleware.ts` の `config.matcher` を `['/((?!api|_next/static|_next/image|favicon.ico|google.*\\.html|robots\\.txt).*)']` に更新する。
- **Rationale**: Google Search Console の確認ボットは認証トークンを持たないため、ミドルウェア実行対象から除外することで HTTP 307 リダイレクト（`/login`）を防ぎ、直接静的ファイルを返却できる。
- **Alternatives considered**: `middleware` 関数内の条件分岐追加（`matcher` で除外する方がミドルウェア自体の呼び出しをスキップでき効率的）。
