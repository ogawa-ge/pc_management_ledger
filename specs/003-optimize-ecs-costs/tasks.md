# Tasks: NAT GatewayとECS稼働数のコスト最適化

**Input**: `specs/003-optimize-ecs-costs/` の設計文書  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: 仕様の受け入れシナリオと成功基準が明示されているため、各ユーザーストーリーでテストを先に作成し、実装前に失敗を確認する。

**Organization**: 各ユーザーストーリーを独立して実装・検証できる単位に分ける。US2はUS1で採用した初期稼働数0のインフラを利用し、US3はUS2の稼働制御・アクティビティ基盤を拡張する。US4は導入済み構成の請求期間経過後に実施する。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 未完了タスクと異なるファイルを変更し、依存関係なしで並行実行可能
- **[Story]**: `spec.md` のユーザーストーリー（US1〜US4）
- すべてのタスクに変更対象または記録先の正確なファイルパスを含める

---

## Phase 1: Setup（共有準備）

**Purpose**: 用語、テスト配置、検証記録の共通形式を先に固定する。

- [ ] T001 `docs/ubiquitous-language.md` に Backend Runtime State、Idempotency Key、In-flight Operation、Runtime Generation、Validation Record の日本語定義とコード上の表記を追加する
- [ ] T002 [P] Lambdaテストのパッケージ構成とAWSクライアント差し替えfixtureを `backend/lambda/tests/__init__.py` と `backend/lambda/tests/conftest.py` に作成する
- [ ] T003 [P] 検証ID、前提、要求ID、冪等キー、所要時間、結果、秘密情報を除く証跡参照を記録できるテンプレートを `specs/003-optimize-ecs-costs/validation-records.md` に作成する

**Checkpoint**: 新規用語と全ストーリー共通のテスト・証跡形式が利用可能。

---

## Phase 2: Foundational（全ストーリーのブロッキング前提）

**Purpose**: 稼働状態、DynamoDBアクセス、内部署名、設定値を共通部品として実装する。

**⚠️ CRITICAL**: このフェーズが完了するまでユーザーストーリー実装を開始しない。

- [ ] T004 [P] Backend Runtime Control と Idempotent Request の列挙値・検証規則・時刻変換を `backend/lambda/src/models/runtime_control.py` に実装する
- [ ] T005 [P] ECS側で共有する Idempotent Request の列挙値と要求fingerprint生成を `backend/ecs/src/models/idempotent_request.py` に実装する
- [ ] T006 T004のモデルを用いて `SystemActivity` の `global` 項目を取得・条件付き更新し、世代と処理中件数を原子的に扱うリポジトリを `backend/lambda/src/services/runtime_control_repository.py` に実装する
- [ ] T007 [P] canonical request、本文SHA-256、HMAC-SHA256生成、内部ヘッダー上書きを `backend/lambda/src/services/internal_request_signer.py` に実装する
- [ ] T008 [P] 時刻窓、本文ハッシュ、定数時間比較で内部署名を検証するサービスを `backend/ecs/src/services/internal_request_verifier.py` に実装する
- [ ] T009 Lambda/ECS共通の内部署名Secret参照、クラスター名、サービス名、再試行・アイドル定数を環境変数として `infrastructure/stacks/ecs_stack.py` と `infrastructure/stacks/lambda_stack.py` に定義し、実値をコードへ埋め込まない
- [ ] T010 T004〜T009のモデル境界、条件付き更新、署名生成・改変・期限切れ拒否を `backend/lambda/tests/test_runtime_control_repository.py`、`backend/lambda/tests/test_internal_request_signer.py`、`backend/ecs/tests/test_internal_request_verifier.py` で検証する

**Checkpoint**: Foundation ready — 稼働制御と内部通信保護を各ストーリーから利用可能。

---

## Phase 3: User Story 1 - 低コスト構成の採用判断（Priority: P1）🎯 MVP

**Goal**: 現行案とNAT Gatewayを常設しない案を同じ条件で比較し、必須4通信を維持する月額3,000円以下の候補を採用可能にする。

**Independent Test**: 現行案と1つ以上の代替案について、Gemini API、DynamoDB、ECR、CloudWatch Logsの通信可否、価格基準日、固定費・従量費・通信費、利点、制約、リスク、採否を第三者が追跡でき、新規タスクから4通信すべてが成功することを確認する。

### Tests for User Story 1（先に作成して失敗確認）

- [ ] T011 [P] [US1] NAT Gateway 0件、ALB 0件、public subnet、AssignPublicIp ENABLED、ECS DesiredCount 0を要求するCDK assertionを `infrastructure/tests/unit/test_ecs_cost_optimization.py` に作成する
- [ ] T012 [P] [US1] 内部署名Secret参照、対象ECSサービスへのIAM権限、デプロイ時初期数0を要求するCDK assertionを `infrastructure/tests/unit/test_lambda_ecs_integration.py` に作成する

### Implementation for User Story 1

- [ ] T013 [US1] VPCを明示的なpublic subnetのみ・`nat_gateways=0`へ変更し、Fargate Serviceを`desired_count=0`かつpublic IP割当のまま構成する `infrastructure/stacks/ecs_stack.py`
- [ ] T014 [US1] LambdaのECS操作IAMを対象クラスター/サービスへ可能な限り限定し、ECSと共有する署名Secretの読み取り権限を設定する `infrastructure/stacks/lambda_stack.py`
- [ ] T015 [P] [US1] 現行NAT案、採用public subnet案、Endpoint案の固定費・従量費・通信費を同じ730時間・東京リージョン・為替条件で記録する `specs/003-optimize-ecs-costs/cost-estimate.md`
- [ ] T016 [P] [US1] 新規タスク起動、ECR pull、CloudWatch Logs、DynamoDBダミーread/write/delete、Geminiダミー解析を実行して検証ID付き結果を出力する `scripts/validate-ecs-connectivity.ps1`
- [ ] T017 [US1] 採用案、却下理由、既知のリスク、月額3,000円判定、見直し条件を `specs/003-optimize-ecs-costs/adoption-decision.md` に記録する
- [ ] T018 [US1] CDK testsとsynth後に検証環境へデプロイし、AWS CLI `describe-services`で直後のdesired/running/pendingがすべて0である証跡を `specs/003-optimize-ecs-costs/validation-records.md` に記録する
- [ ] T019 [US1] `scripts/validate-ecs-connectivity.ps1` を検証環境で実行し、新規タスクから必須4通信がすべてPASSとなる結果と失敗時の理由を `specs/003-optimize-ecs-costs/validation-records.md` に記録する

**Checkpoint**: 低コスト構成の採否と通信維持を独立してレビュー可能。ここまでが最小の判断MVP。

---

## Phase 4: User Story 2 - 停止状態からの自動利用再開（Priority: P1）

**Goal**: 停止中のPC管理操作からECSを一度だけ起動し、起動中表示と最大3分の自動再送を経て、参照・PC登録・PC返却を一回だけ成立させる。

**Independent Test**: ECS desired/running 0から `GET /api/pcs`、PC登録、PC返却を開始し、起動中表示、自動起動、自動再送、3分以内の成功を確認する。同時10件の起動要求を1回に集約し、登録・返却の重複結果がないことも確認する。

### Tests for User Story 2（先に作成して失敗確認）

- [ ] T020 [P] [US2] `503 starting`、`Retry-After`、同時10件の起動所有者1件、利用可能後の転送を検証する契約テストを `backend/lambda/tests/test_ecs_start_proxy.py` に作成する
- [ ] T021 [P] [US2] 内部署名欠落・改変・期限切れの403と正しい署名後も既存認証認可を維持するAPIテストを `backend/ecs/tests/test_internal_proxy_auth.py` に作成する
- [ ] T022 [P] [US2] 新規・処理中・成功済み・fingerprint競合・期限切れの冪等性遷移を検証するテストを `backend/ecs/tests/test_idempotency_service.py` に作成する
- [ ] T023 [P] [US2] PC登録とPC返却の同一キー再送でDynamoDBトランザクションと業務結果が1回だけ成立するテストを `backend/ecs/tests/test_idempotent_pc_operations.py` に作成する
- [ ] T024 [P] [US2] Node.js組み込み`node:test`で`503 starting`と`409 processing`だけを同じキーで再送し、180秒・キャンセル・通常エラーで停止するフロントエンドテストを `frontend/src/services/pc-api.test.ts` に作成する

### Implementation for User Story 2

- [ ] T025 [US2] `STOPPED`/`START_FAILED`からの条件付き`STARTING`遷移、起動所有者だけの`UpdateService(1)`、ready判定、状態照合を `backend/lambda/src/services/ecs_manager.py` に実装する
- [ ] T026 [US2] PC管理要求の受付、起動中共通レスポンス、ready後の署名付き転送、内部ヘッダー除去、公開エラーの秘匿を `backend/lambda/src/main.py` に実装する
- [ ] T027 [US2] `SystemActivity`の`request#{idempotencyKey}`に対する処理権取得、fingerprint競合、成功結果再利用、TTL期限判定を `backend/ecs/src/services/idempotency_service.py` に実装する
- [ ] T028 [US2] 内部署名検証を全PC管理ルートの前段へ適用し、`Idempotency-Key`必須化とprocessing/conflict/replayedレスポンスを `backend/ecs/src/main.py` に実装する
- [ ] T029 [US2] PC登録の条件付き業務書込みと冪等成功記録を1回の`TransactWriteItems`で確定する `backend/ecs/src/services/pc_service.py`
- [ ] T030 [US2] PC返却記録・PC状態/履歴更新・冪等成功記録を1回の`TransactWriteItems`で確定し、同じキーの再送結果を再利用する `backend/ecs/src/services/pc_service.py`
- [ ] T031 [US2] UUIDキー生成、要求スナップショット、`Retry-After`準拠、最大180秒、AbortSignal、starting/processing判定を共通APIクライアントとして `frontend/src/services/pc-api.ts` に実装する
- [ ] T032 [P] [US2] 起動中、残り待機、3分超過、利用者キャンセル、安全な再試行を表示できるよう `frontend/src/components/ecs-loading-state.tsx` と `frontend/src/components/ecs-loading-state.css` を更新する
- [ ] T033 [US2] 一覧・登録・返却を共通再試行クライアントと起動状態UIへ統合する `frontend/src/app/pcs/page.tsx`、`frontend/src/app/pcs/register/page.tsx`、`frontend/src/app/pcs/[pcId]/return/page.tsx`
- [ ] T034 [P] [US2] desired 0から対象3操作を各5回、同時起動10件、3分タイムアウト、登録/返却重複を自動検証する `scripts/validate-cold-start.ps1`
- [ ] T035 [US2] Lambda/ECS/フロントエンドのテストと`validate-cold-start.ps1`を実行し、全15回の所要時間、起動集約、重複0件を `specs/003-optimize-ecs-costs/validation-records.md` に記録する

**Checkpoint**: 停止状態からの対象3操作が利用者の手動更新なしで独立して完了し、一回処理を証明可能。

---

## Phase 5: User Story 3 - 未使用時の自動スリープ（Priority: P2）

**Goal**: 成功完了から2時間未満または処理中は稼働を維持し、2時間以上未使用なら15分以内に停止し、停止競合時は中止または再起動する。

**Independent Test**: `lastActivityAt`を2時間境界の前後へ設定し、処理中、欠損、不正、未来時刻、停止直前/実行後の新規操作を含めて、期待どおり維持・停止・再起動することを確認する。

### Tests for User Story 3（先に作成して失敗確認）

- [ ] T036 [P] [US3] 受付時刻、転送前の処理中加算、2xx成功完了時刻、全終了経路の減算、非2xxで完了時刻を更新しないことを `backend/lambda/tests/test_activity_tracking.py` に作成する
- [ ] T037 [P] [US3] 2時間未満/境界/超過、処理中、欠損、不正、未来時刻を含むfail-open停止判定テストを `backend/lambda/tests/test_idle_sleep_policy.py` に作成する
- [ ] T038 [P] [US3] 停止前の世代競合で停止中止、`UpdateService(0)`後の新世代で`UpdateService(1)`再適用を検証するテストを `backend/lambda/tests/test_stop_start_race.py` に作成する
- [ ] T039 [P] [US3] EventBridgeが15分間隔で停止判定Lambdaを呼び、必要IAMと環境変数を持つCDK assertionを `infrastructure/tests/unit/test_idle_sleep_schedule.py` に作成する

### Implementation for User Story 3

- [ ] T040 [US3] 受付・処理中・成功完了の原子的アクティビティ更新と例外経路の安全な減算をプロキシ処理へ統合する `backend/lambda/src/main.py`
- [ ] T041 [US3] 2時間アイドル、`inFlightCount=0`、正常時刻、世代不変の停止ゲート、異常時fail-open監査、STOPPING後の世代再確認と再起動を `backend/lambda/src/services/ecs_manager.py` に実装する
- [ ] T042 [US3] タイムアウト判定EventBridgeを15分間隔へ変更し、停止判定Lambdaへテーブル名・アイドル秒数・ECS識別子を設定する `infrastructure/stacks/lambda_stack.py`
- [ ] T043 [P] [US3] 境界値、処理中、異常記録、停止前/停止後競合、最終desired/running 0を自動検証する `scripts/validate-idle-sleep.ps1`
- [ ] T044 [US3] US3テストと`validate-idle-sleep.ps1`を実行し、全境界ケース、15分以内停止、競合時の元操作一回成功を `specs/003-optimize-ecs-costs/validation-records.md` に記録する

**Checkpoint**: 起動後に自動で0へ戻り、利用中操作を停止させないことを独立して証明可能。

---

## Phase 6: User Story 4 - 最適化効果の確認（Priority: P3）

**Goal**: 導入後30日または最初の完全請求期間について、主要費用項目の見積りと実績を比較し、目標または20%超過時の再評価判断を残す。

**Independent Test**: 同じ期間・通貨・サービス分類で見積りと請求実績を並べ、差額、差率、原因候補、対応、次回確認日を第三者が追跡できることを確認する。

### Tests for User Story 4（先に作成して失敗確認）

- [ ] T045 [P] [US4] 見積り0円時のNEW_COSTを含む差額・差率、3,000円超過、20%超過の再評価判定をテストする `scripts/tests/test-cost-comparison.ps1`

### Implementation for User Story 4

- [ ] T046 [US4] Cost Explorerの期間・サービス別CSVと`cost-estimate.md`から差額、差率、原因候補欄、再評価要否を生成し、アカウントIDをマスクする `scripts/compare-aws-costs.ps1`
- [ ] T047 [US4] 導入後30日または最初の完全請求期間に`compare-aws-costs.ps1`を実行し、主要明細、合計、差率を `specs/003-optimize-ecs-costs/cost-actual-review.md` に記録する
- [ ] T048 [US4] 月額3,000円または見積り20%超過の有無、原因、対応責任者、再評価判断、次回レビュー日を `specs/003-optimize-ecs-costs/cost-actual-review.md` に確定する

**Checkpoint**: 見積りと実績の差異および見直し判断を独立して監査可能。

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 全ストーリー横断の安全性、回帰、文書整合性を最終確認する。

- [ ] T049 [P] 内部署名なしのECS直接アクセス、期限切れ・本文改変、不正署名、正しい署名後の認証認可を検証する `scripts/validate-internal-proxy-security.ps1`
- [ ] T050 [P] ログと検証記録にAuthorization、HMAC署名、Gemini APIキー、Secrets Manager値、実PCデータが含まれないことを確認する `scripts/validate-sensitive-output.ps1`
- [ ] T051 既存認証・認可、PC一覧、PC登録、PC返却、Gemini抽出の回帰テストを実行し、結果を `specs/003-optimize-ecs-costs/validation-records.md` に追記する
- [ ] T052 `backend/lambda/tests`、外部Gemini実通信を除く`backend/ecs/tests`、`infrastructure/tests`、`npx tsc --noEmit`、`npm run build`、CDK synthを `specs/003-optimize-ecs-costs/quickstart.md` の手順どおり実行する
- [ ] T053 FR-001〜FR-018とSC-001〜SC-008の証跡参照、採用判断、実績レビュー、既知制約を `specs/003-optimize-ecs-costs/validation-records.md` に最終整理する

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup（Phase 1）**: 依存なし。T002とT003はT001と並行可能。
- **Foundational（Phase 2）**: Setup完了後。T004/T005/T007/T008は並行可能、T006はT004後、T009は署名部品の実装と並行可能、T010はT004〜T009後。
- **US1（Phase 3）**: Foundational完了後。採用インフラを確定し、US2/US3の実環境前提となる。
- **US2（Phase 4）**: US1のT013/T014/T018完了後。初期0のECSとIAM/Secret設定を使用する。
- **US3（Phase 5）**: US2完了後。起動状態、世代、プロキシ、処理中カウンターを拡張する。
- **US4（Phase 6）**: US1〜US3の導入後、30日または最初の完全請求期間のデータ取得後。
- **Polish（Phase 7）**: リリース対象のUS1〜US4完了後。

### User Story Dependencies

```text
Setup → Foundational → US1 → US2 → US3 → 運用期間経過 → US4 → Polish
```

- **US1（P1）**: Foundational後に開始可能。構成比較・採用判断だけなら独立したMVP。
- **US2（P1）**: US1の採用インフラに依存するが、US3/US4には依存しない。
- **US3（P2）**: US2の稼働制御とアクティビティ経路に依存する。
- **US4（P3）**: 実装依存ではなく、採用構成の運用期間と請求データに依存する。

### Within Each User Story

1. テストを作成し、対象実装が未完了の状態で失敗を確認する。
2. モデル/インフラ定義を先に実装する。
3. サービス、API、UIの順で統合する。
4. ローカルテストとsynth/buildを成功させる。
5. 実環境検証を行い、秘密情報を除いた証跡を記録する。
6. ストーリーのIndependent Testを満たしてから次の優先度へ進む。

---

## Parallel Opportunities

### Setup / Foundation

```text
T002 Lambda test fixture || T003 validation template
T004 Lambda runtime model || T005 ECS idempotency model || T007 signer || T008 verifier
```

### User Story 1

```text
T011 ECS CDK test || T012 Lambda CDK test
T015 cost estimate || T016 connectivity validation script
```

### User Story 2

```text
T020 start proxy test || T021 internal auth test || T022 idempotency test || T023 operation transaction test || T024 frontend retry test
T032 loading UI || T034 cold-start validation script
```

### User Story 3

```text
T036 activity test || T037 idle policy test || T038 race test || T039 schedule test
T043 idle-sleep validation script（T040〜T042の実装と別ファイルで準備可能）
```

### User Story 4 / Polish

```text
T045 cost comparison test（請求期間経過前に準備可能）
T049 proxy security validation || T050 sensitive output validation
```

---

## Implementation Strategy

### MVP First（User Story 1）

1. Phase 1 Setupを完了する。
2. Phase 2 Foundationalを完了する。
3. Phase 3 US1でNATなし・ECS初期0の構成と費用比較を成立させる。
4. 必須4通信とデプロイ直後タスク0を検証する。
5. **STOP and VALIDATE**: 採用判断をレビューし、月額目標と必須通信の両立を承認する。

### Incremental Delivery

1. **US1**: 構成比較・NAT削除・初期0・通信検証 → 低コスト構成を採用
2. **US2**: 自動起動・自動再送・一回処理 → 停止状態から利用可能
3. **US3**: 2時間アイドル停止・処理中保護・競合回復 → 継続的に待機費0
4. **US4**: 30日実績比較・再評価判断 → 最適化効果を運用で閉じる

### Validation Gates

- US1 gate: NAT 0、ALB 0、デプロイ直後タスク0、必須4通信PASS、比較・採用記録あり
- US2 gate: 対象3操作×5回が3分以内、同時10件が起動1回、登録/返却重複0
- US3 gate: 全境界判定PASS、処理中停止0、境界成立後15分以内停止、競合操作一回成功
- US4 gate: 主要明細の差率100%記録、3,000円/20%超過時の判断あり

---

## Notes

- `[P]` はファイル競合と未完了依存がないタスクだけに付与している。
- 実装中に未定義の業務属性追加が必要と判明した場合、コード変更前に `specs/003-optimize-ecs-costs/data-model.md` と該当契約を更新する。
- 実キー、AWSアカウントID、Authorization、実PCデータをテスト、スクリプト、文書、ログへ保存しない。
- 外部Gemini実通信テストは通常のローカルテストから分離し、検証環境でダミーデータを用いて実行する。
- 各タスクまたは論理的な小グループ単位でコミットし、無関係なリファクタリングを含めない。