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
