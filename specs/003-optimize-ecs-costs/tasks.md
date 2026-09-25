# Tasks: 既存ECS運用のコスト最適化と安全性補強

**Input**: `specs/003-optimize-ecs-costs/` の設計文書
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: 仕様の受け入れシナリオ、成功基準、計画のテスト戦略に従い、バックエンドとCDKでは対象実装より先に失敗するテストを追加する。フロントエンドは既存プロジェクトにテストランナーがないため、新規ライブラリを追加せず型検査、build、手動受け入れ検証で確認する。

**Organization**: 001由来の起動・停止・アイドル判定、Lambdaプロキシ、起動中UI、PC管理処理を再利用し、設定是正と不足する安全対策だけをユーザーストーリー単位で追加する。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 未完了タスクと異なるファイルを変更し、依存関係なしで並行実行可能
- **[Story]**: `spec.md` のユーザーストーリー（US1〜US5）
- すべてのタスクに変更対象または記録先の具体的なファイルパスを含める

---

## Phase 1: Setup（既存実装のベースライン固定）

**Purpose**: 新規構築を避け、001と現行コードの再利用範囲、状態変更API、検証方法、共通用語を実装前に固定する。

- [X] T001 `specs/003-optimize-ecs-costs/validation-records.md` に001由来の既存実装一覧、変更前の`nat_gateways=1` / `desired_count=1`、既存起動・停止・プロキシ・UI・認証の回帰基準、および検証記録テンプレートを作成する
- [X] T002 [P] `docs/ubiquitous-language.md` にBackend Runtime State、Start Lock、Idempotency Key、In-flight Operation、Runtime Generation、Internal Request Signature、Secret Generationの日本語定義とコード表記を追加する
- [X] T003 [P] `backend/lambda/tests/conftest.py` に実`ECSManager`のboto3 ECS・DynamoDB・CloudWatchクライアント境界と固定時計を差し替えるfixtureを追加する
- [X] T004 [P] `backend/ecs/tests/conftest.py` にDynamoDB resource/client、Secrets Manager、固定時計、業務書込み失敗を差し替えるfixtureを追加する
- [X] T005 [P] `backend/ecs/tests/test_state_changing_route_inventory.py` にFastAPIの`POST`/`PUT`/`PATCH`/`DELETE`ルートを棚卸しし、`POST /api/pcs`、`POST /api/pcs/{pc_id}/return`、`PATCH /api/pcs/{pc_id}/status`を冪等対象、`POST /api/pcs/parse-specs`を非永続対象として固定し、未分類ルートで失敗するテストを追加する
- [X] T006 [P] `specs/003-optimize-ecs-costs/quickstart.md` の検証コマンドを実在する`backend/lambda/tests`、`backend/ecs/tests`、`infrastructure/tests`、フロントエンド型検査・buildのパスへ合わせて確認・更新する

**Checkpoint**: 既存コードの再利用境界、状態変更3ルート、全ストーリーで使う検証・用語・テスト基盤が確定している。

---

## Phase 2: Foundational（共有制御データ・署名基盤・契約の最小拡張）

**Purpose**: 既存`SystemActivity`、Secrets Manager、既存API契約を、起動ロック・活動管理・冪等性・内部署名から共用できる状態にする。

**⚠️ CRITICAL**: このフェーズでは起動・停止・プロキシの代替実装を作成せず、既存コードが参照する設定、秘密、データ契約だけを整える。

- [X] T007 `specs/003-optimize-ecs-costs/data-model.md` の`global`項目と`request#{idempotencyKey}`項目について、既存`entityId`キーとの後方互換、初期値、ロック期限、成功完了+7日の期限、TTL削除待ちの置換、5分停滞回収、旧所有者の遅延確定拒否を実装可能な条件式まで最終確認する
- [X] T008 [P] `specs/003-optimize-ecs-costs/contracts/runtime-api.md` の状態変更3ルート、`503 starting`、`409 processing`、7日保持、5分回収、内部署名、±60秒、最大2世代ローテーションをFR-004a〜FR-016へ対応付ける
- [X] T009 [P] `infrastructure/stacks/database_stack.py` の既存`SystemActivity`テーブルへ`expiresAt`のTTL設定だけを追加し、専用テーブルや業務テーブル属性を増やさないCDK assertionを`infrastructure/tests/unit/test_infrastructure_stack.py`に追加する
- [X] T010 [P] `infrastructure/tests/unit/test_internal_proxy_secret.py` にLambda/ECSが同じ内部署名Secretを参照し、秘密値を通常環境変数・CloudFormation出力へ含めず、各実行ロールが対象Secretの`secretsmanager:GetSecretValue`だけを持つCDK assertionを追加して失敗を確認する
- [X] T011 `infrastructure/stacks/lambda_stack.py` と`infrastructure/stacks/ecs_stack.py` に既存`SystemActivity`テーブル名、クラスター名、サービス名、アイドル秒数、再試行上限、内部署名Secret ARN、非機密の署名key ID設定を渡し、Lambda/ECSロールへ対象Secretの読取だけを付与する
- [X] T012 `infrastructure/tests/unit/test_internal_proxy_secret.py` と`infrastructure/tests/unit/test_infrastructure_stack.py`を実行し、TTL、Secret参照、IAM最小権限、秘密値非露出を`specs/003-optimize-ecs-costs/validation-records.md`へ記録する

**Checkpoint**: 既存テーブル・API・秘密管理の境界が固定され、US1〜US4で別の制御基盤や実キー埋込みを作る必要がない。

---

## Phase 3: User Story 1 - 未使用時に固定費を発生させない（Priority: P1）🎯 MVP

**Goal**: 現行VPC/ECS定義の設定ミスだけを是正し、NAT Gatewayなし・ECS初期稼働数0で必要通信、内部署名、既存業務結果を維持する。

**Independent Test**: CDK synth結果にNAT Gatewayがなく、ECS ServiceのDesiredCountが0、public subnetとpublic IP割り当てが維持される。停止状態から起動したタスクで4通信が成功し、有効なLambda署名だけがECS業務処理へ到達し、3段階の秘密ローテーションが無停止で完了する。

### Tests for User Story 1（実装前に失敗確認）

- [X] T013 [P] [US1] NAT Gateway 0件、ECS DesiredCount 0、public subnet、AssignPublicIp ENABLED、ALB 0件を要求するCDK assertionを`infrastructure/tests/unit/test_ecs_cost_optimization.py`に追加して現行設定で失敗を確認する
- [X] T014 [P] [US1] canonical request、HMAC-SHA256、外部入力の`X-Internal-*`除去、メソッド・正規化パス/クエリ・本文ハッシュ・要求ID・冪等キー・時刻・key IDを署名するテストを`backend/lambda/tests/test_internal_request_signer.py`に追加して失敗を確認する
- [X] T015 [P] [US1] 正常署名、ヘッダー欠落、本文・パス・メソッド・要求ID・冪等キー改ざん、不正署名、不明key ID、時刻差-61/-60/+60/+61秒、定数時間比較、既存認証継続を`backend/ecs/tests/test_internal_request_verifier.py`に追加して失敗を確認する
- [X] T016 [P] [US1] 現行のみ、現行+次期、次期へLambda切替、旧秘密失効の各構成で最大2世代だけを検証し、3世代・失効key IDを拒否するテストを`backend/ecs/tests/test_internal_secret_rotation.py`に追加して失敗を確認する
- [X] T017 [P] [US1] 新規タスク起動、ECR pull、CloudWatch Logs出力、DynamoDBダミーread/write/delete、Geminiダミー解析を検証ID付きで記録する`scripts/validate-ecs-connectivity.ps1`を作成する
- [X] T018 [P] [US1] 署名欠落・改ざん・期限切れ・不明key ID・利用者認証違反と3段階秘密切替を秘密値非記録で検証する`scripts/validate-internal-proxy-signature.ps1`を作成する

### Implementation for User Story 1

- [X] T019 [US1] 既存VPCとFargate Service定義を維持したまま`nat_gateways=1`を`nat_gateways=0`、`desired_count=1`を`desired_count=0`へ修正する`infrastructure/stacks/ecs_stack.py`
- [X] T020 [P] [US1] Secrets Managerから指定key IDの1世代を取得しcanonical requestをHMAC-SHA256署名する`backend/lambda/src/services/internal_request_signer.py`を実装する
- [X] T021 [US1] 既存`proxy_to_ecs()`で外部入力の`X-Internal-*`を削除し、要求本文を一度だけ読み取り、要求ID・冪等キー・送信時刻・本文ハッシュ・key ID・署名を再生成して転送する`backend/lambda/src/main.py`
- [X] T022 [P] [US1] Secrets Managerから最大2世代を取得し、本文ハッシュ、時刻窓±60秒、key ID、HMACを定数時間比較で検証する`backend/ecs/src/services/internal_request_verifier.py`を実装する
- [X] T023 [US1] すべてのECS業務ルートで既存認証・認可より前に内部署名を検証し、欠落・不正・期限切れ・失効署名を業務処理前の`403`にする`backend/ecs/src/main.py`
- [X] T024 [P] [US1] 現行「NAT 1・常時1」と採用「NAT 0・初期0/利用時1」とEndpoint却下案を同一の価格基準日、東京リージョン、730時間、通信量、為替条件で比較し採否を`specs/003-optimize-ecs-costs/cost-estimate.md`に記録する
- [X] T025 [US1] `infrastructure/tests/unit/test_ecs_cost_optimization.py`、`infrastructure/tests/unit/test_internal_proxy_secret.py`、Lambda/ECS署名テスト、CDK synthを実行し、NAT 0、初期0、public IP、ALB 0、署名境界、秘密非露出を`specs/003-optimize-ecs-costs/validation-records.md`に記録する
- [ ] T026 [US1] 検証環境で`scripts/validate-ecs-connectivity.ps1`を実行し、デプロイ直後desired/running 0と新規タスクからの4通信を`specs/003-optimize-ecs-costs/validation-records.md`に記録する
- [ ] T027 [US1] 検証環境で`scripts/validate-internal-proxy-signature.ps1`をECSへ次期秘密追加、Lambdaを次期へ切替、ECSから旧秘密失効の順に実行し、各段階の正当転送100%成功、旧秘密失効後100%拒否、業務書込み0件を`specs/003-optimize-ecs-costs/validation-records.md`に記録する

**Checkpoint**: US1単独で、未使用時固定費を除去した構成、必要通信、公開ECSへの多層防御、無停止秘密ローテーションを実証できる。

---

## Phase 4: User Story 2 - 停止状態から安全に操作を再開する（Priority: P1）

**Goal**: 既存の自動起動、Lambdaプロキシ、起動中UIを自動再送へ接続し、状態変更3ルートをボタン連打や再送でも一度だけ原子的に成立させる。

**Independent Test**: 停止状態からPC一覧、PC登録、PC返却を各5回実行して3分以内に自動完了する。登録・返却・ステータス更新で7日保持、5分回収、旧所有者拒否、部分成功0件を確認する。

### Tests for User Story 2（実装前に失敗確認）

- [X] T028 [P] [US2] 既存`proxy_to_ecs()`が停止時に既存`ensure_ecs_running()`を1回呼び、`503`、`Retry-After`、`status=starting`、`Cache-Control=no-store`を返して通常503と区別できるテストを`backend/lambda/tests/test_lambda_ecs_proxy.py`に追加して失敗を確認する
- [X] T029 [P] [US2] 冪等要求の新規取得、同一内容処理中、成功結果再利用、内容競合、成功完了から7日直前の再利用、7日経過後かつTTL物理削除前の新規取得を`backend/ecs/tests/test_idempotency_service.py`に追加して失敗を確認する
- [X] T030 [US2] `PROCESSING`取得から5分未満の回収拒否、5分以上かつ成功未確定の回収、成功済み回収拒否、同時回収1件、旧`ownerRequestId`・旧`startedAt`条件を`backend/ecs/tests/test_idempotency_service.py`に追加して失敗を確認する
- [X] T031 [P] [US2] 同一`Idempotency-Key`の登録・返却・ステータス更新を複数回送って業務書込みが1回、成功再利用、内容競合が業務変更なしの`409`となる契約テストを`backend/ecs/tests/test_idempotent_pc_operations.py`に追加して失敗を確認する
- [X] T032 [US2] 登録、返却、ステータス更新について業務項目、履歴項目、冪等成功記録を項目ごとに失敗させて部分成功0件とし、5分回収後の旧所有者トランザクションが業務変更なしで失敗するテストを`backend/ecs/tests/test_idempotent_pc_transactions.py`に追加して失敗を確認する

### Implementation for User Story 2

- [X] T033 [US2] 既存`proxy_to_ecs()`の停止時分岐を拡張し、既存`ensure_ecs_running()`を使ったまま要求ID、機械判定可能な起動中本文、`Retry-After`、`Cache-Control=no-store`を返す`backend/lambda/src/main.py`
- [X] T034 [US2] `SystemActivity`の`request#{idempotencyKey}`を使い、fingerprint、条件付き処理権取得、処理中応答、成功結果再利用、内容競合、成功+7日判定、TTL削除待ち置換、5分停滞回収を共通化する`backend/ecs/src/services/idempotency_service.py`
- [X] T035 [US2] 登録・返却・ステータス更新で`Idempotency-Key`を必須化し、内部署名検証と既存認証・認可後かつ業務処理前に共通冪等ガードを適用し、`POST /api/pcs/parse-specs`を保存対象外とする`backend/ecs/src/main.py`
- [X] T036 [US2] 既存PC登録を低レベルDynamoDB clientの`TransactWriteItems`へ最小変更し、PC Put、必要な既存履歴Put、所有者・開始時刻条件付き冪等成功更新を同時確定する`backend/ecs/src/services/pc_service.py`
- [X] T037 [US2] 既存PC返却を`TransactWriteItems`へ最小変更し、返却記録Put、PC状態Update、必要な既存履歴Put、所有者・開始時刻条件付き冪等成功更新を同時確定する`backend/ecs/src/services/pc_service.py`
- [X] T038 [US2] 既存PCステータス更新を`TransactWriteItems`へ最小変更し、PC状態Update、既存履歴Put、所有者・開始時刻条件付き冪等成功更新を同時確定する`backend/ecs/src/main.py`
- [X] T039 [US2] UUID形式の要求識別値を利用者操作ごとに1回生成し、同じメソッド・URL・本文・キーを`503 starting`または`409 processing`の`Retry-After`に従って最大180秒再送する共通処理へ既存`getPCs()`、`registerPC()`、`returnPC()`を統合する`frontend/src/services/pc-api.ts`
- [X] T040 [P] [US2] 既存`ECSLoadingState`と`useECSLoadingState`を、起動中、残り待機時間、180秒超過、キャンセル、安全な再試行を表示できるよう拡張する`frontend/src/components/ecs-loading-state.tsx`と`frontend/src/components/ecs-loading-state.css`
- [X] T041 [US2] 既存の直接fetchを`getPCs()`へ置き換え、ECS起動待ちだけ既存`ECSLoadingState`を表示し通常エラーを維持する`frontend/src/app/pcs/page.tsx`
- [X] T042 [US2] 既存の連打抑止を維持しつつ、登録操作の同一キー再送、起動待ち表示、3分超過後の安全な再試行を接続する`frontend/src/app/pcs/register/page.tsx`
- [X] T043 [US2] 既存の直接fetchを`returnPC()`へ置き換え、送信中の連打抑止、同一キー再送、起動待ち表示、成功後処理を接続する`frontend/src/app/pcs/[pcId]/return/page.tsx`
- [X] T044 [US2] 冪等サービス、状態変更契約、トランザクション、Lambdaプロキシのテストとフロントエンド型検査・buildを実行し、7日境界、5分回収、旧所有者拒否、部分成功0件を`specs/003-optimize-ecs-costs/validation-records.md`に記録する
- [ ] T045 [US2] 停止状態からPC一覧・登録・返却を各5回、登録・返却を自動再送込みで各10回、ステータス更新の重複試験を実施し、3分以内完了、同一キー維持、業務結果重複0件を`specs/003-optimize-ecs-costs/validation-records.md`に記録する

**Checkpoint**: US2単独で、停止中からの利用再開と全状態変更ルートの原子的な一回処理を検証できる。

---

## Phase 5: User Story 3 - 同時要求と停止競合から操作を守る（Priority: P1）

**Goal**: 既存`ensure_ecs_running()` / `start_ecs()`の競合窓を条件付き起動ロックで閉じ、停止処理と新規操作が競合しても要求を失わない。

**Independent Test**: 停止状態へ10件同時要求を送って`UpdateService(desiredCount=1)`が1回だけ実行され、停止直前・停止API実行後に到着した操作も既存起動機構と同じ冪等キーで一度だけ完了する。

### Tests for User Story 3（実装前に失敗確認）

- [ ] T046 [P] [US3] 実`ECSManager`に10件の同時起動要求を与え、条件付きロック取得1件、ロック非取得9件、`update_service(desiredCount=1)` 1回、全要求がstarting/runningを返すテストを`backend/lambda/tests/test_ecs_manager.py`に追加して失敗を確認する
- [ ] T047 [US3] 起動ロック期限切れ回復、所有者だけの起動成功・失敗状態更新、ECS実状態との再照合を`backend/lambda/tests/test_ecs_manager.py`に追加して失敗を確認する
- [ ] T048 [P] [US3] 停止所有権取得前の新規世代で停止中止、`desiredCount=0`実行後の新規世代で`desiredCount=1`再適用となる競合テストを`backend/lambda/tests/test_ecs_stop_race.py`に追加して失敗を確認する

### Implementation for User Story 3

- [ ] T049 [US3] 既存`ensure_ecs_running()` / `start_ecs()`に`SystemActivity`の状態・世代・所有者・期限を使う条件付き起動ロックを追加し、所有者だけが既存`update_service(desiredCount=1)`を呼ぶ`backend/lambda/src/services/ecs_manager.py`
- [ ] T050 [US3] ロック非取得側が既存`get_ecs_status()`で起動中または稼働中を返し、期限切れロックと起動失敗を実ECS状態から回復する`backend/lambda/src/services/ecs_manager.py`
- [ ] T051 [US3] 新規操作受付時に世代を進め、停止所有権取得前なら停止中止、既存停止更新後なら既存`ensure_ecs_running()`で再起動する競合処理を`backend/lambda/src/services/ecs_manager.py`と`backend/lambda/src/main.py`へ統合する
- [ ] T052 [P] [US3] 停止状態へ10件を同時送信し、起動更新回数、各応答、最終desired/running数を確認する`scripts/validate-concurrent-start.ps1`を作成する
- [ ] T053 [US3] 起動・停止競合テストを実行し、同時10件と停止前後の競合結果を`specs/003-optimize-ecs-costs/validation-records.md`に記録する
- [ ] T054 [US3] 検証環境で`scripts/validate-concurrent-start.ps1`と停止競合シナリオを実行し、起動更新1回、最終稼働数1、元操作一回成功を`specs/003-optimize-ecs-costs/validation-records.md`に記録する

**Checkpoint**: US3単独で、複数Lambda実行環境を想定した起動集約と停止競合からの要求回復を検証できる。

---

## Phase 6: User Story 4 - 2時間アイドル後の既存自動停止を維持する（Priority: P2）

**Goal**: 既存の最終アクティビティと2時間停止判定を、受付・成功完了・処理中件数へ接続し、異常時や処理中に停止せず条件成立後15分以内に停止する。

**Independent Test**: 2時間境界前後、処理中件数あり、時刻欠損・不正・未来、停止競合の全ケースで期待どおり分岐し、正しいアイドル条件成立後15分以内にdesired/runningが0となる。

### Tests for User Story 4（実装前に失敗確認）

- [ ] T055 [P] [US4] プロキシ受付時の`lastAcceptedAt`、転送前の`inFlightCount += 1`、2xx完了時の`lastActivityAt`、全終了経路の減算を`backend/lambda/tests/test_lambda_activity_tracking.py`に追加して失敗を確認する
- [ ] T056 [P] [US4] 2時間未満・境界・超過、処理中、`lastActivityAt`と`inFlightCount`の欠損・不正・未来・負数を与え、停止せず`invalid_runtime_activity`監査ログを出すテストを`backend/lambda/tests/test_ecs_manager.py`に追加して失敗を確認する
- [ ] T057 [P] [US4] 既存EventBridgeルールが15分間隔で既存停止判定Lambdaを呼ぶCDK assertionを`infrastructure/tests/unit/test_ecs_idle_schedule.py`に追加して失敗を確認する

### Implementation for User Story 4

- [ ] T058 [US4] 既存`proxy_to_ecs()`に受付時刻更新、転送直前の処理中件数加算、2xx成功完了時刻更新、例外を含む全終了経路の安全な減算を追加する`backend/lambda/src/main.py`
- [ ] T059 [US4] 既存`check_and_auto_sleep()`と定期判定ハンドラーを、2時間経過、処理中0、正常時刻、世代不変でだけ既存`stop_ecs()`を呼び、異常時は秘密情報なしの構造化監査ログを残す`backend/lambda/src/services/ecs_manager.py`
- [ ] T060 [US4] 既存`EcsTimeoutCheckRule`を1時間から15分へ変更し、既存停止判定Lambdaへテーブル名・アイドル秒数を渡す`infrastructure/stacks/lambda_stack.py`
- [ ] T061 [P] [US4] 2時間境界、処理中、異常記録、停止後desired/running 0を安全に再現する`scripts/validate-idle-sleep.ps1`を作成する
- [ ] T062 [US4] 活動追跡、停止判定、CDKスケジュールのテストを実行し、結果を`specs/003-optimize-ecs-costs/validation-records.md`に記録する
- [ ] T063 [US4] 検証環境で`scripts/validate-idle-sleep.ps1`を実行し、処理中停止0件、異常時fail-open、アイドル成立後15分以内のdesired/running 0を`specs/003-optimize-ecs-costs/validation-records.md`に記録する

**Checkpoint**: US4単独で、001由来の2時間自動停止が処理中操作を壊さず待機費0へ戻ることを検証できる。

---

## Phase 7: User Story 5 - 最適化効果を確認する（Priority: P3）

**Goal**: 導入後30日または最初の完全請求期間について、見積りと実績を比較し、月額3,000円または20%差の見直し判断を残す。

**Independent Test**: 主要費用項目の見積額、実績額、差額、差率、原因、対応がすべて記録され、閾値超過時に再評価の担当と期限が決まっている。

### Implementation for User Story 5

- [ ] T064 [P] [US5] `specs/003-optimize-ecs-costs/contracts/cost-evaluation.md`をFR-005・FR-019とSC-008・SC-009へ同期し、実績比較の入力元と差率式を確認する
- [ ] T065 [US5] 導入後30日または最初の完全請求期間の主要費用項目を同一条件へ揃え、実績、差額、差率、原因候補を`specs/003-optimize-ecs-costs/cost-actual-review.md`に記録する
- [ ] T066 [US5] 月額3,000円超過または見積り20%超過の有無、再評価要否、対応責任者、期限、次回確認日を`specs/003-optimize-ecs-costs/cost-actual-review.md`に記録する
- [ ] T067 [US5] US5の費用証跡参照と最終判断を、秘密情報やAWSアカウントIDを除いて`specs/003-optimize-ecs-costs/validation-records.md`に追記する

**Checkpoint**: US5単独で、最適化効果と見直し判断を第三者が追跡できる。

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 001の既存機能を壊していないことと、003の全成功基準をまとめて検証する。

- [ ] T068 [P] 既存の認証・認可、PC一覧、PC登録、PC返却、ステータス更新、Gemini解析テストを実行し、回帰結果を`specs/003-optimize-ecs-costs/validation-records.md`に記録する
- [ ] T069 [P] `backend/lambda/tests`、外部Gemini実通信を除く`backend/ecs/tests`、`infrastructure/tests`、フロントエンド`npx tsc --noEmit`と`npm run build`、CDK synthを`specs/003-optimize-ecs-costs/quickstart.md`に従って実行する
- [ ] T070 FR-001〜FR-019とSC-001〜SC-009について、既存証跡を要件へマッピングし、不足分だけを再試験して`specs/003-optimize-ecs-costs/validation-records.md`に最終整理する
- [ ] T071 内部署名、±60秒境界、利用者認証併用、最大2世代・3段階ローテーション、7日境界、5分回収、旧所有者拒否、状態変更3ルート、部分成功0件のSecurity First証跡を`specs/003-optimize-ecs-costs/validation-records.md`で最終監査する
- [ ] T072 `specs/003-optimize-ecs-costs/quickstart.md`を通しで再実行し、既知制約、未実施の実環境項目、再実施手順を`specs/003-optimize-ecs-costs/validation-records.md`に記録する

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup（Phase 1）**: 依存なし。T002〜T006はT001と並行可能。
- **Foundational（Phase 2）**: Setup完了後。T008〜T010はT007と並行着手可能、T011は契約確認後、T012は実装後。
- **US1（Phase 3）**: Foundational完了後。ネットワーク設定と内部署名・秘密管理を一体で検証するMVP。
- **US2（Phase 4）**: Foundational完了後に実装可能。署名済みプロキシ統合と実環境停止試験はUS1完了後。
- **US3（Phase 5）**: US2のプロキシ受付と自動再送を利用するためUS2完了後。
- **US4（Phase 6）**: US3の世代・停止競合制御を停止ゲートへ利用するためUS3完了後。
- **US5（Phase 7）**: US1〜US4導入後、30日または最初の完全請求期間のデータ取得後。
- **Polish（Phase 8）**: リリース対象ストーリー完了後。費用実績待ちの場合、T068〜T069はUS4後に先行可能。

### User Story Dependencies

```text
Setup → Foundational → US1（設定是正・署名境界・MVP）
                   └→ US2（安全な再開・原子冪等性）→ US3（競合制御）→ US4（安全な停止）
US1〜US4導入 → 運用期間 → US5
US1〜US5 → Polish
```

- **US1（P1）**: NAT 0・初期0・通信維持・内部署名・秘密ローテーションを提供するSecurity First適合MVP。
- **US2（P1）**: US1の署名済み転送経路へ、自動再送と状態変更3ルートの原子冪等性を追加する。
- **US3（P1）**: US2の要求受付・再送経路に依存する。
- **US4（P2）**: US3の世代と停止競合対策に依存する。
- **US5（P3）**: 実装依存ではなく、US1〜US4導入後の請求データに依存する。

### Within Each User Story

1. テストタスクを先に実施し、現行実装で期待どおり失敗することを確認する。
2. 既存コードの対象メソッド・ルート・コンポーネントを修正する。
3. 新規内部モジュールは署名生成、署名検証、共通冪等性サービスだけに限定する。
4. ローカルテスト、型検査、build、synthを成功させる。
5. Independent Testを実施し、検証記録を残してから次のストーリーへ進む。

---

## Parallel Opportunities

### Setup / Foundation

```text
T002 用語更新 || T003 Lambda fixture || T004 ECS fixture || T005 API棚卸し || T006 quickstart確認
T008 API契約同期 || T009 TTL/CDKテスト || T010 Secret/IAM CDKテスト
```

### User Story 1

```text
T013 CDKコストテスト || T014 Lambda署名テスト || T015 ECS検証テスト || T016 ローテーションテスト
T017 通信検証スクリプト || T018 署名検証スクリプト
T019 インフラ設定 || T020 Lambda署名実装 || T022 ECS検証実装 || T024 コスト比較
```

### User Story 2

```text
T028 Lambdaプロキシテスト || T029 冪等境界テスト || T031 状態変更契約テスト
T034 冪等サービス実装 || T040 起動中UI拡張
```

### User Story 3 / 4 / 5 / Polish

```text
T046 同時起動テスト || T048 停止競合テスト
T055 活動追跡テスト || T056 アイドル境界テスト || T057 CDKスケジュールテスト
T064 費用契約同期
T068 業務回帰 || T069 全体ビルド・テスト
```

---

## Implementation Strategy

### MVP First（User Story 1）

1. Phase 1で既存実装、状態変更ルート、用語を固定する。
2. Phase 2で既存テーブル、API、Secrets Manager/IAMの最小拡張を確定する。
3. Phase 3でNAT 0、初期0、内部署名、±60秒、最大2世代ローテーションを実装する。
4. NAT 0、初期稼働0、public IP、必須4通信、署名不正拒否、3段階秘密切替を検証する。
5. **STOP and VALIDATE**: Security Firstを満たし、既存PC管理結果を変えず未使用時固定費を除去できたことをレビューする。

### Incremental Delivery

1. **US1**: NAT Gateway削除・初期稼働0・通信・署名境界・秘密ローテーション
2. **US2**: 既存起動フローへの自動再送・7日保持・5分回収・原子冪等性
3. **US3**: 既存ECSManagerへの起動ロック・停止競合対策
4. **US4**: 既存2時間停止への処理中フェンス追加
5. **US5**: 30日実績比較

### Validation Gates

- **US1 gate**: NAT 0、初期desired/running 0、public IP、必須4通信、署名不正時業務処理0、正当転送100%、旧秘密失効後100%拒否
- **US2 gate**: 対象3操作×5回が3分以内、状態変更3ルート重複0、7日境界、5分回収、旧所有者拒否、部分成功0
- **US3 gate**: 同時10件で起動更新1回、停止前後の競合操作が一回成功
- **US4 gate**: 2時間境界・処理中・異常記録が期待どおりで、条件成立後15分以内に停止
- **US5 gate**: 主要費用項目の差率100%記録、3,000円または20%超過時の判断あり

---

## Notes

- `[P]`はファイル競合と未完了依存がないタスクだけに付与している。
- `backend/lambda/src/main.py`、`backend/lambda/src/services/ecs_manager.py`、`backend/ecs/src/main.py`、`frontend/src/components/ecs-loading-state.tsx`は既存実装を修正し、代替ファイルを作らない。
- 新規外部ライブラリ、新しいデプロイ単位、ALB、キュー、専用DynamoDBテーブル、業務テーブルの冪等キー属性を追加しない。
- 実キー、AWSアカウントID、Authorization、署名、実PCデータをテスト、スクリプト、文書、ログへ保存しない。
- 外部Gemini実通信は通常のローカルテストから分離し、検証環境で非機密ダミーデータを用いる。
- 業務スキーマ変更が必要と判明した場合は推測で追加せず、コード変更前に001と003の`data-model.md`、該当契約を更新する。
- 各タスクまたは論理的な小グループ単位でコミットし、無関係なリファクタリングを含めない。
