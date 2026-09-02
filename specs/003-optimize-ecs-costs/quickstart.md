# Quickstart: ECSコスト最適化の検証ガイド

この文書は実装後に機能をエンドツーエンドで検証するための実行ガイドである。詳細な状態・項目は [data-model.md](./data-model.md)、HTTP契約は [contracts/runtime-api.md](./contracts/runtime-api.md)、費用記録は [contracts/cost-evaluation.md](./contracts/cost-evaluation.md) を参照する。

## 1. Prerequisites

- Windows PowerShell 7
- リポジトリ: `D:\workspace\pc_management_ledger`
- プロジェクトの `.venv` とインフラ依存関係がインストール済み
- Node.js/npm と `frontend/node_modules` が利用可能
- 検証環境用AWS認証情報（最小権限、実キーを文書やログへ貼らない）
- `ap-northeast-1` の検証スタック、既存のダミーUsers/PCデータ
- Secrets Manager の Gemini APIキーおよび内部プロキシ署名シークレット
- AWS CLI v2（実環境検証時）

環境確認:

```powershell
Set-Location 'D:\workspace\pc_management_ledger'
& '.\.venv\Scripts\python.exe' --version
node --version
npm --version
aws --version
```

## 2. Local validation

### 2.1 Lambda/ECS/CDK tests

実装後に追加されるテストを含め、外部Gemini実通信を要求しないテストだけを通常ゲートとして実行する。

```powershell
Set-Location 'D:\workspace\pc_management_ledger'

& '.\.venv\Scripts\python.exe' -m pytest 'backend\lambda\tests' -q
& '.\.venv\Scripts\python.exe' -m pytest 'backend\ecs\tests' -q --ignore='backend\ecs\tests\test_gemini_direct.py' --ignore='backend\ecs\tests\test-gemini-accuracy.py'
& '.\.venv\Scripts\python.exe' -m pytest 'infrastructure\tests' -q
```

期待結果:

- 起動ロック同時10件で `UpdateService(1)` が1回
- 2時間未満/以上、処理中、欠損、不正時刻の停止判定が契約どおり
- 停止競合で停止中止または再起動
- 同一 `Idempotency-Key` のPC登録・返却が1回だけ業務処理される
- CDKテンプレートに NAT Gateway と ALB がなく、ECS desired count が0、EventBridgeが15分間隔

### 2.2 Frontend type/build validation

```powershell
Set-Location 'D:\workspace\pc_management_ledger\frontend'
npx tsc --noEmit
npm run build
```

期待結果: 型エラーおよびbuildエラーがなく、一覧・登録・返却が共通再試行クライアントを利用する。

### 2.3 CDK synth

```powershell
Set-Location 'D:\workspace\pc_management_ledger\infrastructure'
& '..\.venv\Scripts\python.exe' 'app.py'
```

またはプロジェクトで利用可能なCDK CLIから `cdk synth` を実行する。

確認項目:

- `AWS::EC2::NatGateway` が0件
- `AWS::ElasticLoadBalancingV2::*` が0件
- ECS Service の `DesiredCount` が0
- ECSタスクがpublic subnetとpublic IPを使う
- タイムアウト判定ルールが15分間隔
- Lambda/ECSが同じ内部署名Secretを参照
- `ecs:UpdateService` 権限が対象サービスへ可能な限り限定

## 3. Deploy and initial-zero validation

デプロイコマンドは環境の既存運用手順に従う。実行直後に次を確認する。

```powershell
$Region = 'ap-northeast-1'
$Cluster = 'PCManagementCluster'
$Service = 'PCManagementService'

aws ecs describe-services `
  --region $Region `
  --cluster $Cluster `
  --services $Service `
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,status:status}'
```

期待結果:

```json
{
  "desired": 0,
  "running": 0,
  "pending": 0,
  "status": "ACTIVE"
}
```

失敗時は次の試験へ進まず、デプロイ処理が desired count を1へ戻す箇所を修正する。

## 4. Required connectivity validation

各試験前に desired/running count が0であることを確認し、停止状態から対象操作を開始する。検証IDを発行し、[cost-evaluation.md](./contracts/cost-evaluation.md) の通信検証表へ記録する。

### 4.1 ECR and task start

1. PC管理操作を1回開始する。
2. UIに「バックエンドを起動しています」が表示されることを確認する。
3. ECS service eventsでイメージpullとタスク起動を確認する。
4. running countが1になることを確認する。

```powershell
aws ecs describe-services --region $Region --cluster $Cluster --services $Service `
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,events:events[0:5]}'
```

### 4.2 CloudWatch Logs

起動したタスクのログストリームに検証IDが出力されることを確認する。秘密値や完全な要求本文が記録されていないことも確認する。

### 4.3 DynamoDB

検証用操作でダミー項目のread/writeを行い、成功後に後片付けする。実運用PCやUserを検証用途に変更しない。

### 4.4 Gemini API

非機密のダミースペック文字列を `POST /api/pcs/parse-specs` へ送り、構造化応答を確認する。APIキーを出力しない。

期待結果: ECR、CloudWatch Logs、DynamoDB、Gemini API の4項目すべてPASS。

## 5. Cold-start operation acceptance

参照系操作 `GET /api/pcs`、PC登録、PC返却を各5回、毎回停止状態から実施する（合計15回）。

各回で記録する項目:

- 検証ID、操作、開始時刻、完了時刻、所要秒数
- 初期 desired/running count = 0
- 起動中表示の有無
- 自動再送回数と同一 `Idempotency-Key` の維持
- 最終HTTP結果と業務結果
- PC登録の新規PC数、PC返却の返却記録数
- `Idempotency-Replayed` の有無

期待結果:

- 全15回が利用者の手動更新なしで3分以内に成功
- PC登録5回とPC返却5回で各操作の業務結果が1件ずつ
- 起動中応答と通常障害をUIが区別
- 3分を意図的に超えるテストでは自動再送を終了し、安全な再試行ボタンを表示

## 6. Concurrent-start validation

停止状態で、同一または独立ブラウザから10件を同時送信する。自動化する場合も各利用操作の `Idempotency-Key` は別々とする。

確認:

1. 10件すべてが `starting` または通常成功の一貫した応答を受ける。
2. 稼働制御項目の世代遷移が1回の起動に集約される。
3. CloudTrail/モック監査で `UpdateService(desiredCount=1)` が1回。
4. 最終 running count が1（10ではない）。

## 7. Idempotency validation

PC登録とPC返却について次を実施する。

1. 1つの要求本文と `Idempotency-Key` を固定する。
2. 同じ要求を起動中および処理中に複数回送る。
3. 成功後にも同じ要求を再送する。
4. 同じキーで本文だけを変更して送る。

期待結果:

- 処理中は `409 processing` と `Retry-After`
- 成功後は元と同じ結果、`Idempotency-Replayed: true`
- 業務項目・返却記録は1件だけ
- 本文変更は `409 idempotency_conflict`、業務変更なし

## 8. Idle and stop-race validation

実時間2時間を毎回待たず、テスト環境の `SystemActivity` を境界値へ設定して判定Lambdaを手動起動する。時刻更新は検証項目だけに限定する。

必須ケース:

| Case | lastActivityAt | inFlightCount | Expected |
|---|---|---:|---|
| Before boundary | now - 1:59:59 | 0 | running維持 |
| At boundary | now - 2:00:00 | 0 | 次回判定で停止 |
| Processing | now - 3:00:00 | 1 | running維持 |
| Missing | absent | 0 | running維持 + warning |
| Invalid | invalid/future | 0 | running維持 + warning |

停止競合:

1. 停止判定が `STOPPING` を取得する直前に新規操作を送るケースを再現し、停止が中止されることを確認。
2. `UpdateService(0)` 実行後に新規操作を送るケースを再現し、停止完了後に自動再起動して元操作が1回成功することを確認。

自動停止後、`desired=0` かつ `running=0` を確認する。境界成立から停止まで15分以内であることを記録する。

## 9. Security validation

- ECS公開IPへ内部署名なしで直接アクセスし `403` となること
- 期限切れ時刻、改変本文、不正署名で `403` となること
- 正しい内部署名でも利用者認証・認可違反が従来どおり拒否されること
- ログにAuthorization、HMAC署名、Gemini APIキー、Secrets Manager値がないこと
- セキュリティグループとIAMが計画以上に広がっていないこと

## 10. Cost validation

[cost-evaluation.md](./contracts/cost-evaluation.md) の形式で以下を実施する。

1. 基準日の東京リージョン公式単価と為替前提を取得。
2. 現行案、採用案、Endpoint案を同じ730時間・通信量で比較。
3. 採用案の月額が3,000円以下か確認。超過時は理由と追加対応を記録。
4. 導入後30日または最初の完全請求期間にCost Explorer/請求実績と比較。
5. 3,000円超または見積り20%超過なら再評価判断と担当・期限を記録。

## 11. Completion criteria

- ローカルテスト、型検査、build、CDK synthが成功
- NAT Gateway 0、ALB 0、初期/停止後タスク0
- 必須4通信が新規タスクで成功
- 対象3操作×5回が全件3分以内、自動再送、一回処理
- 同時10件が起動1回へ集約
- 2時間境界、処理中、異常データ、停止競合が契約どおり
- 内部署名と既存認証・認可が有効
- 比較、採用理由、却下理由、実績差異、見直し判断が記録済み