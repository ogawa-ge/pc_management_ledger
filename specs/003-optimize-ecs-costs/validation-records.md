# Validation Records: 既存ECS運用のコスト最適化と安全性補強

**対象フィーチャー**: `003-optimize-ecs-costs`
**記録開始日**: 2026-09-25

## 1. 001由来の既存実装ベースライン

003では次の既存実装を再作成せず、設定是正と安全対策を差分追加する。

| 領域 | 既存実装 | 主なファイル | 003の回帰基準 |
|---|---|---|---|
| ECS起動・停止 | desired countを1/0へ更新し、状態取得と2時間アイドル判定を行う | `backend/lambda/src/services/ecs_manager.py` | 起動、停止、状態取得、2時間判定の既存結果を維持する |
| Lambdaプロキシ | ECSの公開IPを取得し、停止時は起動要求後に`503 starting`を返す | `backend/lambda/src/main.py` | 停止時の既存起動経路とECSへの要求転送を維持する |
| 起動中UI | ECSコールドスタート中のオーバーレイを表示する | `frontend/src/components/ecs-loading-state.tsx` | 起動中表示を維持し、自動再送状態だけを拡張する |
| PC管理 | 一覧、登録、返却、ステータス更新、Gemini解析を提供する | `backend/ecs/src/main.py`, `backend/ecs/src/services/pc_service.py` | 認証・認可と業務上の結果を変更しない |
| 認証・認可 | Bearer値から既存Usersを解決し、管理者操作を制限する | `backend/ecs/src/main.py` | 内部署名を追加しても利用者認証・認可を代替しない |

## 2. 変更前構成値

2026-09-25時点の変更前ベースラインは次のとおり。

| 設定 | 変更前 | 記録元 |
|---|---:|---|
| VPC NAT Gateway数 | `nat_gateways=1` | `infrastructure/stacks/ecs_stack.py` |
| ECS初期稼働数 | `desired_count=1` | `infrastructure/stacks/ecs_stack.py` |
| ECS public IP | `assign_public_ip=True` | `infrastructure/stacks/ecs_stack.py` |
| ECS subnet | `SubnetType.PUBLIC` | `infrastructure/stacks/ecs_stack.py` |
| アイドル判定間隔 | 1時間 | `infrastructure/stacks/lambda_stack.py` |

## 3. 共通回帰基準

- 既存の認証・認可違反は従来どおり拒否される。
- PC一覧、PC登録、PC返却、ステータス更新の成功時レスポンスと業務結果を維持する。
- Geminiスペック抽出の入力・出力契約を変更しない。
- 停止中は既存の起動処理を使用し、別の起動実装を追加しない。
- 自動停止は既存の2時間方針を維持し、処理中および異常記録時は停止しない。
- 秘密値、Authorization、HMAC署名、AWSアカウントID、実PCデータを記録しない。

## 4. 検証記録テンプレート

各ローカル試験・AWS検証は次の形式で追記する。

### `<validationId>`: `<scenario>`

- **実施日時**: `<ISO 8601 UTC>`
- **環境**: `<local/test/staging>`
- **関連タスク**: `<Txxx>`
- **事前条件**:
  - `<condition>`
- **期待結果**: `<expected>`
- **実結果**: `<actual>`
- **所要秒数**: `<durationSeconds or N/A>`
- **結果**: `<PASS/FAIL/NOT RUN>`
- **失敗理由**: `<reason or N/A>`
- **証跡参照**: `<test command, sanitized log, CloudWatch reference>`
- **秘密情報確認**: 実キー、Authorization、署名、秘密値、AWSアカウントIDを含まない

## 5. 実施記録

### `local-phase1-route-inventory`: 状態変更ルート棚卸し

- **実施日時**: 2026-09-25
- **環境**: local
- **関連タスク**: T001〜T006
- **事前条件**: FastAPIの現行ルートを変更していない
- **期待結果**: 永続状態変更3ルートと非永続`parse-specs`だけが明示分類される
- **実結果**: 棚卸しテスト3件が成功した
- **所要秒数**: N/A
- **結果**: PASS
- **失敗理由**: N/A
- **証跡参照**: `.venv\Scripts\python.exe -m pytest backend\ecs\tests\test_state_changing_route_inventory.py -q`
- **秘密情報確認**: 実キー、Authorization、署名、秘密値、AWSアカウントIDを含まない

### `local-phase1-existing-tests`: 既存ECSテスト確認

- **実施日時**: 2026-09-25
- **環境**: local
- **関連タスク**: T003〜T006
- **事前条件**: 外部Gemini実通信テストを除外
- **期待結果**: 通常のECSテストが収集・実行できる
- **実結果**: 既存テストの旧ファイル名`gemini-service.py`参照を現行`gemini_service.py`へ是正した
- **所要秒数**: N/A
- **結果**: PASS（再実行結果は後続記録へ追記）
- **失敗理由**: N/A
- **証跡参照**: `backend/ecs/tests/test_gemini_api_key.py`
- **秘密情報確認**: 実キー、Authorization、署名、秘密値、AWSアカウントIDを含まない

### `local-phase2-foundation`: TTL・Secret参照・IAM境界

- **実施日時**: 2026-09-25
- **環境**: local
- **関連タスク**: T007〜T012
- **事前条件**: CDKスタックをローカル合成可能
- **期待結果**: `SystemActivity`だけに`expiresAt` TTLがあり、Lambda/ECSが同一内部署名Secretを参照し、秘密値を通常環境変数・出力へ含めず、書込み権限を持たない
- **実結果**: 対象CDK assertion 4件が成功した
- **所要秒数**: 78.13
- **結果**: PASS
- **失敗理由**: N/A
- **証跡参照**: `.venv\Scripts\python.exe -m pytest infrastructure\tests\unit\test_infrastructure_stack.py infrastructure\tests\unit\test_internal_proxy_secret.py -q`
- **秘密情報確認**: 実キー、Authorization、署名、秘密値、AWSアカウントIDを含まない

### `local-us1-security-cost`: NAT 0・初期0・内部署名・コスト比較

- **実施日時**: 2026-09-25
- **環境**: local
- **関連タスク**: T013〜T025
- **事前条件**: 外部Gemini実通信を除外し、Secrets Managerはモックを使用
- **期待結果**: NAT 0、DesiredCount 0、public IP維持、ALB 0、署名改ざん拒否、±60秒境界、最大2世代、秘密値非露出
- **実結果**: Lambda/ECSテスト30件、CDK assertion 6件、CDK synthが成功。東京リージョン公開単価で現行・採用・Endpoint案を比較した
- **所要秒数**: N/A
- **結果**: PASS（AWS通信・3段階実ローテーションは未実施）
- **失敗理由**: N/A
- **証跡参照**: `backend/lambda/tests`, `backend/ecs/tests`, `infrastructure/tests`, `cost-estimate.md`
- **秘密情報確認**: 実キー、Authorization、署名、秘密値、AWSアカウントIDを含まない

### `local-us2-idempotent-retry`: 自動再送・冪等境界・原子状態変更

- **実施日時**: 2026-09-25
- **環境**: local
- **関連タスク**: T028〜T044
- **事前条件**:
  - DynamoDB、ECS、Secrets Manager境界はモックを使用
  - `backend/ecs`と`backend/lambda`は同名`src`パッケージのため別プロセスで実行
  - AWS実環境へのデプロイおよび反復操作は実施しない
- **期待結果**: `503 starting`と`409 processing`だけを同一キーで最大180秒再送し、登録・返却・ステータス更新が業務項目、履歴項目、冪等成功記録を同一トランザクションで確定する。7日再利用、5分回収、旧所有者拒否、成功再生、内容競合、部分成功0件を確認できる
- **実結果**:
  - ECSテスト56件が成功した。冪等サービス境界、3ルートの成功再生/競合/処理中、UUIDキー必須、camelCase項目、3種類の`TransactWriteItems`、現所有者・開始時刻条件、失敗時に個別書込みへフォールバックしないことを確認した
  - 登録・返却・ステータス更新を各1組ずつ、同一`Idempotency-Key`・同一本文で初回成功後に再送し、業務関数の呼出しが各1回だけで、保存済み成功結果と`Idempotency-Replayed: true`が返ることを確認した。同じキーで本文だけを変更した要求は、3操作すべて`409 idempotency_conflict`となり、業務関数の追加呼出しは0件だった
  - 登録3項目、返却4項目、ステータス更新3項目の合計10トランザクション項目へ位置ごとに障害を注入し、PC、返却記録、利用履歴、冪等成功記録のスナップショットが全ケースで不変となることを確認した
  - 5分停滞回収後を模して冪等記録を新`ownerRequestId`・新`startedAt`へ変更し、旧所有者による登録・返却・ステータス更新の確定をすべて所有者条件で拒否し、業務変更0件となることを確認した
  - Lambdaテスト2件が成功し、停止時の`503`、`status=starting`、`Retry-After`、`Cache-Control=no-store`を確認した
  - infrastructure assertion 6件が成功し、ReturnRecordsを含むECSタスク権限・環境変数と既存コスト/署名境界を確認した
  - CDK synthが成功した。既存の`VpcProps#cidr`非推奨警告のみ発生した
  - `npx tsc --noEmit`と`npm run build`が成功し、一覧・登録・返却画面と共通再送クライアントを型検査・production buildで確認した
  - 登録画面は`parseSpecs`結果のJSON再入力を廃止し、検証後も元の端末テキストを登録APIへ渡すよう契約を是正した
- **所要秒数**: infrastructure assertion 83.66秒、その他N/A
- **結果**: PASS。T031、T032、T044のローカル契約・原子性・総合検証は完了。AWS実環境反復試験T045は未実施
- **失敗理由**: N/A
- **証跡参照**:
  - `.venv\Scripts\python.exe -m pytest backend\ecs\tests -q --ignore=backend\ecs\tests\test_gemini_direct.py --ignore=backend\ecs\tests\test-gemini-accuracy.py` → 56 passed
  - `.venv\Scripts\python.exe -m pytest backend\ecs\tests\test_idempotent_pc_operations.py backend\ecs\tests\test_idempotent_pc_transactions.py backend\ecs\tests\test_idempotency_service.py -q` → 24 passed
  - `.venv\Scripts\python.exe -m pytest backend\lambda\tests -q` → 2 passed
  - `.venv\Scripts\python.exe -m pytest infrastructure\tests -q` → 6 passed
  - `infrastructure: ..\.venv\Scripts\python.exe app.py` → synth completed
  - `frontend: npx tsc --noEmit; npm run build` → exit code 0
- **秘密情報確認**: 実キー、Authorization、署名、秘密値、AWSアカウントIDを含まない