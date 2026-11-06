# Implementation Plan: 既存ECS運用のコスト最適化と安全性補強

**Branch**: `003-optimize-ecs-costs` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-optimize-ecs-costs/spec.md`

## Summary

001で実装済みのLambda（認証・軽量処理・ECSプロキシ）とECS Fargate（PC管理・Gemini処理）の責務分担、起動・停止、2時間アイドル判定、起動中UIを維持し、構成ミスと競合時の安全性だけを差分修正する。VPCのNAT Gatewayを0、ECS Serviceの初期稼働数を0にし、パブリックサブネットとタスク稼働時のパブリックIPv4によってGemini API、DynamoDB、ECR、CloudWatch Logsへの送信通信を維持する。

停止中の操作は、Lambdaが既存`SystemActivity`の条件付き更新で起動を一度だけ要求し、フロントエンドが同じ`Idempotency-Key`を保持して最大3分間自動再送する。ECSは状態変更結果を7日間保持し、処理開始から5分更新されず成功未確定の要求だけを条件付きで回収する。PC登録、PC返却、PCステータス更新は、業務書込みと冪等成功記録を1回のDynamoDB `TransactWriteItems`で確定し、所有者と開始時刻の条件によって旧所有者の遅延コミットを拒否する。

公開IPのECSへの転送は、LambdaがHTTPメソッド、正規化パスとクエリ、本文ハッシュ、要求ID、冪等キー、送信時刻、秘密世代IDをHMAC-SHA256署名する。ECSは業務処理前に本文、署名、±60秒の時刻窓を検証する。共有秘密はSecrets Managerで管理し、Lambdaは現行1世代で署名、ECSは移行中のみ現行・次期の最大2世代を検証して無停止ローテーションする。

## Technical Context

**Language/Version**: Python 3.9（Lambda）、Python 3.11（ECSコンテナ）、TypeScript 6 / React 19 / Next.js 16（フロントエンド）
**Primary Dependencies**: AWS CDK 2.x（Python）、FastAPI 0.104.1、Mangum 0.17.0、boto3 1.34.11、urllib3、Next.js 16.2.4、AWS ECS Fargate、API Gateway HTTP API、EventBridge、Secrets Manager
**Storage**: 既存DynamoDB `SystemActivity`（稼働制御・冪等性記録をキー分離して追加利用）、既存業務テーブル`PCs`、`ReturnRecords`、`PCUsageHistories`、`Users`、既存Secrets Manager
**Testing**: pytest（Lambda/ECS/CDK）、httpx、CDK assertions、TypeScript型検査、Next.js build、AWS検証環境受け入れ試験
**Target Platform**: AWS `ap-northeast-1`、API Gateway + Lambda Python 3.9、ECS Fargate Linux、Amplify/主要ブラウザ
**Project Type**: Web application（`frontend` + `backend/lambda` + `backend/ecs` + `infrastructure`）
**Performance Goals**: 停止状態から対象操作を3分以内に完了、同時10件の起動要求を1回のECS起動更新へ集約、アイドル条件成立後15分以内に停止
**Constraints**: 月額3,000円以下を目標、ALB/NAT Gateway不使用、アイドル2時間、再試行上限3分、成功結果保持7日、停滞処理権回収5分、署名時刻差±60秒、署名秘密は最大2世代、状態変更結果の重複0件、既存認証・業務結果を変更しない
**Scale/Scope**: 20〜30名の低頻度・小規模利用、参照系1操作、状態変更3ルート、PC登録・PC返却を必須受け入れ対象、現行案・採用案・却下案の同条件コスト比較

## Constitution Check

*GATE: Phase 0開始前に確認し、Phase 1設計後に再確認する。*

| 原則 | 設計上の対応 | Phase 0前 | Phase 1後 |
|---|---|---|---|
| 日本語出力 | 計画・調査・データモデル・契約・検証手順を日本語で作成 | PASS | PASS |
| スキーマ推測禁止 | 001の`data-model.md`、API契約、現行ルートとCDK定義を一次ソースとし、状態変更3ルートと既存PKを確認 | PASS | PASS |
| Security First | 実キーを記載せずSecrets Managerを利用。Lambda署名、ECS業務処理前検証、±60秒、最大2世代、既存利用者認証を独立して検証 | PASS | PASS |
| Hybrid Responsibility | 起動・停止・軽量プロキシ・署名はLambda、PC管理・Gemini処理・内部署名検証はECSのまま維持 | PASS | PASS |
| Cost-Awareness | NAT GatewayとALBを使わず、ECSを初期0・2時間アイドル後0にする | PASS | PASS |
| Clean Code / Naming | Pythonは`snake_case`、一般ファイルは`kebab-case`、状態名と識別子は契約で統一 | PASS | PASS |
| AI Logic | Gemini抽出ロジック自体は変更せず、通信経路と回帰結果だけを検証 | PASS | PASS |
| Ubiquitous Language | Backend Runtime State、Start Lock、Idempotency Key、In-flight Operation、Runtime Generation、Internal Request Signature、Secret Generationを実装前に追加 | PASS（実装前ゲート） | PASS（先頭タスクで実施） |
| Issue単位・最小変更 | 設定是正、既存経路の安全対策、検証記録だけを変更し、代替実装や無関係なリファクタリングを行わない | PASS | PASS |

憲章違反および未解決の`NEEDS CLARIFICATION`はない。内部署名と秘密ローテーションはSecurity Firstを満たす必須実装ゲートとし、欠落した状態で実装完了としない。

## Project Structure

### Documentation (this feature)

```text
specs/003-optimize-ecs-costs/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── runtime-api.md
│   └── cost-evaluation.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── lambda/
│   ├── src/
│   │   ├── main.py                         # 起動応答、署名付きプロキシ、活動記録
│   │   └── services/
│   │       ├── ecs_manager.py              # 起動ロック、状態、停止競合、定期判定
│   │       └── internal_request_signer.py  # canonical requestとHMAC署名（追加）
│   └── tests/                               # 起動・停止・プロキシ・署名テスト（追加）
└── ecs/
    ├── src/
    │   ├── main.py                         # 内部署名検証、冪等ガード、活動完了連携
    │   └── services/
    │       ├── idempotency_service.py      # 状態変更の一回処理（追加）
    │       └── internal_request_verifier.py # HMAC・時刻窓・秘密世代検証（追加）
    └── tests/                               # 冪等性・署名・活動記録テスト

frontend/
└── src/
    ├── services/
    │   └── pc-api.ts                       # 共通3分再試行・Idempotency-Key
    ├── components/
    │   └── ecs-loading-state.tsx           # 起動中・上限超過表示
    └── app/pcs/                             # 一覧・登録・返却で共通クライアントを利用

infrastructure/
├── stacks/
│   ├── database_stack.py                   # 既存SystemActivityのTTL設定
│   ├── ecs_stack.py                        # NATなし、desired_count=0、検証秘密参照
│   └── lambda_stack.py                     # 署名秘密参照、IAM最小化、15分ルール
└── tests/unit/                              # CDK assertions
```

**Structure Decision**: 既存4領域を維持し、新規モジュールは既存Lambda/ECS内の署名責務と共通冪等性責務に限定する。新しいデプロイ単位、ALB、キュー、専用テーブルは追加しない。テストは実在する`backend/lambda/tests`、`backend/ecs/tests`、`infrastructure/tests`へ配置する。

## Phase 0: Research Outcomes

詳細は[research.md](./research.md)を参照。主要判断は次のとおり。

1. NAT Gatewayなしのパブリックサブネット方式。
2. DynamoDB条件付き更新による単一起動。
3. クライアント自動再送と7日保持・5分回収を備えたECS冪等性。
4. 状態変更3ルートについて、業務書込みと`PROCESSING -> SUCCEEDED`を1回の`TransactWriteItems`で確定し、`ownerRequestId`と`startedAt`を条件に旧所有者の遅延確定を拒否。
5. 15分判定・処理中フェンス・世代による停止競合制御。
6. HMAC-SHA256、±60秒、Secrets Managerの最大2世代による境界防御と無停止ローテーション。
7. 公式価格情報に基づく再現可能なコスト記録。

## Phase 1: Design Outcomes

- [data-model.md](./data-model.md): 稼働制御状態、冪等所有権・5分回収・7日保持・原子確定、コスト評価、検証記録を定義
- [contracts/runtime-api.md](./contracts/runtime-api.md): 状態変更3ルート、起動中応答、再試行、冪等性、署名付き内部転送、秘密ローテーションの契約
- [contracts/cost-evaluation.md](./contracts/cost-evaluation.md): 比較表、価格根拠、見直し条件の記録契約
- [quickstart.md](./quickstart.md): ローカル検証、CDK synth、AWS通信・起動・停止・署名・秘密切替・費用確認手順

Phase 1後も憲章ゲートはすべてPASSであり、設計上の例外承認は不要である。

## Implementation Strategy

1. **用語・対象棚卸し**: 新語をユビキタス言語へ追加し、現行ECSルートを走査して状態変更3ルートと非永続`parse-specs`を契約・テストで固定する。
2. **テスト先行**: Lambda/ECS/CDKの失敗する契約テストを実装より先に作成する。
3. **ネットワーク費削減**: 既存VPCをNAT 0、ECSを`desired_count=0`へ修正し、public subnet、public IP、ALBなしをassertionsで固定する。
4. **境界防御**: Lambdaでcanonical requestをHMAC-SHA256署名し、ECSミドルウェア/依存関数で業務処理前に本文、要求ID、冪等キー、key ID、±60秒を検証する。外部入力の内部ヘッダーはLambdaで削除して再生成する。
5. **秘密管理**: Secrets Managerの1秘密内に現行・次期の最大2世代を非機密key IDと対応付ける。Lambdaは指定された現行1世代だけで署名し、ECSは移行中だけ2世代を検証する。CDKは秘密値をCloudFormation、通常環境変数、ログへ展開せず、必要最小限の読取権限を付与する。
6. **稼働制御**: `SystemActivity/global`の条件付き更新で起動所有権を1呼び出しに限定し、状態世代番号を用いて停止競合後の再起動を保証する。
7. **活動・停止判定**: 受付時と成功完了時を更新し、転送中件数を原子的に増減する。欠損・不正値・処理中は停止せず、EventBridgeを15分間隔へ変更する。
8. **再試行・一回処理**: フロントエンド共通APIクライアントに`Retry-After`準拠の最大3分自動再送を実装する。ECSは成功結果を7日保持し、5分未満は回収を拒否、5分以上停滞かつ成功未確定の場合だけ古い所有者・開始時刻を条件に処理権を回収する。
9. **原子確定**: PC登録、PC返却、PCステータス更新は低レベルDynamoDB clientの`TransactWriteItems`を使い、既存業務項目のPut/Update、必要な既存履歴項目、冪等成功結果を同時確定する。冪等更新条件に現`ownerRequestId`、現`startedAt`、`status=PROCESSING`を含め、回収後に旧所有者が業務変更を確定できないようにする。既存業務スキーマへ新属性は追加しない。
10. **実環境検証**: 必須4通信、対象3操作×5回、同時10件、2時間境界、停止競合、署名欠落・改ざん・期限切れ、利用者認証併用、3段階秘密切替、デプロイ直後0を記録する。
11. **費用検証**: 公式価格の基準日・条件・為替を記録し、導入後30日または最初の完全請求期間に見積りとの差をレビューする。

## Test Strategy Details

- **署名単体/契約**: 正常、ヘッダー欠落、本文・パス・メソッド・要求ID・冪等キー改ざん、時刻差-61/-60/+60/+61秒、不明・失効key ID、定数時間比較、外部内部ヘッダー除去を検証する。
- **ローテーション**: ECSが現行+次期を受理する段階、Lambdaを次期へ切り替える段階、旧秘密をECSから除外する段階を順番に検証し、各段階で正当要求100%成功、失効後旧秘密100%拒否を記録する。
- **冪等所有権**: 5分未満の回収拒否、5分境界以上かつ成功未確定時の回収成功、成功済み回収拒否、同時回収1件、回収後の旧所有者トランザクション失敗を検証する。
- **7日保持**: 7日直前は保存結果を再利用し、7日経過後はDynamoDB TTL削除待ちでも新規要求として条件付き置換できることを検証する。
- **API棚卸し**: FastAPIルートから`POST/PUT/PATCH/DELETE`を列挙し、3状態変更ルートが冪等ガード対象、`POST /api/pcs/parse-specs`が永続変更なしの対象外であることをテストで固定する。将来ルート追加時は分類なしで検証を通さない。
- **トランザクション**: 各業務書込み、履歴書込み、成功記録のいずれかを失敗させ、部分成功0件であることを検証する。

## Complexity Tracking

憲章違反はないため、例外的な複雑性の正当化は不要。