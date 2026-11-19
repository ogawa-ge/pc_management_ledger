# Implementation Plan: PC新規登録時の登録失敗・画面固まり解消

**Branch**: `007-fix-pc-registration` | **Date**: 2026-11-18 | **Spec**: [spec.md](file:///c:/Users/hagihara/pc_management_ledger/specs/007-fix-pc-registration/spec.md)

**Input**: Feature specification from `/specs/007-fix-pc-registration/spec.md` (GitHub Issue #30)

## Summary

PC新規登録画面（`/pcs/register`）で登録ボタンを押しても登録が完了せず固まったように見える問題について、まず **主原因（ECS に DynamoDB `Users` テーブルの読み取り権限がない）を実環境で実証（T000）** したうえで、**CDK `EcsStack` への `Users` テーブル読み取り権限（`grant_read_data`）の付与漏れ** を修正する。あわせてフロントエンド側の **管理者向けオーナー候補一覧取得（`getUsers`）へのコールドスタート待機リトライ適用**、**エラー時の ECS起動待機表示の解除徹底**、**登録ボタン付近への日本語エラーメッセージ表示** を最小差分で実装する。

既存の技術スタックのみを使用し、本 Issue の対象外のリファクタリングや他画面の変更は行わない。

## Technical Context

**Language/Version**: TypeScript 6.0.3 (Next.js 16.2.4 / React 19.2.5), Python 3.11 / 3.12 (AWS CDK 2.276.0, FastAPI 0.104.1)  
**Primary Dependencies**: Next.js, NextAuth.js, AWS CDK (`aws-cdk-lib`), pytest（※新規ライブラリ追加なし）  
**Storage**: Amazon DynamoDB（既存の `Users` テーブルへの読み取り権限付与のみ。スキーマ変更なし）  
**Testing**: `pytest`（`infrastructure/tests/unit/` ※`.venv` に `infrastructure/requirements-dev.txt` を導入して実行）、フロントエンドのビルド／型チェック確認、AWS 本番環境での PC 新規登録実機テスト  
**Target Platform**: AWS Amplify Hosting（フロントエンド） + AWS ECS Fargate / CDK（バックエンド）  
**Project Type**: Web Application + AWS CDK Infrastructure  
**Performance Goals**: ECS 起動済み状態で PC 登録・オーナー候補一覧取得が数秒以内に完了すること、コールドスタート時は既存の 180 秒リトライ待機で自動回復すること  
**Constraints**:
- Constitution Layer 4 厳守: Issue #30 に直結するファイルのみを最小限修正し、他画面や無関係なリファクタリング・依存パッケージ更新・認証基盤の強化（Issue #32）は行わない。
- 最小権限の原則: `EcsStack` には `Users` テーブルの読み取り権限（`grant_read_data`）のみ付与し、書き込み権限は付与しない。
- ECS 側コードは `Users` テーブル名を直書き（`'Users'`）しているため、未使用の環境変数（`USERS_TABLE_NAME`）は追加しない。  
**Scale/Scope**: CDK 2ファイル + CDK 単体テスト 1ファイル + フロントエンド 2ファイル。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 憲法規定 / 原則 | 適合状況 | 判定 |
|---|---|---|
| **Layer 1: Output Language** | ドキュメント・設計・テスト・解説をすべて日本語で記述 | **PASS** |
| **Layer 1: No Hallucination** | `Users` テーブルの既存キー（`userId`）および既存 API 契約のみを参照。原因は実環境で実証（T000）してから修正する | **PASS** |
| **Layer 1: Security First** | 最小権限（`grant_read_data` のみ）を適用し、機密情報のハードコードなし | **PASS** |
| **Layer 3: Architecture Integrity** | 既存の Lambda / ECS / DynamoDB 役割分担とコスト最適化構成を維持 | **PASS** |
| **Layer 3: Code Standard & Ubiquitous Language** | `docs/ubiquitous-language.md` の用語（オーナー、オーナー候補、コールドスタート、ECS起動待機表示等）に準拠。新語は同ドキュメントへ追記済み | **PASS** |
| **Layer 4: Strict Scope Boundaries** | Issue #30 の原因箇所のみを最小修正し、他ブランチ・他画面・Issue #32 とのコンフリクトを回避 | **PASS** |

## Project Structure

### Documentation (this feature)

```text
specs/007-fix-pc-registration/
├── spec.md              # 仕様書
├── checklists/
│   └── requirements.md  # 仕様品質チェックリスト
├── research.md          # Phase 0 調査メモ（技術方針・原因実証方針・脆弱性リサーチ結果）
├── quickstart.md        # Phase 1 検証・デプロイ手順
├── plan.md              # 本実装計画書
└── tasks.md             # Phase 2 タスクリスト (/speckit-tasks で生成)
```
※DBテーブル・カラムやAPIエンドポイントの新規追加・変更はないため、`data-model.md` および `contracts/` は省略。

### Source Code (repository root)

```text
infrastructure/
├── app.py                                      # 【変更】EcsStack に users_table を渡す
├── stacks/
│   └── ecs_stack.py                            # 【変更】users_table の読み取り権限 (grant_read_data) を追加
└── tests/
    └── unit/
        └── test_infrastructure_stack.py        # 【変更】EcsStack の Users テーブル読み取り専用権限を検証する単体テスト追加

frontend/
└── src/
    ├── services/
    │   └── pc-api.ts                           # 【変更】getUsers に requestWithRetry を適用（503コールドスタート待機対応）
    └── app/
        └── pcs/
            └── register/
                └── page.tsx                    # 【変更】fetchUsers の起動待機連動、エラー時の ECS起動待機表示の解除徹底、ボタン直上への日本語エラー表示

docs/
└── ubiquitous-language.md                      # 【変更済み】新語（コールドスタート / ECS起動待機表示）を追記
```

**Structure Decision**: 既存の `infrastructure/` と `frontend/` の構成を踏襲し、コード変更対象を上記5ファイルのみに限定する（用語追記は `docs/ubiquitous-language.md` のみ）。
