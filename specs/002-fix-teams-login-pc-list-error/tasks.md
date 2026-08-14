# タスク一覧: Fix Teams Login PC List Fetch Error

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 既存の Next.js プロジェクト環境と依存関係の確認
- [ ] T002 `frontend/src/app/pcs/page.tsx` の現在のフェッチロジック（SWR等）の構造把握

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented
*(※本Issueは既存機能の改修であるため、基盤の大幅な変更はありません)*

- [ ] T003 `page.tsx` に利用する Tailwind CSS のスピナーアイコン（`animate-spin`）の選定・準備

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - サーバー起動待機時の自動リトライと待機画面 (Priority: P1) ⭐ MVP

**Goal**: ECSスリープ時の503エラーでクラッシュさせず、スピナーを表示して自動リトライを行う。

**Independent Test**: ECSサーバーが停止している状態（またはモックで503を返す状態）で `/pcs` にアクセスし、エラー画面ではなくローディング画面（スピナー付き）が表示され、5秒間隔の自動リトライが走ることを確認する。

### Implementation for User Story 1

- [ ] T004 [US1] `frontend/src/app/pcs/page.tsx` のフェッチ処理で HTTP 503 レスポンスをハンドリングするロジックの追加
- [ ] T005 [US1] 503エラー時にエラーをスローせず、`setTimeout` を用いた5秒間隔・最大3回のポーリング処理を実装
- [ ] T006 [US1] 自動リトライ中に表示する「サーバー起動中...」のテキストおよびスピナーUIの実装

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - 詳細で分かりやすいエラー案内と手動再試行 (Priority: P2)

**Goal**: 503以外のエラーやリトライ上限到達時に、手動再試行ボタンと分かりやすいエラーメッセージを提供する。

**Independent Test**: 意図的にネットワークを切断するか500エラーを返し、日本語のエラーメッセージと「再試行」ボタンが表示され、クリックで単発フェッチが行われることを確認する。

### Implementation for User Story 2

- [ ] T007 [US2] 503以外のエラー（500/502等）やポーリング上限到達時にエラーメッセージステートを更新する処理の実装
- [ ] T008 [US2] 未加工のエラーメッセージを隠蔽し、「PC一覧の取得に失敗しました。サーバーに一時的に接続できません。」というテキストを表示するUI実装
- [ ] T009 [US2] 単発フェッチを行う「再試行」ボタン（Tailwind適用）のUI配置および `onClick` イベントの実装

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T010 [P] モックサーバー等を利用した総合的な手動テストの実施（503から正常復帰のフロー、503から上限到達のフロー）
- [ ] T011 [P] コンポーネントのコードクリーンアップ（不要なコメントの削除等）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 と US2 は並行可能だが、US1（自動リトライ）の実装後にUS2（上限到達時の処理）を繋ぐと効率的
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2)
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - US1 のポーリングロジック（上限判定）と連携するため、US1 の実装と調整しながら進める。

### Within Each User Story

- UIコンポーネント（スピナー、ボタン）の配置前に、ロジック（ステート管理・ポーリング）の実装を優先する。
- Story complete before moving to next priority

### Parallel Opportunities

- 全ての [P] タスクは並行して実行可能。
- T006 (UI実装) と T004/T005 (ロジック実装) は担当者が分かれていれば並行可能。

---

## Parallel Example: User Story 1

```bash
# ロジックとUIを並行して実装する場合の例
Task: "503レスポンスのハンドリングとポーリングロジックの実装" (T004, T005)
Task: "スピナーと待機テキストのコンポーネント作成" (T006)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 & 2
2. Complete Phase 3: User Story 1 (自動リトライ機能)
3. **STOP and VALIDATE**: 503エラー時にリトライが機能することを確認
4. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational 完了
2. User Story 1 完了 -> テスト（自動リトライの確認）
3. User Story 2 完了 -> テスト（手動再試行ボタンの確認）
4. 両方の結合テストを実施し、Issueクローズ。

## Notes

- [P] tasks = different files, no dependencies
- [US1], [US2] = 特定のユーザーストーリーに紐づくタスク
- 他のIssue（特にIssue #11）に関連するコードには絶対に手を出さないこと。
