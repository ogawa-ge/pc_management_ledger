# Tasks: AI PC情報取得機能

**Input**: Design documents from `/specs/002-ai-pc-info-extraction/`

**Prerequisites**: [plan.md](./plan.md)（必須）, [spec.md](./spec.md)（必須）, [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: バックエンドの抽出ロジックについてのみユニットテストタスクを含む（001-pc-managementの既存テスト運用を踏襲）。フロントエンドのテストは`quickstart.md`の手動検証で代替する。

**Organization**: タスクはユーザーストーリー単位（US1, US2）でグループ化。各ストーリーは独立して実装・検証可能。

## Path Conventions

Webアプリケーション構成（001-pc-managementと同一）: `frontend/src/`, `backend/ecs/src/`

---

## Phase 1: Setup

**Purpose**: ローカル開発環境の確認（新規プロジェクト初期化は不要）

- [ ] T001 [quickstart.md](./quickstart.md) の Prerequisites に従い、`frontend`（`npm run dev`）と `backend/ecs`（`uvicorn src.main:app --reload`）のローカル起動、および `GEMINI_API_KEY` 環境変数の設定を確認する

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: US1・US2共通で必要な、バックエンドの抽出・登録APIのスキーマ整合と信頼性向上

**⚠️ CRITICAL**: このフェーズが完了するまでUser Story 1/2の実装には着手しない

- [ ] T002 `backend/ecs/src/services/gemini_service.py` のGeminiプロンプトを修正し、`cpu, memory, storage, os, manufacturer, model` の6項目を抽出するようにする（`gpu`, `motherboard`は削除）
- [ ] T003 `backend/ecs/src/services/gemini_service.py` に、抽出対象6項目に含まれないキー（`BiosSerialNumber`等）をGemini APIへの送信前に除去するサニタイズ処理を追加する（FR-008）
- [ ] T004 `backend/ecs/src/services/gemini_service.py` にGemini API呼び出しのリトライ処理（最大3回、指数バックオフ）を追加し、3回失敗時は `{"error": "...", "retriesExhausted": true}` を返すようにする（FR-007）
- [ ] T005 `backend/ecs/src/models/pc.py` を更新する: `Pc.model` を `Optional[str] = None` に緩和し、`PcCreateRequest` を `specs_text` ではなく構造化フィールド（`cpu, memory, storage, os, manufacturer, model`）を受け取る形に変更する（[data-model.md](./data-model.md) 参照）
- [ ] T006 `backend/ecs/src/services/pc_service.py` の `create_pc()` を更新し、内部で `parse_specs()` を再実行せず、渡された構造化フィールドをそのまま `Pc` に永続化するようにする（依存: T005）
- [ ] T007 `backend/ecs/src/main.py` の `POST /api/pcs` と `POST /api/pcs/parse-specs` ハンドラを [contracts/api.md](./contracts/api.md) の定義に合わせて更新する（依存: T005, T006）
- [ ] T008 [P] `backend/ecs/tests/test-gemini-accuracy.py` に、manufacturer/model抽出、リトライ、機微データ除外のテストケースを追加する（依存: T002-T004）
- [ ] T009 [P] `docs/ubiquitous-language.md` に新用語（「貼り付け入力」「抽出リトライ」）を追加する

**Checkpoint**: バックエンドの抽出・登録APIが新しい契約（[contracts/api.md](./contracts/api.md)）で動作する状態

---

## Phase 3: User Story 1 - ターミナル出力の貼り付けとAIによる自動抽出 (Priority: P1) 🎯 MVP

**Goal**: ユーザーがターミナル実行結果を貼り付けると、Gemini APIが必要な項目のみを自動抽出し、フォームに反映する

**Independent Test**: 実際の`Get-ComputerInfo`出力（JSON）をPC登録画面に貼り付けた際に、CPU・メモリ・OSバージョン等の判別可能な項目が自動でフォームに反映されることを確認する

### Implementation for User Story 1

- [ ] T010 [US1] `frontend/src/services/pc-api.ts` の `parseSpecs()`/`registerPC()` を [contracts/api.md](./contracts/api.md) に合わせて構造化フィールドの送受信に書き換える（依存: Phase 2完了）
- [ ] T011 [P] [US1] `frontend/src/app/pcs/register/page.tsx` に「ターミナル実行結果を貼り付けてください」のラベル付き`<textarea>`（state: `terminalOutput`）を追加する
- [ ] T012 [US1] `frontend/src/app/pcs/register/page.tsx` の `handleSubmit` 内、`parseSpecs(terminalCommand)` を `parseSpecs(terminalOutput)` に修正する（依存: T010, T011）
- [ ] T013 [US1] `frontend/src/app/pcs/register/page.tsx` に `manufacturer`/`model` の入力欄を追加し、Specs定義に存在しない `gpu` 欄を削除する（依存: T011）
- [ ] T014 [US1] `frontend/src/app/pcs/register/page.tsx` で、`parseSpecs()` のレスポンスを `cpu/memory/storage/os/manufacturer/model` の各state（`setCpu`等）に反映する（依存: T012, T013）
- [ ] T015 [US1] `frontend/src/app/pcs/register/page.tsx` に、貼り付け内容の送信前JSONバリデーションを追加し、不正な場合はAPIを呼ばずエラーメッセージを表示する（FR-006, 依存: T012）
- [ ] T016 [US1] `frontend/src/app/pcs/register/page.tsx` に抽出中のローディング表示（`aria-busy`）と、`retriesExhausted`受信時のエラー表示（貼り付け内容は保持したまま）を追加する（FR-007のUI側, 依存: T014）

**Checkpoint**: User Story 1が独立して動作・検証可能（[quickstart.md](./quickstart.md) シナリオ1〜3）

---

## Phase 4: User Story 2 - 抽出結果の確認・手動修正 (Priority: P2)

**Goal**: ユーザーは自動抽出された内容を登録前に確認し、必要に応じて修正できる

**Independent Test**: 自動反映後にフォームの値（例: CPU欄）を編集し、編集後の内容で登録が完了することを確認する

### Implementation for User Story 2

- [ ] T017 [US2] `frontend/src/app/pcs/register/page.tsx` の `handleSubmit` を修正し、`parseSpecs()` の戻り値をそのまま送信するのではなく、フォームstate（編集後の値を含む）から構築したオブジェクトを `registerPC()` に渡すようにする（依存: T010, T014）
- [ ] T018 [US2] `frontend/src/app/pcs/register/page.tsx` に、送信前に必須項目（例: `model`が空欄）を警告するクライアント側バリデーションを追加する（依存: T017）

**Checkpoint**: User Story 1・2ともに独立して動作・検証可能（[quickstart.md](./quickstart.md) シナリオ1）

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: 全体検証と回帰確認

- [ ] T019 [P] [quickstart.md](./quickstart.md) のシナリオ1〜4を実機（Windows 11 / PowerShell）で実行し、結果を記録する
- [ ] T020 [P] `frontend/src/app/pcs/register/page.tsx` について、[quickstart.md](./quickstart.md) のa11yチェックリスト（label関連付け、Tab順序、`aria-live`、`aria-busy`、色以外でのエラー表現）を確認する
- [ ] T021 001-pc-managementの管理者代理登録画面（US3）が本機能の影響を受けず従来通り動作することを確認する（回帰確認、[quickstart.md](./quickstart.md) 参照）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 依存なし、即着手可能
- **Foundational (Phase 2)**: Setup完了後に着手。**US1・US2の両方をブロックする**
- **User Story 1 (Phase 3)**: Foundational完了後に着手可能。他ストーリーへの依存なし
- **User Story 2 (Phase 4)**: Foundational完了後に着手可能だが、T017がUS1のT010・T014（`pc-api.ts`書き換え、フォーム自動反映）に依存するため、**実質的にUS1のT010・T014完了後に着手するのが安全**
- **Polish (Final Phase)**: US1・US2完了後

### Within Each Phase

- Phase 2: T002→T003→T004（同一ファイル、順次）。T005→T006→T007（依存順）。T008・T009は並行可
- Phase 3: T010・T011は並行可。T012以降はT010・T011に依存し、`page.tsx`の同一ファイル内で順次進める
- Phase 4: T017→T018の順

### Parallel Opportunities

- Phase 2: T008（バックエンドテスト）とT009（ドキュメント更新）は並行実行可能
- Phase 3: T010（`pc-api.ts`）とT011（`page.tsx`へのtextarea追加）は異なるファイルのため並行実行可能
- Phase 4以降はほぼ同一ファイル（`page.tsx`）への逐次変更のため、並行実行の余地は小さい

---

## Parallel Example: Foundational

```bash
# T008とT009は異なるファイルのため並行実行可能
Task: "backend/ecs/tests/test-gemini-accuracy.py にmanufacturer/model抽出・リトライ・機微データ除外のテストケースを追加"
Task: "docs/ubiquitous-language.md に新用語を追加"
```

## Parallel Example: User Story 1（着手時）

```bash
# T010とT011は異なるファイルのため並行実行可能
Task: "frontend/src/services/pc-api.ts をcontracts/api.mdに合わせて書き換え"
Task: "frontend/src/app/pcs/register/page.tsx に貼り付け用textareaを追加"
```

---

## Implementation Strategy

### MVP First (User Story 1 のみ)

1. Phase 1: Setup 完了
2. Phase 2: Foundational 完了（**必須、ここを飛ばすとUS1が正しく動作しない**）
3. Phase 3: User Story 1 完了
4. **停止して検証**: [quickstart.md](./quickstart.md) シナリオ1〜3でUS1単独の動作を確認
5. この時点で「貼り付け→AI自動抽出→登録」の基本フローが完成し、Issue #9の主要な訴えは解消される

### Incremental Delivery

1. Setup + Foundational → 抽出・登録APIの土台が正しい状態になる
2. User Story 1 追加 → 独立検証 → MVP相当（自動抽出のみ、手動編集の反映は次段階）
3. User Story 2 追加 → 独立検証 → 手動修正が正しく登録に反映される
4. Polish（quickstart.md全シナリオ + a11y + 回帰確認）

---

## Notes

- Phase 2（Foundational）が最大のボリュームを占めるのは、Issue #9の根本原因（バックエンドのスキーマ不整合・未配線）がここに集中しているため
- `page.tsx`への変更が多いUser Story 1・2は同一ファイルへの逐次変更が中心となり、並行実行の余地は限定的
- 各タスク完了後、論理的な区切りでコミットすることを推奨（`/speckit-git-commit`）
- 各チェックポイントで [quickstart.md](./quickstart.md) の該当シナリオを確認してから次フェーズに進むこと
