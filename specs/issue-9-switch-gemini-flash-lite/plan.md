# Implementation Plan: AI抽出モデルの軽量モデルへの切り替え

**Branch**: `issue-9-switch-gemini-flash-lite` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/issue-9-switch-gemini-flash-lite/spec.md`

## Summary

本番の AI 抽出が「通信エラー」で失敗する問題を解消する。原因は、AI 抽出に使っている `gemini-3.6-flash` の応答の遅れ・混雑で、Lambda が ECS の応答を待つ上限（25秒）を超えていること（[research.md](./research.md) Decision 1）。ECS の `gemini_service.py` で使うモデルを `gemini-3.5-flash-lite`（ローカル検証で 1.9〜3.1 秒、全項目を抽出）に切り替える。変更はモデル名の 1 か所のみで、API の入出力・プロンプト・画面は変えない。

## Technical Context

**Language/Version**: Python 3.11（ECS コンテナ `python:3.11-slim`）

**Primary Dependencies**: FastAPI、標準ライブラリ `urllib.request`（Gemini API を REST で呼び出す）

**Storage**: N/A（データの保存は変更しない）

**Testing**: pytest（`backend/ecs/tests`、Gemini API の呼び出しはモック）＋ローカルでの実 API 呼び出し＋本番での画面確認（[quickstart.md](./quickstart.md)）

**Target Platform**: AWS ECS Fargate（`PCManagementService`）。本番への反映には ECS の再デプロイが必要

**Project Type**: Web アプリケーション（Next.js フロントエンド＋Lambda プロキシ＋ECS バックエンド）

**Performance Goals**: AI 抽出が 10 秒以内に完了する（SC-001）。ローカル検証では 1.9〜3.1 秒

**Constraints**: Lambda のプロキシが ECS の応答を待つ上限は 25 秒（API Gateway HTTP API と Lambda の上限は 30 秒）。Gemini API は無料枠のキーを使う

**Scale/Scope**: 社内の少人数での利用、AI 抽出の実行は少ない回数。変更するファイルは 1 つ（1 行）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 判定 | 根拠 |
|---|---|---|
| L1-1 Output Language（日本語） | ✅ | 成果物はすべて日本語 |
| L1-2 No Hallucination | ✅ | API の契約・データモデルは変更せず、002 の定義をそのまま参照する |
| L1-3 Security First | ✅ | API キーはコードやドキュメントに書かず、Secrets Manager の値を使う。検証でもキーは環境変数で渡す |
| L2 Mission（コスト最適化） | ✅ | 無料枠のキーと軽量モデルを使い、AWS の構成は変えない |
| L3-1 Architecture Integrity | ✅ | Lambda（プロキシ）と ECS（抽出処理）の役割分担は変えない |
| L3-2 Code Standard / Naming | ✅ | 新しいファイル名・変数名を追加しない |
| L3-3 AI Logic | ✅ | LLM による抽出の方式とプロンプトは変えない |
| L3 Ubiquitous Language | ✅ | 新しい用語はない |
| L4-1 Issue 単位のドキュメント管理 | ✅（注記あり） | Issue #9 のブランチと `specs/issue-9-switch-gemini-flash-lite/` で管理する。※ Constitution の文面は `specs/<issue-number>-<feature-name>/` だが、2026-11-25 に `main` へ入った AGENTS.md（`6c3f094`）のルール `specs/issue-<issue番号>-<feature-name>/` に従っている。Constitution 側の更新漏れとしてチームに連絡済みで、改定は別途行われる（/speckit-analyze D1） |
| L4-2 Strict Scope Boundaries | ✅ | 変更は `gemini_service.py` のモデル名のみ。Lambda の上限・リトライ設計・古いテストスクリプトの修正は範囲外（[research.md](./research.md) Decision 4） |

**結果**: 違反なし。Phase 1 の設計後も同じ判定（設計で変更範囲は広がっていない）。

## Project Structure

### Documentation (this feature)

```text
specs/issue-9-switch-gemini-flash-lite/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command) — 変更なしを明記
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md  # /speckit-specify で作成
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

`contracts/` は作らない。`POST /api/pcs/parse-specs` の入出力は変わらないため、[002-ai-pc-info-extraction/contracts/api.md](../002-ai-pc-info-extraction/contracts/api.md) をそのまま参照する。

### Source Code (repository root)

```text
backend/ecs/
├── src/
│   └── services/
│       └── gemini_service.py   # 変更: API URL のモデル名を gemini-3.6-flash → gemini-3.5-flash-lite
└── tests/                      # 変更なし（既存テストが通ることを確認する）
```

**Structure Decision**: 既存の Web アプリケーション構成（`backend/ecs`、`backend/lambda`、`frontend`、`infrastructure`）のうち、`backend/ecs/src/services/gemini_service.py` だけを変更する。Lambda・フロントエンド・CDK は変更しない。

## Complexity Tracking

Constitution の違反はないため、記載なし。
