# Cost Estimate: ECSコスト最適化

**価格取得日**: 2026-09-25
**リージョン**: Asia Pacific (Tokyo) / `ap-northeast-1`
**通貨**: USD（比較表示は評価シナリオとして `1 USD = 150 JPY`）
**月間時間**: 730時間

## 1. 価格根拠

AWS公式価格ページおよびAWS Price List APIの公開単価を同日に確認した。価格は将来変動するため、再評価時は同じusage typeを再取得する。

| 項目 | Usage type / 条件 | 単価 |
|---|---|---:|
| NAT Gateway時間 | `APN1-NatGateway-Hours` | USD 0.062 / 時 |
| NAT Gateway処理量 | `APN1-NatGateway-Bytes` | USD 0.062 / GB |
| Fargate x86 vCPU | `APN1-Fargate-vCPU-Hours:perCPU` | USD 0.05056 / vCPU時 |
| Fargate x86メモリ | `APN1-Fargate-GB-Hours` | USD 0.00553 / GB時 |
| 使用中public IPv4 | `APN1-PublicIPv4:InUseAddress` | USD 0.005 / 時 |
| Interface Endpoint時間 | `APN1-VpcEndpoint-Hours` | USD 0.014 / endpoint時 |
| Interface Endpoint処理量 | 最初の1PB/月 | USD 0.01 / GB |

## 2. 共通条件

- ECSタスク: 0.25 vCPU、0.5 GB、Linux x86。
- 比較用通信量: 月10 GB。実請求レビューでは実測値へ置換する。
- 採用案の標準実稼働: 月60時間。低利用20時間、高利用180時間も感度確認する。
- 現行案はNAT Gateway 1台、ECSタスク1件とpublic IPv4を730時間維持する。
- Endpoint案は2 AZでECR API、ECR DKR、CloudWatch Logs、Secrets Managerの4 Interface Endpointを常設する仮定。DynamoDB Gateway Endpoint自体の時間料金は含めない。Gemini向けインターネット出口を別途解決できないため、費用以前に要件未達である。
- API Gateway、Lambda、DynamoDB、CloudWatch Logs保存量、ECR保存量、インターネット転送料は全案に共通または利用量依存のため、この固定費比較から分離する。実績レビューでは主要費用項目として確認する。

## 3. 計算式

タスク1時間のFargate料金:

```text
(0.25 × 0.05056) + (0.5 × 0.00553) = USD 0.015405 / 時
```

| 候補 | 月額計算（USD） | 月額USD | 150円/USD換算 | 判定 |
|---|---|---:|---:|---|
| 現行: NAT 1 + ECS常時1 | NAT `0.062×730` + Fargate `0.015405×730` + IPv4 `0.005×730` + NAT処理 `0.062×10` | 60.77565 | 約9,116円 | 却下 |
| 採用: NAT 0 + ECS 60時間 | Fargate `0.015405×60` + IPv4 `0.005×60` | 1.22430 | 約184円 | 採用 |
| 採用・低利用20時間 | Fargate `0.015405×20` + IPv4 `0.005×20` | 0.40810 | 約61円 | 感度確認 |
| 採用・高利用180時間 | Fargate `0.015405×180` + IPv4 `0.005×180` | 3.67290 | 約551円 | 目標内 |
| Endpoint案 | 4 endpoints × 2 AZ × `0.014×730` + `0.01×10` | 81.86000 | 約12,279円 | 却下 |

## 4. 採否

**採用**: public subnet + 稼働時public IPv4、NAT Gateway 0、ECS初期0・利用時1。

理由:

1. 標準・高利用シナリオとも月額3,000円目標を十分下回る。
2. Gemini APIを含むインターネット送信を維持できる。
3. NAT Gatewayと複数Interface Endpointの時間固定費を除去できる。
4. 既存のpublic subnet、`assign_public_ip=True`、Lambda起動経路を維持する最小変更である。

既知リスクと緩和策:

- 公開IP上のECSはネットワーク境界だけに依存せず、LambdaのHMAC内部署名と既存利用者認証を併用する。
- public IPv4、Fargate、通信単価の変更時はPrice List APIのusage typeを再取得する。
- 実稼働時間、ログ量、ECR pull量が想定を超え、月額3,000円または見積り20%を超過した場合は、アイドル時間、起動回数、ログ保持、ARM64適合性を再評価する。