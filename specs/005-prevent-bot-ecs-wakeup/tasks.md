# Tasks: ボットアクセスによる不要起動防止と自動停止の確実化

**Input**: Design documents from `/specs/005-prevent-bot-ecs-wakeup/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/api.md`, `quickstart.md`)  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`  
**Tests**: 仕様書（spec.md）の受け入れ基準および `quickstart.md` の検証ガイドに基づき、ユニットテストタスクを含めて定義。  
**Organization**: ユーザーストーリー単位でフェーズ分割し、各ストーリーが独立して実装・テスト可能な構成とする。

---

## Format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

- **[P]**: 並行実行可能（異なるファイル、未完了タスクへの依存なし）
- **[Story]**: 対象ユーザーストーリー（US1, US2, US3）
- 説明には対象ファイルの具体的なパスを必ず明記

---

## Phase 1: Setup (共通準備)

**Purpose**: 実装着手前の環境確認およびベースライン検証

- [x] T001 現行のプロキシルーティング（`@app.api_route("/{path:path}")`）と状態管理コード（`record_request_accepted`, `_claim_start`, `check_and_auto_sleep`）の実装内容を読み込み、今回の修正対象箇所をコメントで明記する (File: `backend/lambda/src/main.py`, `backend/lambda/src/services/ecs_manager.py`, DependsOn: None)
- [x] T002 [P] テスト実行環境およびモック構成を確認し、`unittest.mock` と `botocore.stub` のセットアップが `conftest.py` および各テストに揃っていることを検証する (File: `backend/lambda/tests/conftest.py`, DependsOn: None)

---

## Phase 2: Foundational (共通基盤・前提条件)

**Purpose**: ユーザーストーリーの実装に先立つ共通設定の確認

**⚠️ CRITICAL**: ユーザーストーリーの実装前に本フェーズの整合性を確認すること

- [x] T003 `record_request_accepted` および `_claim_start` の DynamoDB UpdateExpression に `lastActivityAt` フィールドを追加できることを確認し、既存の `lastAcceptedAt`・`inFlightCount` 等の属性と型衝突が発生しないことをコードで検証する (File: `backend/lambda/src/services/ecs_manager.py`, DependsOn: T001, T002)

**Checkpoint**: 共通基盤確認完了。ユーザーストーリーの実装へ移行可能。

---

## Phase 3: User Story 1 - 非業務パスアクセス時の不要起動防止 (Priority: P1) 🎯 MVP

**Goal**: `/robots.txt`、`/favicon.ico` などの非業務パスに対するアクセスをルーティングゲート層で即座に 404 Not Found として遮断し、ECS 起動処理が一切呼び出されないようにする。

**Independent Test**: `backend/lambda/tests/test_lambda_ecs_proxy.py` を実行し、`/robots.txt` や `/favicon.ico` へのアクセス時に 404 が返り、`ecs_manager.ensure_ecs_running` が一度も呼ばれないことを確認する。

### Tests for User Story 1

- [x] T004 [P] [US1] 非業務パス（`/robots.txt`, `/favicon.ico`, `/sitemap.xml` 等）への単発・連続アクセス時に 404 が返り ECS 起動処理が呼び出されないことを検証するテストを追加する（※T012 と同一ファイルへの書き込みになるため、T012 より先に実施すること） (File: `backend/lambda/tests/test_lambda_ecs_proxy.py`, DependsOn: T003)

### Implementation for User Story 1

- [x] T005 [US1] ECS リバースプロキシのデコレータを `@app.api_route("/{path:path}", ...)` から `@app.api_route("/api/{path:path}", ...)` に変更し、非 `/api/*` パスを即座に 404 遮断するよう修正する (File: `backend/lambda/src/main.py`, DependsOn: T004)
- [x] T006 [US1] プロキシ転送先 URL を `http://{public_ip}:80/api/{path}{query_string}`、内部署名対象パスを `f"/api/{path}{query_string}"` に整合させるよう `proxy_to_ecs` を修正する (File: `backend/lambda/src/main.py`, DependsOn: T005)

**Checkpoint**: User Story 1 の実装完了。非業務パスへのアクセスが 404 で遮断され、ECS が不要起動しないことを独立して検証可能。

---

## Phase 4: User Story 2 - クライアント早期離脱・単発アクセス時の確実な自動停止 (Priority: P1) 🎯 MVP

**Goal**: 初回アクセスで起動要求（503）を受け付けた後、クライアントが離脱して後続要求が 0 件のままであっても、起動要求時刻から 2 時間経過後に定期アイドル監視パトロールで確実に ECS をスリープ状態（タスク数 0）へ自動停止させる。

**Independent Test**: `backend/lambda/tests/test_lambda_activity_tracking.py` および `backend/lambda/tests/test_ecs_manager.py` を実行し、起動要求時の `lastActivityAt` 初期化と、`STARTING` 状態タスクの 2 時間アイドル後自動停止を確認する。

### Tests for User Story 2

- [x] T007 [P] [US2] 起動要求受付（`record_request_accepted` / `_claim_start`）時に `lastActivityAt` が現在時刻（ISO8601）で初期化されることを検証するテストを追加する (File: `backend/lambda/tests/test_lambda_activity_tracking.py`, DependsOn: T003)
- [x] T008 [P] [US2] `runtimeState="STARTING"` のまま後続リクエストが 0 件で 2 時間経過した孤立タスクが安全に自動停止（`STOPPING` -> `STOPPED`）されること、および `lastActivityAt` 欠落時のフォールバック評価を検証するテストを追加する (File: `backend/lambda/tests/test_ecs_manager.py`, DependsOn: T003)

### Implementation for User Story 2

- [x] T009 [US2] `record_request_accepted` および `_claim_start` の DynamoDB 更新式に `lastActivityAt=if_not_exists(lastActivityAt, :now)` を追加し、起動受付時に現在時刻を記録するよう修正する (File: `backend/lambda/src/services/ecs_manager.py`, DependsOn: T007, T008)
- [x] T010 [US2] `check_and_auto_sleep` において、`lastActivityAt` が未設定または読み取れない場合のフォールバック値として `startRequestedAt`（第1候補）→ `lastAcceptedAt`（第2候補）の優先順位で評価し、両方欠落時は `invalid_runtime_activity` として既存の安全装置（フェイルオープン）に委ねるロジックを実装する (File: `backend/lambda/src/services/ecs_manager.py`, DependsOn: T009)
- [x] T011 [US2] `check_and_auto_sleep` の停止判定および DynamoDB 条件式において、`runtimeState="STARTING"` かつ起動ロック期限経過（`startLockExpiresAt <= nowEpoch`）かつ `inFlightCount == 0` の孤立タスクを停止対象として扱えるよう修正する (File: `backend/lambda/src/services/ecs_manager.py`, DependsOn: T010)

**Checkpoint**: User Story 2 の実装完了。単発アクセス後に通信が途絶えても、2 時間アイドル後に 100% 自動停止することを独立して検証可能。

---

## Phase 5: User Story 3 - 正規業務API利用時の既存オンデマンド起動とスリープ運用の維持 (Priority: P2)

**Goal**: 正規の業務 API（`/api/pcs` 等）に対するオンデマンド自動起動（503 Retry-After）、稼働中の透過プロキシ転送（200）、および通常業務終了後の 2 時間自動停止が既存仕様どおり正常に動作することを保証する。

**Independent Test**: `backend/lambda/tests/test_lambda_ecs_proxy.py` を実行し、正規 API パスに対する初回 503、稼働時プロキシ転送、および正常業務完了時の `lastActivityAt` 更新を検証する。

### Tests & Implementation for User Story 3

- [x] T012 [US3] 正規業務 API（`/api/pcs`）に対する初回 503 応答（`Retry-After: 15` 付与）および起動後プロキシ転送の動作を検証するテストを追加・拡充する (File: `backend/lambda/tests/test_lambda_ecs_proxy.py`, DependsOn: T004, T005, T006)
- [x] T013 [US3] `finish_in_flight(succeeded=True)` が `lastActivityAt` を最新時刻に更新していること、および停止処理中の新規正規 API 受付時の再起動優先（FR-006）が `check_and_auto_sleep` のアイドル判定と整合していることを確認・必要に応じ修正する (File: `backend/lambda/src/services/ecs_manager.py`, DependsOn: T011, T012)

**Checkpoint**: 全ユーザーストーリーの実装が完了し、正規 API の利便性を維持しながらボット・放置タスクの課金が完全に防止される。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 監査ログ確認、全体結合の検証、リグレッション確認、品質チェック

- [x] T014 [P] `backend/lambda/tests/` 配下の全テストを実行し、既存機能への悪影響がないことを検証する（SC-003: 正規 API の応答成功率・可用性が既存テストの全 pass により保証されることを確認する） (File: `backend/lambda/tests/test_lambda_ecs_proxy.py`, `backend/lambda/tests/test_lambda_activity_tracking.py`, `backend/lambda/tests/test_ecs_manager.py`, DependsOn: T012, T013)
- [x] T015 `specs/005-prevent-bot-ecs-wakeup/quickstart.md` の検証ガイドに基づき、全シナリオの動作とログ出力の一致を確認する (File: `specs/005-prevent-bot-ecs-wakeup/quickstart.md`, DependsOn: T014)
- [x] T016 `record_request_accepted`、`_claim_start`、および `check_and_auto_sleep` の修正コードにおいて、`_log_audit` による監査ログが起動要求受付時・`lastActivityAt` 初期化時・自動停止判定時に出力されることを確認し、欠落がある場合は `_log_audit` 呼び出しを追加する（FR-007 対応） (File: `backend/lambda/src/services/ecs_manager.py`, DependsOn: T011, T015)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup (T001, T002)
    │
    ▼
Phase 2: Foundational (T003)
    │
    ├─────────────────────────────┐
    ▼                             ▼
Phase 3: User Story 1 (P1)   Phase 4: User Story 2 (P1)
  (T004 -> T005 -> T006)       (T007, T008 -> T009 -> T010 -> T011)
    │                             │
    └──────────────┬──────────────┘
                   ▼
             Phase 5: User Story 3 (P2)
               (T012 -> T013)
                   │
                   ▼
             Phase 6: Polish
               (T014 -> T015 -> T016)
```

- **Setup (Phase 1)**: 依存関係なし。即時開始可能。
- **Foundational (Phase 2)**: Phase 1 完了後に実施。全ユーザーストーリーをブロック。
- **User Story 1 (Phase 3)**: Phase 2 完了後に着手可能。`backend/lambda/src/main.py` を修正。
- **User Story 2 (Phase 4)**: Phase 2 完了後に着手可能。`backend/lambda/src/services/ecs_manager.py` を修正（US1 と異なるファイルのため並行作業可能）。
- **User Story 3 (Phase 5)**: Phase 3 および Phase 4 完了後に結合整合性を確認。
- **Polish (Phase 6)**: 全ユーザーストーリー完了後に実行。全テスト実行（T014）、クイックスタート検証（T015）、FR-007 監査ログ確認・補強（T016）を実施。

### User Story Dependencies

- **User Story 1 (P1)**: 他のストーリーへの依存なし。ルーティングゲート層の 404 遮断のみを完結。
- **User Story 2 (P1)**: 他のストーリーへの依存なし。バックエンド ECSManager の状態管理ロジックのみを完結。
- **User Story 3 (P2)**: US1（ルーティング）と US2（状態管理）の既存動作が損なわれていないことを検証。

### Parallel Opportunities

- **Phase 1**: `T002`（テスト環境確認）は `T001` と別ファイルのため並行実行可能。
- **Phase 3 (US1)** と **Phase 4 (US2)** は修正対象ファイルが完全に分離しているため（`main.py` vs `ecs_manager.py`）、テスト作成・実装ともに並行実行可能。
- テスト作成タスク `T004` (`test_lambda_ecs_proxy.py`)、`T007` (`test_lambda_activity_tracking.py`)、`T008` (`test_ecs_manager.py`) はすべて対象ファイルが異なるため、`[P]` マーク付きで実装前に並行作成可能。

---

## Parallel Example: User Stories 1 & 2

```bash
# Developer / Branch A (User Story 1 - ルーティング遮断):
T004: tests/test_lambda_ecs_proxy.py に非業務パス遮断テスト作成（T012 より先に実施）
T005: src/main.py のルートを /api/{path:path} に変更
T006: src/main.py の proxy_to_ecs 転送パスを調整

# Developer / Branch B (User Story 2 - 状態管理・自動停止):
T007: tests/test_lambda_activity_tracking.py に lastActivityAt 初期化テスト作成
T008: tests/test_ecs_manager.py に孤立タスク自動停止テスト作成
T009: src/services/ecs_manager.py で lastActivityAt を初期化
T010: src/services/ecs_manager.py でフォールバックを実装（startRequestedAt → lastAcceptedAt の優先順位）
T011: src/services/ecs_manager.py で STARTING 停止条件を拡張
```

---

## Implementation Strategy

### MVP First (User Story 1 & User Story 2)

1. Phase 1 (Setup: T001〜T002) および Phase 2 (Foundational: T003) を完了
2. Phase 3 (User Story 1: T004〜T006 非業務パス 404 遮断) を実装・テスト
   - **この時点で検索ボットやクローラーによる不要起動が 100% 遮断される (MVP 1 達成)**
3. Phase 4 (User Story 2: T007〜T011 早期離脱・単発起動時の自動停止) を実装・テスト
   - **万一の単発起動時にも 2 時間アイドル後に 100% 自動停止する (MVP 2 達成)**
4. Phase 5 (User Story 3: T012〜T013) で正規業務 API の既存挙動が正常であることを確認
5. Phase 6 (Polish: T014〜T016) で全テストスイート実行・クイックスタート検証・FR-007 監査ログ確認を実施して完了
