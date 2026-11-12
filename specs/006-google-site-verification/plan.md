# Implementation Plan: Google Search Console 所有権確認対応（セーフブラウジング誤検知対策）

**Branch**: `006-google-site-verification` | **Date**: 2026-11-12 | **Spec**: [spec.md](file:///c:/Users/hagihara/pc_management_ledger/specs/006-google-site-verification/spec.md)

**Input**: Feature specification from `/specs/006-google-site-verification/spec.md` (GitHub Issue #29)

## Summary

Google セーフ ブラウジングの誤検知（赤画面警告）解除申請に向けて、Google Search Console の所有権確認用 HTML ファイル（`frontend/public/google6f17d6e6785211dc.html`）を配置し、未ログイン状態でも確認クローラーが取得できるよう `frontend/src/middleware.ts` の認証リダイレクト対象（`config.matcher`）から `google.*\.html` および `robots.txt` を除外する。

## Technical Context

**Language/Version**: TypeScript 6.0.3 (Next.js 16.2.4)  
**Primary Dependencies**: Next.js (`next/server`), NextAuth.js (`next-auth/jwt`)（※新規追加なし）  
**Storage**: N/A（静的ファイル配信のみ、DB変更なし）  
**Testing**: `npm run build` および本番 URL に対する未認証 `curl` / Search Console 所有権確認  
**Target Platform**: AWS Amplify Hosting (Next.js App Router)  
**Project Type**: Web application (Frontend)  
**Performance Goals**: 静的ファイル配信およびミドルウェア除外によりオーバーヘッドゼロ  
**Constraints**:
- Constitution Layer 4 厳守: Issue #29 の対象（`frontend/public/google6f17d6e6785211dc.html` の追加と `frontend/src/middleware.ts` の `matcher` 更新）のみに限定し、他画面やバックエンドには一切手を触れない。  
**Scale/Scope**: フロントエンドの新規静的ファイル 1 件作成、ミドルウェア設定 1 行修正。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 憲法規定 / 原則 | 適合状況 | 判定 |
|---|---|---|
| **Layer 1: Output Language** | ドキュメント・計画・解説をすべて日本語で記述 | **PASS** |
| **Layer 1: No Hallucination** | DB・API変更なし（静的ファイル配信とミドルウェア除外のみ） | **PASS** |
| **Layer 1: Security First** | 業務画面の認証保護を維持し、公開対象の静的確認ファイルのみ除外 | **PASS** |
| **Layer 3: Code Standard** | Next.js 標準の `public/` 配置および `middleware.ts` の `matcher` 規約に準拠 | **PASS** |
| **Layer 4: Strict Scope Boundaries** | Issue #29 に必要な 2 ファイルのみの変更でコンフリクトを回避 | **PASS** |

## Project Structure

### Documentation (this feature)

```text
specs/006-google-site-verification/
├── spec.md              # 仕様書
├── checklists/
│   └── requirements.md  # 仕様品質チェックリスト
├── research.md          # Phase 0 調査メモ（簡潔版）
├── quickstart.md        # Phase 1 検証手順（簡潔版）
├── plan.md              # 本実装計画書
└── tasks.md             # Phase 2 タスクリスト (/speckit-tasks で生成)
```
※DBエンティティやAPI変更を伴わないため `data-model.md` および `contracts/` は対象外（省略）。

### Source Code (repository root)

```text
frontend/
├── public/
│   └── google6f17d6e6785211dc.html  # 【新規】Search Console 所有権確認用HTMLファイル
└── src/
    └── middleware.ts                # 【変更】matcher に google.*\.html|robots\.txt を除外追加
```

**Structure Decision**: Next.js の標準静的ファイル配信ディレクトリ `frontend/public/` に確認ファイルを配置し、`frontend/src/middleware.ts` の `config.matcher` 正規表現を1箇所更新する最小構成とする。
