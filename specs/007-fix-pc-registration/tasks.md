# Tasks: PC新規登録時の登録失敗・画面固まり解消

**Input**: Design documents from `/specs/007-fix-pc-registration/`

**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `quickstart.md`

**Tests**: `plan.md` および Issue #30 の完了条件に基づき、CDK `EcsStack` の `Users` テーブル読み取り専用権限を検証する単体テストタスクを含む。

**Organization**: ユーザーストーリー単位（P1: US1 / P2: US2）に分割し、他画面や依存パッケージ更新・認証強化（Issue #32）へ波及しない最小構成とする。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列実行可能（異なるファイル、未完了タスクへの依存なし）
- **[Story]**: 対応するユーザーストーリー（`[US1]`, `[US2]`）
- すべてのタスクに正確なファイルパスを明記

---

## Phase 1: Setup

※新規ライブラリの導入・DBスキーマ変更・新規プロジェクト初期化は不要なため、事前作業はなし。

---

## Phase 2: Foundational（原因の実証・ブロッキング）

**Purpose**: 主原因（ECS に `Users` テーブルの読み取り権限がない）を実環境で実証してから修正に着手する。**実証できない場合は実装を止めて再分析する。**

- [x] T000 AWS 上で読み取り専用の原因確認を行い、結果（機密情報はマスク）を `specs/007-fix-pc-registration/research.md` の Decision 3 配下に追記する（手順は `specs/007-fix-pc-registration/quickstart.md` §0。MFA セッションが必要）。確認項目: ①ECS タスクロールのポリシーに `Users` テーブルがないこと、②ECS ロググループに `Users` テーブル参照エンドポイントの HTTP 503 が記録されていること

**Checkpoint**: 主原因が実証され、Phase 3 以降に進める状態。

---

## Phase 3: User Story 1 - 一般ユーザーおよび管理者によるPC新規登録の完了 (Priority: P1) 🎯 MVP

**Goal**: ECS タスクロールに DynamoDB `Users` テーブルの読み取り専用権限（最小権限）を付与し、PC新規登録（`POST /api/pcs`）およびオーナー候補・利用可能なユーザー参照時の `AccessDeniedException`（HTTP 503）を解消する。

**Independent Test**: CDK 単体テスト（`infrastructure/tests/unit/test_infrastructure_stack.py`）で `EcsStack` タスクロールに `Users` テーブルの読み取り専用権限のみが付与されていることを検証でき、`cdk deploy EcsStack` 後に一般ユーザー（および管理者アカウントがある場合は管理者）で `/pcs/register` から PC 登録が完了すること。

### Implementation & Tests for User Story 1

- [x] T001 [US1] `infrastructure/stacks/ecs_stack.py` の `EcsStack.__init__` に `users_table=None` 引数を追加し、`users_table.grant_read_data(task_definition.task_role)` による読み取り専用権限付与を実装する（ECS 側コードはテーブル名を直書きしているため環境変数 `USERS_TABLE_NAME` は追加しない）（`T000` 完了後）
- [x] T002 [P] [US1] `infrastructure/app.py` の `EcsStack` 生成引数に `users_table=database_stack.users_table` を追加する（`T001` 完了後）
- [x] T003 [P] [US1] `infrastructure/tests/unit/test_infrastructure_stack.py` に、`EcsStack` のタスクロールへ `Users` テーブルの読み取り権限（`dynamodb:GetItem` / `Scan` 等）が付与され書き込み権限（`dynamodb:PutItem` / `UpdateItem` / `DeleteItem`）が付与されていないことを検証する単体テストを追加する（`T001` 完了後）

**Checkpoint**: `EcsStack` への `Users` テーブル読み取り専用権限付与と CDK 単体テストが完了し、User Story 1 が独立して検証可能な状態。

---

## Phase 4: User Story 2 - 管理者向けオーナー候補一覧のコールドスタート対応と登録エラーの明確な表示 (Priority: P2)

**Goal**: 管理者ログイン時のオーナー候補一覧取得（`GET /api/users`）でコールドスタート（HTTP 503 `starting`）を自動リトライ待機できるようにし、登録失敗時・タイムアウト時に ECS起動待機表示を確実に解除したうえで「PCを登録」ボタン直上へ視認しやすい日本語のエラーメッセージを表示する。

**Independent Test**: `getUsers` が 503 `starting` 応答時に自動待機リトライを実行し ECS起動待機表示に反映されること、エラー／タイムアウト時に ECS起動待機表示が閉じられること、およびスクロール不要で「PCを登録」ボタン付近に赤字の日本語エラーメッセージが表示されること（英語の生メッセージが出ないこと）。

### Implementation for User Story 2

- [x] T004 [P] [US2] `frontend/src/services/pc-api.ts` の `getUsers` に `options: RetryOptions = {}` 引数を追加し、`fetch` 直呼び出しから `requestWithRetry<User[]>` 経由へ変更してコールドスタート（HTTP 503 `starting`）に対応する（`T000` 完了後）
- [x] T005 [US2] `frontend/src/app/pcs/register/page.tsx` を更新し、①`fetchUsers` から `getUsers` へ `onRetryStateChange` を渡して ECS起動待機表示（`ECSLoadingState`）と連動させ、②`fetchUsers` および `handleSubmit` の `catch` 内で `ecsLoading.setIsLoading(false)` を明示呼び出ししてエラー／タイムアウト時の表示残存を防ぎ、③`registrationError` を「PCを登録」ボタンの直上にも Tailwind 未導入環境で視認しやすいスタイル（`style={{ color: '#dc2626', fontWeight: 600 }}` 等）付きで表示し、④エラー文言を `error.message` の生表示ではなく `specs/007-fix-pc-registration/research.md` Decision 2-4 のステータス別日本語メッセージ（401/403、`start_timeout`、500 以上、その他・通信断。既存の 404 専用処理は維持）に変換する（`T004` 完了後）

**Checkpoint**: User Story 1（インフラ権限修正）と User Story 2（フロントエンド待機リトライ・待機表示解除・日本語エラー表示）の両方が完了した状態。

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: 変更全体のテスト検証、デプロイ、実機確認とスコープ遵守チェック

- [x] T006 [P] `.venv` に `pytest` が未導入の場合は `infrastructure/requirements-dev.txt` を導入したうえで、`.\.venv\Scripts\pytest.exe infrastructure/tests/unit/` を実行し、既存テストを含め全件パスすることを確認する（※`test_infrastructure_stack.py` 3件・`test_ecs_cost_optimization.py` 3件・`test_internal_proxy_signing_generation_rejects_unknown_selector` 1件の計7件は PASS。`LambdaStack` の `PythonFunction` ビルドを伴う残り6件はローカル Docker 未稼働・環境制約により `docker exited with status 125` で失敗）
- [x] T007 [P] `frontend/` の変更差分・型整合性（ローカルに `frontend/node_modules` がある場合は `npm run build`、未導入の場合は構文・型検証およびデプロイ時の Amplify ビルド確認）および `git diff` を確認し、Issue #30（`specs/007-fix-pc-registration/plan.md`）のスコープ外の変更（他画面や Issue #32 対象の依存パッケージ更新・認証強化など）が混入していないことを検証する
- [x] T009 [US1] `backend/ecs/src/main.py` の `verify_internal_proxy_request` を `@app.middleware("http")`（`BaseHTTPMiddleware`）から、受信した本文を後続の `receive` へ再送する純粋 ASGI ミドルウェア（`InternalProxyVerificationMiddleware`）へ書き換え、`POST /api/pcs` 等の本文付きリクエストでのデッドロック（502 タイムアウト）を解消する（`research.md` Decision 6）
- [x] T010 [US1] `backend/ecs/tests/test_internal_request_verifier.py` に、署名検証有効状態（`INTERNAL_PROXY_SECRET_ARN` 設定時）で JSON 本文付き `POST /api/pcs` がデッドロックせず下流ハンドラまで到達することを検証する回帰テストを追加し、テストを実行してパスすることを確認する（`T009` 完了後）
- [x] T008 `specs/007-fix-pc-registration/quickstart.md` §3〜§4 の手順に従い、`cdk diff EcsStack` で想定差分を確認して `cdk deploy EcsStack` を実行し、`main` へのプッシュ（Amplify 自動デプロイ）後に本番で PC 新規登録を実機確認する（一般ユーザーは必須、管理者は管理者アカウントを用意できた場合）（`T006`, `T007`, `T009`, `T010` 完了後）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 2 (T000)** は Phase 3 / Phase 4 をブロックする（原因が実証できない場合は実装に進まない）。
- **Phase 3 (User Story 1 - P1)** と **Phase 4 (User Story 2 - P2)** は対象ディレクトリが異なる（`infrastructure/` vs `frontend/`）ため、`T000` 完了後は互いに独立して並列実施可能。
- **Phase 5 (Polish)** は Phase 3 および Phase 4 の完了後に実行する。

### Task Dependencies

- `T000` ➔ `T001`, `T004`
- `T001` ➔ `T002`, `T003`（`T002` と `T003` は `T001` 完了後に並列実行可能）
- `T004` ➔ `T005`（`T004` は `T001` と並列実行可能）
- `T002`, `T003`, `T005` ➔ `T006`, `T007`（`T006` と `T007` は並列実行可能）
- `T006`, `T007` ➔ `T008`

### Parallel Example

```text
# 事前確認（ブロッキング）:
- T000: AWS 上の原因実証（読み取り専用）

# 並列グループ1（US1 インフラ基盤 + US2 API クライアント）:
- T001: infrastructure/stacks/ecs_stack.py
- T004: frontend/src/services/pc-api.ts

# 並列グループ2（US1 呼び出し元・テスト + US2 画面UI）:
- T002: infrastructure/app.py
- T003: infrastructure/tests/unit/test_infrastructure_stack.py
- T005: frontend/src/app/pcs/register/page.tsx

# 並列グループ3（最終検証）:
- T006: CDK 単体テスト実行
- T007: フロントエンド検証 & git diff スコープ確認

# 最終:
- T008: デプロイ & 本番実機確認
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. `T000` で原因を実証する。
2. `T001`〜`T003` を実装し、CDK 単体テストで `EcsStack` の `Users` テーブル読み取り専用権限を検証する（これだけで PC 新規登録エラーの主原因を解消）。
3. 続けて `T004`〜`T005` を実装し、管理者のコールドスタート待機・待機表示解除・ボタン付近の日本語エラー表示を改善する。
4. `T006`〜`T007` で最終検証を行い、`T008` でデプロイ後に `quickstart.md` に沿って本番実機で PC 新規登録を確認する。
