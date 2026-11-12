# Tasks: Google Search Console 所有権確認対応（セーフブラウジング誤検知対策）

**Input**: Design documents from `/specs/006-google-site-verification/`

**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Organization**: 最小限のタスク構成（User Story 1 の実装とビルド検証）に集約。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列実行可能（異なるファイル、依存関係なし）
- **[Story]**: 対応するユーザーストーリー（`[US1]`）

---

## Phase 1: Setup & Foundational

※新規パッケージ導入やDB変更は不要なため、Phase 1 / Phase 2 の事前作業はなし。直ちに Phase 3（User Story 1）を実施する。

---

## Phase 3: User Story 1 - Google Search Console によるサイト所有権確認 (Priority: P1) 🎯 MVP

**Goal**: 未ログイン状態でも `/google6f17d6e6785211dc.html` がリダイレクトされずに配信され、Google Search Console の所有権確認を完了できるようにする。

**Independent Test**: 未ログイン状態で `/google6f17d6e6785211dc.html` にアクセスし、`google-site-verification: google6f17d6e6785211dc.html` が返却されること。

### Implementation for User Story 1

- [x] T001 [P] [US1] Google Search Console 所有権確認用ファイル `frontend/public/google6f17d6e6785211dc.html` を作成する（内容: `google-site-verification: google6f17d6e6785211dc.html`）
- [x] T002 [P] [US1] `frontend/src/middleware.ts` の `config.matcher` に `google.*\\.html` および `robots\\.txt` の除外設定を追加する

**Checkpoint**: `frontend/public/google6f17d6e6785211dc.html` の配置と `frontend/src/middleware.ts` の除外設定が完了していること。

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T003 `frontend/src/middleware.ts` の変更に伴うフロントエンドのビルド・型チェック（`npm run build` または `npx tsc --noEmit`）を確認する

---

## Dependencies & Execution Order

- **T001** と **T002** は異なるファイルのため並列実行可能（`[P]`）。
- **T003** は **T001**・**T002** 完了後に実行する。

## Implementation Strategy

### MVP First (User Story 1 Only)

1. `T001` および `T002` を実施する。
2. `T003` でビルドエラーがないことを確認し、デプロイ後に Google Search Console で「所有権の確認」を実行する。
