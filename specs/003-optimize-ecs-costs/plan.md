# Implementation Plan: NAT GatewayとECS稼働数のコスト最適化

**Branch**: `003-optimize-ecs-costs` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-optimize-ecs-costs/spec.md`

## Summary

既存の Lambda（認証・軽量処理・ECSプロキシ）と ECS Fargate（PC管理・Gemini処理）の責務分担を維持しながら、NAT Gateway を削除し、ECS サービスの初期稼働数を 0 にする。ECS タスクはパブリックサブネットで稼働時のみパブリック IPv4 を割り当て、Gemini API、DynamoDB、ECR、CloudWatch Logs への送信通信を維持する。

停止中の操作は、Lambda が DynamoDB の条件付き更新で起動を一度だけ要求し、フロントエンドが同じ `Idempotency-Key` を保持して最大3分間自動再送する。状態変更操作は ECS 側の冪等性記録により一回だけ成立させる。受付時・転送時・成功完了時のアクティビティと処理中件数を `SystemActivity` に記録し、15分間隔の EventBridge 判定が、最終成功完了から2時間以上かつ処理中件数0の場合のみ停止する。停止競合時は世代番号を再確認して再起動を保証する。

## Technical Context

**Language/Version**: Python 3.9（Lambda）、Python 3.11（ECSコンテナ）、TypeScript 6 / React 19 / Next.js 16（フロントエンド）  
**Primary Dependencies**: AWS CDK 2.x（Python）、FastAPI 0.104.1、Mangum 0.17.0、boto3 1.34.11、urllib3、Next.js 16.2.4、AWS ECS Fargate、API Gateway HTTP API、EventBridge  
**Storage**: 既存 DynamoDB `SystemActivity`（稼働制御・冪等性記録をキー分離して追加利用）、既存業務テーブル `PCs`、`ReturnRecords`、`PCUsageHistories`、`Users`  
**Testing**: pytest 8.4.2（CDK）、pytest 7.4.3 + httpx（ECS）、Lambda の pytest 単体・統合テストを追加、TypeScript 型検査、Next.js build、CDK assertions、AWS 実環境受け入れ試験  
**Target Platform**: AWS ap-northeast-1、API Gateway + Lambda Python 3.9、ECS Fargate Linux 1.4.0以降、Amplify/ブラウザ  
**Project Type**: Web application（`frontend` + `backend/lambda` + `backend/ecs` + `infrastructure`）  
**Performance Goals**: 停止状態から全対象操作を3分以内に完了、同時10件の起動要求を1回の ECS 起動へ集約、アイドル成立後15分以内に停止  
**Constraints**: 月額3,000円以下を目標、ALB不使用、NAT Gateway不使用、アイドル2時間、再試行上限3分、状態変更結果の重複0件、デプロイ直後と停止後の稼働タスク0、既存認証・業務結果を変更しない  
**Scale/Scope**: 20〜30名、低頻度・小規模利用、参照系1操作・PC登録・PC返却を必須受け入れ対象、ネットワーク候補2案以上の比較

## Constitution Check

*GATE: Phase 0 開始前に確認し、Phase 1 設計後に再確認する。*

| 原則 | 設計上の対応 | Phase 0前 | Phase 1後 |
|---|---|---|---|
| 日本語出力 | 計画・調査・データモデル・契約・検証手順を日本語で作成 | PASS | PASS |
| スキーマ推測禁止 | 既存 `data-model.md` と API 契約を参照し、新規制御項目を本機能の `data-model.md` と `contracts/` に定義 | PASS | PASS |
| Security First | 実キーを記載せず Secrets Manager を利用。公開IPのECSは Lambda 署名付き内部要求を検証し、既存認証ヘッダーも維持 | PASS | PASS |
| Hybrid Responsibility | 起動・停止・軽量プロキシは Lambda、PC管理・Gemini処理は ECS のまま維持 | PASS | PASS |
| Cost-Awareness | NAT Gateway と ALB を使わず、ECSを初期0・2時間アイドル後0にする | PASS | PASS |
| Clean Code / Naming | Pythonは `snake_case`、一般ファイルは `kebab-case`、状態名は契約で統一 | PASS | PASS |
| AI Logic | Gemini抽出ロジック自体は変更せず、通信経路のみ検証 | PASS | PASS |
| Ubiquitous Language | 実装開始前に Backend Runtime State、Idempotency Key 等の新語を `docs/ubiquitous-language.md` へ追加する | PASS（実装前ゲート） | PASS（実装タスクの先頭条件） |
| Issue単位・最小変更 | Issue #16に必要なインフラ、起動制御、再試行、冪等性、検証記録だけを変更 | PASS | PASS |

憲章違反および未解決の `NEEDS CLARIFICATION` はない。

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
└── tasks.md                 # /speckit.tasks で後続作成
```

### Source Code (repository root)

```text
backend/
├── lambda/
│   ├── src/
│   │   ├── main.py                         # 起動応答、署名付きプロキシ、活動記録
│   │   └── services/
│   │       └── ecs_manager.py              # 起動ロック、状態、停止競合、定期判定
│   └── tests/                               # 起動・停止・プロキシ契約テスト（追加）
└── ecs/
    ├── src/
    │   ├── main.py                         # 内部署名検証、活動完了連携
    │   └── services/
    │       └── idempotency_service.py      # 状態変更の一回処理（追加）
    └── tests/                               # 冪等性・活動記録テスト

frontend/
└── src/
    ├── services/
    │   └── pc-api.ts                       # 共通3分再試行・Idempotency-Key
    ├── components/
    │   └── ecs-loading-state.tsx           # 起動中・上限超過表示
    └── app/pcs/                             # 一覧・登録・返却で共通クライアントを利用

infrastructure/
├── stacks/
│   ├── ecs_stack.py                        # NATなしVPC、desired_count=0、署名シークレット
│   └── lambda_stack.py                     # IAM最小化、15分ルール、環境変数
└── tests/unit/                              # CDK assertions
```

**Structure Decision**: 既存4領域を維持し、新規サービスを既存 Lambda/ECS の配下に限定する。新しいデプロイ単位、ALB、キュー、専用テーブルは追加せず、`SystemActivity` の単一パーティションキー設計をキー接頭辞で拡張する。

## Phase 0: Research Outcomes

詳細は [research.md](./research.md) を参照。主要判断は、(1) NAT Gatewayなしのパブリックサブネット方式、(2) Lambdaの条件付き起動ロック、(3) クライアント自動再送とECS冪等性記録、(4) 15分判定と処理中フェンス、(5) 公式価格情報に基づく再現可能なコスト記録である。

## Phase 1: Design Outcomes

- [data-model.md](./data-model.md): 稼働制御状態、アクティビティ、冪等性、コスト評価、検証記録を定義
- [contracts/runtime-api.md](./contracts/runtime-api.md): 起動中応答、再試行、冪等性、署名付き内部転送の契約
- [contracts/cost-evaluation.md](./contracts/cost-evaluation.md): 比較表、価格根拠、見直し条件の記録契約
- [quickstart.md](./quickstart.md): ローカル検証、CDK synth、AWS通信・起動・停止・費用確認手順

## Implementation Strategy

1. **用語・テスト基盤**: 新語をユビキタス言語へ追加し、Lambda/ECS/CDKの失敗する契約テストを先に作成する。
2. **ネットワーク費削減**: VPCを明示的なパブリックサブネットのみ・NAT 0へ変更し、ECS `desired_count=0`、既存ALBなしを assertions で固定する。
3. **稼働制御**: DynamoDB条件付き更新で起動所有権を1呼び出しに限定し、状態世代番号を用いて停止競合後の再起動を保証する。
4. **活動・停止判定**: 受付時と成功完了時を更新し、転送中件数を原子的に増減する。欠損・不正値・処理中は fail-open で停止しない。EventBridgeを15分間隔へ変更する。
5. **再試行・一回処理**: フロントエンド共通APIクライアントに `Retry-After` 準拠の最大3分自動再送を実装し、状態変更は同一キーの処理結果をECSで再利用する。
6. **境界防御**: Lambdaが内部署名、時刻、要求IDを付与し、ECSは署名・時刻窓を検証する。IAMの `ecs:UpdateService` は対象サービスARNへ絞る。
7. **実環境検証**: 4通信先、対象3操作×5回、同時10件、2時間境界、停止競合、デプロイ直後0を記録する。
8. **費用検証**: 公式価格の基準日・条件・為替を記録し、導入後30日または最初の完全請求期間に見積りとの差をレビューする。

## Complexity Tracking

憲章違反はないため、例外的な複雑性の正当化は不要。