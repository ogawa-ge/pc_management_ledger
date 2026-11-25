---

description: "Task list for Issue #9: AI抽出モデルの軽量モデルへの切り替え"
---

# Tasks: AI抽出モデルの軽量モデルへの切り替え

**Input**: Design documents from `/specs/issue-9-switch-gemini-flash-lite/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md（contracts/ はなし。API の入出力は [002-ai-pc-info-extraction/contracts/api.md](../002-ai-pc-info-extraction/contracts/api.md) から変更しない）

**Tests**: spec では新しいテストの作成を求めていないため、テスト作成のタスクは作らない。既存のテストが通ることの確認と、[quickstart.md](./quickstart.md) の手順での確認を行う。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- Web アプリケーション構成。本機能で変更するのは `backend/ecs/src/services/gemini_service.py` のみ（[plan.md](./plan.md) Structure Decision）

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 変更前の状態を把握する

- [X] T001 変更前に `backend/ecs/tests` の既存テストを `.venv` の pytest で実行し、成功・失敗の件数を記録する（もともと失敗するテストがあれば、本機能とは無関係として区別できるようにするため）。環境変数 `GEMINI_API_KEY` を設定しない状態で実行し、Gemini API を実際に呼ぶ `backend/ecs/tests/test_gemini_api_key.py` と `backend/ecs/tests/test_gemini_direct.py` は除外する（`backend/ecs/tests/test-gemini-accuracy.py` はファイル名にハイフンを含むため pytest の既定の収集対象外）

---

## Phase 2: Foundational (Blocking Prerequisites)

本機能には、全ユーザーストーリーの前提となる基盤作業はない（データモデル・API・設定の変更なし。[data-model.md](./data-model.md) 参照）。

---

## Phase 3: User Story 1 - 本番環境でAI自動抽出が時間内に完了する (Priority: P1) 🎯 MVP

**Goal**: AI 抽出に使うモデルを `gemini-3.5-flash-lite` に切り替え、本番で通信エラーにならずに 10 秒以内に結果が反映されるようにする（FR-001, FR-003, FR-004）

**Independent Test**: 本番の PC 登録画面で、ECS が起動済みの状態で AI 抽出を 5 回続けて実行し、5 回とも通信エラーにならず 10 秒以内に反映されること（SC-001、[quickstart.md](./quickstart.md) §3）

### Implementation for User Story 1

- [X] T002 [US1] `backend/ecs/src/services/gemini_service.py` の `parse_specs` 内の API URL のモデル名を `gemini-3.6-flash` から `gemini-3.5-flash-lite` に変更する。プロンプト・リトライ・送信前の除外処理（FR-008）・戻り値の形式は変更しない（FR-004、[research.md](./research.md) Decision 4）
- [X] T003 [US1] T001 と同じ既存テストを同じ条件（`GEMINI_API_KEY` なし、同じ2ファイルを除外）で再度実行し、T001 の結果から新たな失敗が増えていないことを確認する（`backend/ecs/tests`）
- [X] T004 [US1] [quickstart.md](./quickstart.md) §2 に従い、`GEMINI_API_KEY` を環境変数で渡して `backend/ecs/src/services/gemini_service.py` の `parse_specs` をサンプル入力で実際に呼び、数秒以内に結果が返ることと、`memory`・`storage` が GB 単位・小数点第1位までの数値であることを確認する（SC-003、[data-model.md](./data-model.md) の AI抽出結果 `memory`・`storage`）。キーの入力はユーザーが行い、キーをファイルやチャットに残さない
- [ ] T005 [US1] 変更をコミットし、`main` への PR を作成する（ブランチ `issue-9-switch-gemini-flash-lite`、Refs #9）。PR のマージはチームの手順に従う
- [ ] T006 [US1] PR のマージ後、`infrastructure/stacks/ecs_stack.py` の EcsStack を再デプロイして本番の ECS に新しいコードを反映する。デプロイの実施者・方法（CDK を誰が実行するか、`--exclusively` で EcsStack のみにするか）は、実施前にユーザーに確認する
- [ ] T007 [US1] [quickstart.md](./quickstart.md) §3 に従い本番で AI 抽出を 5 回続けて実行し、通信エラーにならず 10 秒以内に反映されることを確認する。あわせて Lambda のログ（`/aws/lambda/LambdaStack-ApiLambda...`）に `POST /api/pcs/parse-specs 502` が出ていないことを確認する（SC-001）

**Checkpoint**: 本番で AI 抽出が使える状態になる（MVP）

---

## Phase 4: User Story 2 - 抽出結果の品質が切り替え前と同等である (Priority: P2)

**Goal**: 切り替え後も 8 項目すべてが抽出され、内容が元データと矛盾しないことを確かめる（FR-002）

**Independent Test**: 同一のサンプル入力で抽出し、全 8 項目が入っていること、CPU・OS・メーカー・モデル・GPU・PC 名が元データと矛盾しないこと（SC-002）

### Implementation for User Story 2

- [ ] T008 [US2] T004 の抽出結果（ローカル）と T007 の抽出結果（本番、実機の PowerShell の出力）について、[data-model.md](./data-model.md) の AI抽出結果の 8 項目（`cpu`, `memory`, `storage`, `os`, `manufacturer`, `model`, `gpu`, `pcName`）がすべて入っており、`cpu`・`os`・`manufacturer`・`model`・`gpu`・`pcName` が元データと矛盾しないことを確認する。GB 値の換算方法（1000単位か1024単位か）の違いは問題としない（[research.md](./research.md) Decision 3）

**Checkpoint**: User Story 1 と 2 の両方が確認済みになる

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: 記録と後片付け

- [ ] T009 確認結果（T001・T003 のテスト結果、T004・T007 の応答時間と抽出結果）を `specs/issue-9-switch-gemini-flash-lite/quickstart.md` の末尾に記録し、`specs/issue-9-switch-gemini-flash-lite/spec.md` の Status を `Completed` に更新する
- [ ] T010 すべての確認が終わったら、ユーザーの確認を得たうえで GitHub Issue #9 をクローズする（`specs/002-ai-pc-info-extraction/spec.md` の Status を更新するかどうかもユーザーに確認する）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: すぐに開始できる
- **Foundational (Phase 2)**: 作業なし
- **User Story 1 (Phase 3)**: T001 の完了後。T002 → T003 → T004 → T005 → T006 → T007 の順に進める（T006 は PR のマージが前提、T007 は再デプロイが前提）
- **User Story 2 (Phase 4)**: T004 と T007 の結果を使うため、それらの完了後
- **Polish (Phase 5)**: すべての確認の完了後

### User Story Dependencies

- **User Story 1 (P1)**: 他のストーリーに依存しない
- **User Story 2 (P2)**: User Story 1 の確認結果（T004, T007）を使って評価する

### Parallel Opportunities

- 変更するファイルが 1 つだけで、各タスクが前のタスクの結果に依存するため、並行して進められるタスクはない

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 で変更前のテスト結果を記録する
2. T002 でモデル名を変更し、T003・T004 でローカルの確認をする
3. T005〜T007 で PR・デプロイ・本番確認を行う
4. **STOP and VALIDATE**: 本番で 5 回続けて成功すれば MVP 完了

### Incremental Delivery

1. User Story 1 → 本番で AI 抽出が使える状態にする（MVP）
2. User Story 2 → 抽出結果の品質を確認する
3. Polish → 記録を残し、Issue #9 をクローズする

---

## Notes

- 本機能の範囲外（[research.md](./research.md) Decision 4）: Lambda の待ち時間の上限の変更、ECS のリトライ設計の見直し、非同期化、モデル名の設定化、`backend/ecs/tests/test_gemini_direct.py` の古いモデル名（`gemini-pro`）の修正
- 本番の AWS 操作（T006, T007）は、プロファイル `pcledger-new-mfa` を使う。一時認証情報の期限が切れている場合は、ユーザーに作り直してもらう
