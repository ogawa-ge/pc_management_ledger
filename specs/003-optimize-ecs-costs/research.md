# Phase 0: Research - NAT GatewayとECS稼働数のコスト最適化

**調査基準日**: 2026-09-02  
**対象リージョン**: `ap-northeast-1`（東京）

## 1. NAT Gatewayを常設しないネットワーク

### Decision

ECS Fargate タスクを明示的なパブリックサブネットに配置し、稼働時のみパブリック IPv4 を割り当てる。VPC の NAT Gateway 数を 0 とし、ALB と有料の Interface VPC Endpoint は追加しない。

### Rationale

- AWS公式の Fargate networking では、パブリックサブネットのタスクENIへパブリックIPを付与すればインターネットへの経路を持てる。
- 現行 `ecs_stack.py` は既に `assign_public_ip=True` と `PUBLIC` サブネットを指定しており、NAT Gateway は ECS の送信通信に使われていない可能性が高い。
- Gemini API はインターネット上の外部サービスであり、AWS向けVPC Endpointだけでは通信を完結できない。
- ECRイメージ取得、Secrets Manager、CloudWatch Logs、DynamoDB は、タスク実行/タスクロールとパブリック経路で利用できる。4通信先は新規タスク起動を含む実環境試験で確認する。
- Interface VPC Endpoint はAZごとの時間固定費を持つため、低頻度・小規模環境では NAT 削減後の目標に逆行しやすい。

### Alternatives considered

1. **現行 NAT Gateway 1台を維持**: 安定したプライベート送信経路だが、時間固定費とデータ処理費が月額目標を圧迫するため却下。
2. **プライベートサブネット + ECR/Logs/Secrets Manager Interface Endpoint + DynamoDB Gateway Endpoint**: AWS内通信は私設化できるが、Gemini向けインターネット出口が別途必要で、複数Interface Endpointの固定費も生じるため却下。
3. **NAT Instance**: 固定費を下げられる可能性はあるが、パッチ、可用性、経路監視の運用負荷が小規模環境に見合わないため却下。
4. **IPv6-only + Egress-only Internet Gateway**: IPv4依存先、ECR endpoint、既存実装の適合確認が増え、Issueの最小変更範囲を超えるため今回は却下。将来の見直し候補とする。

## 2. ECSを0から単一起動する方式

### Decision

ECS Service の `desired_count` をデプロイ時 0 にし、Lambda が `SystemActivity` の稼働制御項目を DynamoDB 条件付き更新して起動所有権を取得した場合だけ `UpdateService(desiredCount=1)` を呼ぶ。他の同時要求は起動中応答を返す。

### Rationale

- ECS `UpdateService` は `desiredCount` を変更できるが、同時10件を「起動要求1回」に集約するアプリケーション上の保証はしない。
- DynamoDB条件付き更新で `STOPPED/RUNNING -> STARTING` の遷移所有者を1件に限定できる。
- Application Auto Scaling の min capacity 0 も可能だが、CPU/Memoryメトリクスはタスク0では通常の要求到着を表せない。今回はAPI要求が明確な起動シグナルなので、Lambda制御が単純で追跡しやすい。
- 起動中の要求はAPI Gateway/Lambdaで即時応答し、Lambdaの30秒上限内で3分間待機しない。

### Alternatives considered

1. **全要求から `UpdateService(1)`**: 最終 desired count は1でも、SC-005の起動要求1回を証明できないため却下。
2. **Application Auto Scalingのみ**: タスク0時の要求メトリクス生成と遅延制御が複雑なため却下。
3. **SQSで要求を保持**: 強い非同期性を得られるが、既存同期APIの全面変更と新規サービスが必要なため却下。
4. **Step Functions**: 起動オーケストレーションには使えるが、固定ワークフロー追加が条件付き更新より複雑なため却下。

## 3. 元操作の自動再送と一回処理

### Decision

フロントエンドの共通APIクライアントが操作ごとに UUID の `Idempotency-Key` を生成し、起動中応答の `Retry-After` に従って同じメソッド・パス・本文・キーを最大3分間自動再送する。ECS は状態変更操作のキーを `SystemActivity` に条件付き登録し、同じ要求の処理中・完了結果を再利用する。

### Rationale

- Lambdaは30秒タイムアウトであり、起動完了まで元HTTP接続を保持できない。
- ブラウザ側で元のクロージャと本文を保持すれば、手動更新なしで自動再送できる。
- PC登録は自動採番、PC返却は記録作成を伴い、単純な再POSTでは重複し得る。キー単位の処理権取得と完了結果保存が必要。
- GETは自然に再実行可能だが、同じ再試行基盤を使用して利用体験を統一する。
- 完了結果はDynamoDBの項目上限を超えない小さなJSONのみ保存し、TTLで期限切れにする。状態変更の業務書込みと成功記録は DynamoDB `TransactWriteItems` で原子的に確定する。

### Alternatives considered

1. **フロントエンドだけで再送**: 起動体験は満たすが状態変更の一回処理を保証できないため却下。
2. **Lambdaが要求本文をキュー保存して後送**: ブラウザ切断に強いが、認証コンテキスト、応答取得、DLQを含む大幅な非同期API化になるため却下。
3. **業務キーだけで重複判定**: 正当な連続登録や再返却との区別が曖昧なため却下。

## 4. アクティビティと処理中の停止防止

### Decision

Lambdaが対象操作の受付時に `lastAcceptedAt` と状態世代を更新し、ECSへの転送直前に `inFlightCount` を原子的に増やす。成功応答時に `lastActivityAt` を完了時刻へ更新し、`inFlightCount` を減らす。失敗時も件数は減らすが成功完了時刻は更新しない。停止判定は `inFlightCount=0`、状態がRUNNING、最終時刻が正常、2時間以上経過の全条件を満たす場合だけ実行する。

### Rationale

- 受付と成功完了を記録する FR-012 と、処理中は停止しない FR-012a を分けて表現できる。
- 欠損、不正時刻、負の件数では停止せず警告ログを残す fail-open が FR-015 に適合する。
- EventBridgeを15分間隔にすれば、2時間成立後15分以内のSC-006を満たせる。

### Alternatives considered

1. **最終受付時刻だけ**: 長時間処理が2時間を超えた場合の停止防止を表せないため却下。
2. **CloudWatchアクセスログの最終時刻**: 集計遅延と検索費用があり、処理中状態を原子的に扱えないため却下。
3. **ECS CPU使用率**: タスク0からの起動契機と業務操作の成功完了を表せないため却下。

## 5. 停止処理との競合

### Decision

稼働制御項目に単調増加する `generation` を持たせる。停止判定は読んだ世代を条件に `RUNNING -> STOPPING` を取得して `desiredCount=0` を設定する。新規操作は世代を進めて `STARTING` とし `desiredCount=1` を要求する。停止側は更新後に世代を再読し、変化していれば `desiredCount=1` を再設定して停止完了後の再起動を保証する。

### Rationale

- DynamoDBの状態変更順とECS API到達順が逆転する競合にも、停止側の事後再確認で対応できる。
- 停止開始前なら条件更新失敗で停止を中止し、開始後なら再起動するという FR-014a の二段階を実現できる。

### Alternatives considered

1. **状態フラグのみ**: ECS APIのネットワーク順序逆転を検出できないため却下。
2. **分散ロックを長時間保持**: 障害時のロック回収と起動遅延が増えるため却下。

## 6. Lambdaから公開ECSへの境界防御

### Decision

ALBを追加せず既存の公開IPプロキシを維持する代わりに、Lambdaが Secrets Manager の共有シークレットを用いて、HTTPメソッド、パス、本文ハッシュ、要求ID、時刻をHMAC署名する。ECSは署名と短い時刻窓を検証し、不正・期限切れ要求を拒否する。利用者の認証・認可ヘッダーは従来どおり別途検証する。

### Rationale

- LambdaはVPC外であり、ECSへプライベートIP接続するにはVPC接続とAWS API/Gemini向け出口設計が追加で必要になる。
- 現行セキュリティグループは80番を全IPv4へ公開しているため、ネットワーク制限だけでなくアプリケーション層の内部呼出し認証が必要。
- 実キーはコードや文書に保存せず、Secrets Manager参照とする。

### Alternatives considered

1. **ALB/API Gateway VPC Link/NLB**: 固定費と構成要素が増え、憲章のALB回避・低コスト方針に反するため却下。
2. **送信元IPによるSG制限**: 非VPC Lambdaの安定した送信元IPを前提にできないため却下。
3. **署名なしで既存認証のみ**: 未認証エンドポイントや認証実装漏れへの多層防御がないため却下。

## 7. ARM64移行

### Decision

今回の必須採用構成には含めず、x86_64を維持する。ARM64は、依存パッケージとDockerイメージを実環境同等にビルド・テストし、起動時間と費用を比較できた時点の見直し候補とする。

### Rationale

- FargateはARM64をサポートするが、タスク定義の runtime platform とコンテナイメージのアーキテクチャを一致させる必要がある。
- 本Issueの主要削減要因はNAT固定費と待機中タスク費であり、初期0化後の低い稼働時間ではARM移行の絶対効果が小さい。
- 現在のCDK出力にはx86_64向けPythonネイティブ依存物が見られ、検証なしの変更は通信・起動試験を危険にする。

### Alternatives considered

1. **即時ARM64化**: 追加削減は期待できるが、互換性検証を同時に持ち込むため却下。
2. **multi-arch image**: 将来の切替には有効だが、現行 `from_asset` のビルド経路整備が別作業になるため保留。

## 8. コスト比較と価格の扱い

### Decision

現行案と採用案を同じ利用条件で比較し、単価は実装・検証時点の AWS Pricing Calculator、AWS公式価格ページ、Cost Explorer/請求実績から取得する。文書には基準日、リージョン、USD単価、為替、稼働時間、通信量、含有/除外項目、計算式を保存し、変動する価格を本計画で断定しない。

### Rationale

- NAT Gatewayは時間料金と処理データ量料金、パブリックIPv4は使用時間、FargateはvCPU・メモリの実行時間、Interface EndpointはAZごとの時間とデータ処理量が主要因である。
- 価格はリージョンと時点で変わり、Webページの表示も選択条件に依存する。再現可能性には単価そのものと取得元の保存が必要。
- 採用案ではNAT固定費が0、Fargate待機費が0となり、主な残存費用は実稼働Fargate、稼働中パブリックIPv4、API/Lambda/DynamoDB/Logs等の従量費となる。

### Common estimation conditions

- 1か月: 730時間
- ECS: 0.25 vCPU、0.5 GiB、通常待機0、実稼働時間は低/標準/高の3シナリオで記録
- 通信量: Gemini、ECR pull、Logs、DynamoDBを項目別に記録
- 通貨: AWS単価はUSD、円換算レートと取得元・取得日を明記
- 比較対象: 現行「NAT Gateway 1 + ECS常時1」と採用「NAT 0 + ECS初期0/2時間アイドル停止」。VPC Endpoint案も却下案として固定費を記録
- 目標: 合計3,000円以下。超過時は必須通信を削らず、アイドル時間、起動回数、ログ量、ARM64を再評価

### Alternatives considered

1. **固定の概算値だけを記載**: 将来追跡できないため却下。
2. **請求実績だけで判断**: 導入前比較ができず、候補間条件も揃わないため却下。

## 9. 参照した一次資料

- AWS: *Amazon ECS task networking options for Fargate*
- AWS: *Automatically scale your Amazon ECS service*
- AWS API Reference: *UpdateService*
- AWS: *AWS services that integrate with AWS PrivateLink*
- AWS: *Amazon VPC Pricing*
- AWS: *AWS Fargate Pricing*
- リポジトリ: `infrastructure/stacks/ecs_stack.py`
- リポジトリ: `infrastructure/stacks/lambda_stack.py`
- リポジトリ: `backend/lambda/src/services/ecs_manager.py`
- リポジトリ: `backend/lambda/src/main.py`
- リポジトリ: `frontend/src/services/pc-api.ts`

すべての技術コンテキスト上の不明点は解消済みであり、`NEEDS CLARIFICATION` は残っていない。