# Implementation Plan: PC Management Ledger

**Branch**: `001-pc-management` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-pc-management/spec.md`

## Summary

社内のPC管理台帳アプリ。Microsoftアカウントでのログイン、PCの一覧確認、ユーザー自身によるPC登録（ターミナルからのスペック情報取得とGemini APIによる自動抽出）、管理者による代理登録、PCの返却機能を提供する。
コスト最適化のため、フロントエンドはNext.js (AWS Amplify)、バックエンドはAWS LambdaとAmazon ECS (Express Mode) を組み合わせたハイブリッド構成とし、DynamoDBをデータストアとして利用する。
ログインは常に利用できるようNext.js + AWS Lambdaで構成し、ログイン後の資産管理情報出力などの重い処理にはAmazon ECSを利用する。ECSは利用時にのみ起動し、起動後または利用終了から2時間経過後に自動でスリープ状態（課金されない状態）に移行する。ECSの起動に時間がかかる場合は、フロントエンドで「loading...」などの表示を行い、ユーザーの待機時間を適切にハンドリングする。

## Technical Context

**Language/Version**: TypeScript (Next.js), Python (FastAPI, AWS CDK)
**Primary Dependencies**: Next.js, FastAPI, AWS CDK, AWS SDK (boto3), Gemini API
**Storage**: Amazon DynamoDB
**Testing**: Jest (Frontend), pytest (Backend), AWS CDK tests
**Target Platform**: AWS (Amplify, Lambda, ECS, DynamoDB)
**Project Type**: Web Application (Frontend + Serverless/Container Hybrid Backend)
**Performance Goals**: ECSコールドスタート時のUX考慮（適切なローディング表示）、通常時は数秒以内のレスポンス
**Constraints**: 月間数百円〜数千円以内のコスト、ALB非利用（Lambda Function URLsやECS直接接続を活用）
**Scale/Scope**: 20〜30名のユーザー、PC台数約40台（初期）

## ECS Auto-Sleep Implementation Details

**背景**: FR-015 で「ECS は利用時にのみ起動し、2 時間のアイドル状態が継続した場合に自動でスリープ状態に移行」と定義されている。以下が実装の責任分担と技術詳細。

### タイムスタンプ管理
- **記録場所**: DynamoDB `PCs` テーブルに `lastActivityAt` フィールドを追加（ISO 8601 形式）
- **更新トリガー**: Lambda 経由のすべての ECS API 呼び出し完了時に、該当ユーザーまたはシステムの `lastActivityAt` をリアルタイムで更新
- **判定ロジック**: Lambda 内の `ecs-manager.py` で、ECS ヘルスチェック API の呼び出し時に「現在時刻 - lastActivityAt > 2 時間」を条件に停止指令を実行

### CloudWatch Events との連携
- **定期判定**: CloudWatch Events で 1 時間ごとに Lambda 関数を実行（`ecs-manager.py` 内の `check_idle_timeout` 関数）
- **停止処理**: Lambda が ECS タスク定義を参照し、タイムアウト条件にマッチしたタスクを停止（ECS `stop_task` API）
- **ログ記録**: ECS 停止イベントを CloudWatch Logs に記録し、トラブルシューティング時に参照可能にする

### 起動処理
- **トリガー**: フロントエンドから PC 管理関連の重い API リクエスト（parse-specs、PC 登録、一覧取得等）を受信時
- **実装**: Lambda が ECS タスク定義を起動（ECS `run_task` API）し、ローディング UI をフロントエンドに返す（FR-016）
- **責任**: T039（ecs-manager.py）が起動・停止ロジックの全責任を担う；T040（ecs-loading-state.tsx）はフロントエンドのローディング表示を担当

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Core Principles:
  - Layer 1: 出力言語は日本語。スキーマ推測の禁止 (`data-model.md` と `contracts/` を厳密に参照)。セキュリティファースト (実データ・キーを含めず、環境変数やダミーデータを使用)。
  - Layer 2: プロジェクトミッションはAWSコスト最適化とGemini APIによるPCスペック登録の完全自動化。
  - Layer 3: 開発ポリシー: ハイブリッド責任モデル (ログイン/軽量処理はLambda、重い処理/管理者はECS)、コスト意識 (ECS自動スリープ、ALB回避)、クリーンコード、Kebab-case命名、AIロジック (LLMによる柔軟なパース)。
  - Layer 4: ドキュメント運用: `docs/session-notes.md`、`docs/backlog.md`、`docs/troubleshooting.md` の維持・更新。

## Project Structure

### Documentation (this feature)

```text
specs/001-pc-management/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/           # Next.js App Router
│   ├── components/
│   ├── lib/
│   └── services/      # API Clients
└── package.json

backend/
├── lambda/            # AWS Lambda (Login, Lightweight API, ECS Trigger)
│   ├── src/
│   └── requirements.txt
├── ecs/               # Amazon ECS (Core Logic, Admin Features)
│   ├── src/
│   ├── Dockerfile
│   └── requirements.txt
└── tests/

infrastructure/        # AWS CDK
├── app.py
├── stacks/
└── tests/
```

**Structure Decision**: Web application with separate frontend (Next.js), backend (Python/FastAPI split into Lambda and ECS), and infrastructure (AWS CDK) directories.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
