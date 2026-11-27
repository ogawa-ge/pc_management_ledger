---
description: "Task list for Issue #33: PC一覧の表示不整合修正およびPC詳細画面の実装"
---

# Tasks: PC一覧の表示不整合修正およびPC詳細画面の実装

**Input**: Design documents from `specs/33-fix-pc-list-and-detail/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: バックエンド API の挙動変更・新設（`GET /api/pcs`, `GET /api/pcs/{pc_id}`）を担保するため、pytest テストタスクを含めています。

**Organization**: ユーザーストーリー単位（US1 → US2 → US3）に整理し、各ストーリーを独立して実装・検証できる構成としています。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列実行可能（対象ファイルが異なり、未完了タスクへの依存がない）
- **[Story]**: 対象のユーザーストーリー（`[US1]`, `[US2]`, `[US3]`）
- すべてのタスクに正確なファイルパスを明記する

---

## Phase 1: Setup（事前確認）

**Purpose**: 実装開始前に既存コードとテストのベースラインを確認する

- [X] T001 `backend/ecs/tests/` で既存 `pytest` を実行し、作業開始前のベースラインが通ることを確認する

---

## Phase 2: Foundational（全ストーリー共通の基盤整備）

**Purpose**: US1〜US3 のすべてが依存するモデル・型定義・表示フォーマットユーティリティを整備する

**⚠️ CRITICAL**: ユーザーストーリーの実装開始前に本フェーズを完了すること

- [X] T002 `backend/ecs/src/models/pc.py` の `Pc` モデルに `owner_name: Optional[str] = None` を追加し、`owner_id` を `Optional[str] = None` に変更する（`data-model.md` の `PC.ownerName`, `PC.ownerId` に準拠）
- [X] T003 [P] `frontend/src/types/pc.ts` の `PC` インターフェースに `pcName?: string | null`・`gpu?: string | null` を追加し、`ownerId`・`ownerName`・`model` の型を `data-model.md` の `PC.ownerId`, `PC.ownerName`, `PC.model`, `PC.pcName`, `PC.gpu` に合わせて整合させる（誤用の `modelName` を削除）
- [X] T004 [P] `frontend/src/lib/utils.ts` に未設定・空文字・`Unknown` を `"-"` へ正規化する `formatSpecValue` と、`Notebook`/`Desktop` を日本語表記へ変換する `getPcTypeDisplay` を追加する（`data-model.md` の `PC.type` および 2.2 表示値正規化ルールに準拠）

**Checkpoint**: 基盤モデル・型・ユーティリティが整い、US1〜US3 の実装を開始できる状態になる

---

## Phase 3: User Story 1 - PC一覧でのオーナー名と機種情報の正確な確認 (Priority: P1) 🎯 MVP

**Goal**: 全PC一覧画面でオーナー氏名とモデル名が正しく表示され、PC新規登録時にモデル名が必須入力として検証されるようにする

**Independent Test**: 新規 PC 登録画面でモデル名未入力がブロックされること、およびモデル名を入力して登録した PC が `/pcs` 一覧の「ユーザー」列（オーナー氏名）と「モデル名」列（登録値）に正しく表示されることを確認する

### Implementation for User Story 1

- [X] T005 [US1] `backend/ecs/src/main.py` に `Users` テーブルから `ownerId` に対応する表示名を解決するヘルパーを追加し、`GET /api/pcs` で `Depends(get_user_repository)` の `get_all_users()` による一括マップ解決および `os.getenv("PCS_TABLE_NAME", "PCs")` の参照（N+1 回避、`ownerId` 不在時または `PC.status != "InUse"` 時は `None`・`PC.status == "InUse"` かつユーザー未発見時は `"不明なユーザー"`）を実装する（`data-model.md` の `PC.ownerName`, `PC.ownerId`, `PC.status`, `User.userId`, `User.name`, `User.email` および `contracts/api.md` §1 に準拠）
- [X] T006 [P] [US1] `frontend/src/app/pcs/page.tsx` の一覧テーブル「モデル名」列を `pc.modelName` から `formatSpecValue(pc.model)` へ修正し、既存 5 列構成とオーナー名表示（`pc.ownerName || '未割り当て'`）を整備する（`data-model.md` の `PC.model`, `PC.ownerName` に準拠）
- [X] T007 [P] [US1] `frontend/src/app/pcs/register/page.tsx` のモデル名入力欄を画面上の必須項目化し（必須ラベル・`required` 属性・送信時の `model.trim()` 検証でブロックしエラー表示、AI 抽出で取得できなかった場合も手入力を促す）、従来の非ブロッキング警告を必須エラーへ置き換える（`data-model.md` の `PC.model` および 2.1 に準拠）
- [X] T008 [US1] `backend/ecs/tests/test_pc_list_and_detail_api.py` を新規作成し、`GET /api/pcs` の `ownerName` 解決（`InUse` 正常・`ownerId` 未割り当て・非 `InUse`（`Unused` / `PendingDisposal` / `Disposed`）PC の `None` 扱い・不明ユーザーフォールバック）を検証するテストを追加する

**Checkpoint**: US1 単独でテスト・動作確認が可能（MVP 達成）

---

## Phase 4: User Story 2 - PC詳細画面での基本情報・スペック情報の閲覧 (Priority: P1)

**Goal**: 全PC一覧・未使用PC一覧の「詳細」リンクから 404 エラーなく PC 詳細画面を開き、全基本情報・スペック情報・存在しない ID 時の案内・ECS 起動待機表示を確認できるようにする

**Independent Test**: `/pcs` および `/pcs/unused` の「詳細」リンクから `/pcs/{pcId}` を開いて全スペック情報が表示されること、一覧へ戻れること、および存在しない管理番号 `/pcs/N-999999` で専用 Not Found 表示が出ることを確認する

### Implementation for User Story 2

- [X] T009 [US2] `backend/ecs/src/main.py` に単一 PC 取得エンドポイント `GET /api/pcs/{pc_id}`（`response_model=Pc`）を追加し、`os.getenv("PCS_TABLE_NAME", "PCs")` から `pcId` で取得・`Depends(get_user_repository)` で `ownerName` を解決（`PC.status != "InUse"` 時は `None`）・未存在時は `404 Not Found` を返すよう実装する（`data-model.md` の `PC.pcId`, `PC.ownerName`, `PC.ownerId`, `PC.status` および `contracts/api.md` §2 に準拠）
- [X] T010 [P] [US2] `frontend/src/services/pc-api.ts` に `requestWithRetry` 経由で `GET /api/pcs/{pcId}` を呼び出す `getPCById` 関数を追加する（`contracts/api.md` §2 に準拠）
- [X] T011 [US2] `frontend/src/app/pcs/[pcId]/page.tsx` を新規作成し（Next.js 16 対応のため `useParams` で `pcId` を取得）、未ログイン時 `/login` リダイレクト、`getPCById` 呼び出しと `ECSLoadingState` 連携、404 専用 Not Found 表示、その他エラー時の再試行ボタン、全基本情報・スペック項目表示（`formatSpecValue`・`getPcTypeDisplay`・`getStatusDisplay`・`getStatusColor` 適用）、および「PC一覧に戻る」導線を実装する（`data-model.md` の `PC.pcId`, `PC.ownerName`, `PC.type`, `PC.status`, `PC.pcName`, `PC.manufacturer`, `PC.model`, `PC.cpu`, `PC.memory`, `PC.storage`, `PC.os`, `PC.gpu`, `PC.serialNumber`, `PC.createdAt`, `PC.updatedAt` に準拠）
- [X] T012 [US2] `backend/ecs/tests/test_pc_list_and_detail_api.py` に `GET /api/pcs/{pc_id}` の正常取得（200・`InUse` の `ownerName` 解決・非 `InUse` 時の `None`・不明ユーザーフォールバック）および存在しない `pc_id` 時の 404 応答テストを追加する

**Checkpoint**: US1・US2 ともに独立して動作・検証できる状態になる

---

## Phase 5: User Story 3 - PC詳細画面からの返却手続きおよび管理者向けステータス管理 (Priority: P2)

**Goal**: PC 詳細画面から条件を満たす利用中 PC の返却手続き画面へ遷移して認証エラーなく返却を完了でき、管理者は詳細画面上からステータスを更新して即時反映できるようにする

**Independent Test**: 一般ユーザー自身の利用中 PC 詳細にのみ「返却手続き」ボタンが表示され返却送信まで完了できること（他人 PC や未使用 PC では非表示）、および管理者のみステータス変更フォームが表示され更新結果が画面と一覧に反映されることを確認する

### Implementation for User Story 3

- [X] T013 [P] [US3] `frontend/src/services/pc-api.ts` に `requestWithRetry` 経由で `PATCH /api/pcs/{pcId}/status` を呼び出す `updatePCStatus` 関数（`Authorization: Bearer <userId>` ヘッダー付与）を追加し、あわせて既存の `returnPC` 関数にも `Authorization: Bearer ${returnData.userId}` ヘッダーを付与して返却時の 401 エラーを解消する（`contracts/api.md` §3, §4 に準拠）
- [X] T014 [US3] `frontend/src/app/pcs/[pcId]/page.tsx` に、返却手続き画面（`/pcs/${pc.pcId}/return`）への遷移ボタン（`PC.status === 'InUse'` かつオーナー本人または `User.role === 'Admin'` の場合のみ表示）と、管理者専用ステータス更新セクション（`User.role === 'Admin'` の場合のみ表示、`InUse`/`Unused`/`PendingDisposal`/`Disposed` 選択・現在と同一ステータス時は更新ボタン無効化・任意理由入力・更新成功後の再取得または最新 state 反映・エラー表示）を追加する（`data-model.md` の `PC.status`, `User.role` および 3.1/3.2 に準拠）

**Checkpoint**: US1・US2・US3 の全機能が完了し、それぞれ独立検証できる状態になる

---

## Phase 6: Polish & Cross-Cutting Concerns（最終検証・仕上げ）

**Purpose**: 全体の自動テスト・型チェック・ビルド・スコープ外変更がないことを最終検証する

- [X] T015 `backend/ecs/` で `pytest` を実行し、`backend/ecs/tests/test_pc_list_and_detail_api.py` および既存テスト全件（`test_naming_convention.py` 等を含む）がパスすることを確認する
- [X] T016 `frontend/` で `npx tsc --noEmit` および `npm run build` を実行し、TypeScript 型エラーおよびビルドエラーがないことを確認する（※ローカルに `frontend/node_modules` 未導入のため、AWS Amplify の自動ビルド（`next build`）成功および本番実機検証にて完了確認）
- [X] T017 `specs/33-fix-pc-list-and-detail/quickstart.md` の検証項目および `git diff --stat` を確認し、Issue #33 のスコープ外ファイルに変更がないことを確認する

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 依存なし — 即時開始可能
- **Phase 2 (Foundational)**: Phase 1 完了後に開始 — US1〜US3 すべての前提
- **Phase 3 (US1 - P1)** & **Phase 4 (US2 - P1)**: いずれも Phase 2 完了後に開始可能（`backend/ecs/src/main.py` の編集箇所のみ順序調整）
- **Phase 5 (US3 - P2)**: Phase 4 の `T011`（`frontend/src/app/pcs/[pcId]/page.tsx` 作成）完了後に `T014` を実施（`T013` は並列実行可能）
- **Phase 6 (Polish)**: Phase 3〜5 完了後に実施

### Parallel Opportunities

- **Phase 2**: `T002`（backend）、`T003`（frontend types）、`T004`（frontend utils）は別ファイルのため並列実行可能
- **Phase 3 (US1)**: `T005`（backend `main.py`）と、`T006`（一覧ページ）・`T007`（登録ページ）は並列実行可能
- **Phase 4 (US2)**: `T009`（backend `main.py`）と `T010`（frontend `pc-api.ts`）は並列実行可能
- **Phase 5 (US3)**: `T013`（`pc-api.ts`）は Phase 4 と並行して先に実装可能

---

## Parallel Example: Phase 2 & User Story 1

```text
# Phase 2 を並列実行:
- T002: backend/ecs/src/models/pc.py
- T003: frontend/src/types/pc.ts
- T004: frontend/src/lib/utils.ts

# User Story 1 でバックエンドとフロントエンドを並列実行:
- T005: backend/ecs/src/main.py
- T006: frontend/src/app/pcs/page.tsx
- T007: frontend/src/app/pcs/register/page.tsx
```

---

## Implementation Strategy

### MVP First（User Story 1 優先）

1. Phase 1 + Phase 2 を完了して共通基盤を整える
2. Phase 3（US1）を完了し、PC 一覧のユーザー名・モデル名表示とモデル名必須登録を検証する
3. Phase 4（US2）を完了し、PC 詳細画面の 404 解消とスペック閲覧を検証する
4. Phase 5（US3）を完了し、返却導線と管理者向けステータス更新を検証する
5. Phase 6 で全体の pytest・型チェック・build・差分チェックを完了する
