# Cost Evaluation Contract - 構成比較・採用・実績確認

## 1. 目的

FR-001〜FR-006、FR-017およびSC-001〜SC-003、SC-008を再現可能な記録として残すための必須フォーマットを定義する。単価は固定値としてこの契約に埋め込まず、評価実施日のAWS公式情報から取得する。

## 2. 共通評価条件

各評価記録の先頭に次を必ず記載する。

| Field | Required value / rule |
|---|---|
| 価格基準日 | `YYYY-MM-DD` |
| リージョン | `ap-northeast-1` |
| 月間時間 | 730時間、異なる場合は理由 |
| AWS単価通貨 | USD等、公式表示通貨 |
| 円換算レート | 数値、取得日、取得元 |
| 利用者規模 | 20〜30名 |
| ECSサイズ | 0.25 vCPU / 0.5 GiB（変更時は明記） |
| ECS月間稼働時間 | 低・標準・高シナリオまたは実測 |
| 月間通信量 | Gemini、ECR、CloudWatch Logs、DynamoDB、その他に分解 |
| 価格根拠 | AWS Pricing CalculatorまたはAWS公式価格URL |
| 含有項目 | NAT、public IPv4、Fargate CPU/Memory、Endpoints、API Gateway、Lambda、DynamoDB、Logs等 |
| 除外項目 | 金額0または共通で比較対象外とした項目も理由を明記 |

## 3. 候補比較表

最低限、候補Aと候補Bを記録する。候補Cは却下案の価格比較に推奨する。

| Candidate | Network | ECS policy | Gemini | DynamoDB | ECR pull | Logs | Fixed cost/month | Usage cost/month | Total JPY | Advantages | Constraints/Risks | Decision |
|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|
| A 現行 | NAT Gateway 1、public task IP | desired 1常時 | 未/可/否 + evidence | 同左 | 同左 | 同左 | 実測 | 実測 | 実測 | 記録 | 記録 | REJECTED/ADOPTED |
| B 採用候補 | NAT 0、public subnet + task public IP | deploy 0、要求時1、2h後0 | 同上 | 同上 | 同上 | 同上 | 実測 | 実測 | 実測 | 記録 | 記録 | ADOPTED/REJECTED |
| C Endpoint案 | private subnet + endpoints + internet egress案 | 0/1 | 同上 | 同上 | 同上 | 同上 | 実測 | 実測 | 実測 | 記録 | 記録 | REJECTED/ADOPTED |

通信欄は単なる「可」ではなく、検証IDまたはAWS公式仕様への参照を含める。

## 4. 費用明細

候補ごとに次の形式で、数量と式を省略せず記録する。

| Service/Item | Unit price | Unit | Quantity/month | Formula | Monthly USD | Source |
|---|---:|---|---:|---|---:|---|
| NAT Gateway hours | 取得値 | gateway-hour | 730等 | unit × quantity | 計算値 | URL/Calculator |
| NAT data processing | 取得値 | GB | 通信量 | unit × quantity | 計算値 | URL/Calculator |
| Public IPv4 | 取得値 | IP-hour | ECS稼働時間 | unit × quantity | 計算値 | URL/Calculator |
| Fargate vCPU | 取得値 | vCPU-hour/second | vCPU × 稼働時間 | unit × quantity | 計算値 | URL/Calculator |
| Fargate memory | 取得値 | GB-hour/second | GiB × 稼働時間 | unit × quantity | 計算値 | URL/Calculator |
| Interface endpoint | 取得値 | endpoint-AZ-hour | endpoint × AZ × 730 | unit × quantity | 計算値 | URL/Calculator |
| API/Lambda/DynamoDB/Logs等 | 取得値 | 各サービス単位 | 利用量 | unit × quantity | 計算値 | URL/Calculator |

円換算:

```text
totalJpy = round(totalUsd × exchangeRate)
```

## 5. 採用判断

```markdown
### Adoption Decision

- Decision date:
- Approver role/id:
- Adopted candidate:
- Estimated monthly total (JPY):
- Meets JPY 3,000 target: Yes/No
- Adoption reasons:
  1.
- Rejected candidates and reasons:
  1.
- Known risks and mitigations:
  1.
- Review triggers:
  - 合計実績が月額3,000円を超過
  - 合計または主要明細が見積りを20%超過
  - Gemini/DynamoDB/ECR/Logsの必須通信に失敗
  - 3分以内の起動完了率または一回処理要件を未達
  - 利用規模・稼働時間・AWS価格・為替が大幅変化
```

## 6. 通信検証記録

新規タスク起動を含め、以下4行を必須とする。

| Validation ID | Destination | Operation | New task confirmed | Result | Evidence | Failure reason |
|---|---|---|---|---|---|---|
|  | Gemini API | 非機密ダミーテキストの解析 | Yes/No | PASS/FAIL | 参照 |  |
|  | DynamoDB | テスト項目のread/write/delete | Yes/No | PASS/FAIL | 参照 |  |
|  | ECR | desired 0からのimage pull/task start | Yes/No | PASS/FAIL | 参照 |  |
|  | CloudWatch Logs | 一意validation IDの出力確認 | Yes/No | PASS/FAIL | 参照 |  |

APIキー、認証トークン、完全なPC実データは証跡へ含めない。

## 7. 導入後実績比較

対象期間は導入後連続30日または最初の完全な請求期間とする。

| Service/Item | Estimated JPY | Actual JPY | Difference JPY | Difference % | Cause hypothesis | Action |
|---|---:|---:|---:|---:|---|---|
|  |  |  | `actual-estimated` | 定義式 |  |  |

差率:

```text
differencePercent =
  estimated > 0 ? ((actual - estimated) / estimated) × 100
                : (actual > 0 ? "NEW_COST" : 0)
```

### Mandatory conclusion

- Actual total JPY:
- Above JPY 3,000: Yes/No
- More than 20% above estimate: Yes/No
- Re-evaluation required: Yes/No
- Decision and owner:
- Next review date:

## 8. 証跡の品質条件

- AWSアカウントID、アクセスキー、APIキー、Authorization値はマスクする。
- Cost Explorer、請求書、Calculatorの取得日時とフィルター条件を残す。
- 単価取得元と請求実績を混同しない。
- 見積りと実績でサービス名・期間・通貨・税込/税別条件を揃える。
- 検証失敗を空欄や0円として扱わず、失敗理由と再実施判断を記録する。