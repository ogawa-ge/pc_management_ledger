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
