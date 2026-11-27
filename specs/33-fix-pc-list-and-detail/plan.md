# Implementation Plan: PC一覧の表示不整合修正およびPC詳細画面の実装

**Branch**: `issue-33-fix-pc-list-and-detail` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/33-fix-pc-list-and-detail/spec.md`

## Summary

Issue #33 で報告された 3 つの問題（①PC一覧の「ユーザー」列が常に「未割り当て」、②「モデル名」列が空欄＋登録時のモデル名必須化、③「詳細」リンクが 404 未実装）を、既存の技術スタック（Next.js App Router + FastAPI on ECS + DynamoDB）のみで最小限かつ安全に修正・実装する。
バックエンド（ECS FastAPI）では `GET /api/pcs` に `Users` テーブルからの `ownerName` 解決（`InUse` のみオーナー名を解決し、それ以外のステータスは「未割り当て」扱いの `null`）を追加し、単一 PC 取得 API `GET /api/pcs/{pc_id}` を新設する。フロントエンド（Next.js）では一覧の `model` 参照修正、登録フォームのモデル名必須化（画面上のみ）、返却 API 呼び出し時の `Authorization` ヘッダー付与修正、および PC 詳細画面（`/pcs/[pcId]`）の新規実装（スペック表示・返却導線・管理者向けステータス更新・ECS 起動待機対応）を行う。

## Technical Context

**Language/Version**: TypeScript (Next.js App Router), Python 3.11+ (FastAPI)  
**Primary Dependencies**: Next.js, NextAuth.js, Tailwind CSS, FastAPI, Pydantic (`BaseApiModel`), boto3  
**Storage**: Amazon DynamoDB（既存テーブル `PCs`, `Users`, `PCUsageHistories` — スキーマ変更・CDK 変更なし）  
**Testing**: pytest (`backend/ecs/tests/`), TypeScript 型チェック `npx tsc --noEmit` & Next.js `npm run build` (`frontend/`)  
**Target Platform**: Web アプリケーション（PC ブラウザ対象、AWS Amplify + Lambda Proxy + Amazon ECS）  
**Project Type**: Web application (`backend/ecs/` + `frontend/`)  
**Performance Goals**: `GET /api/pcs` は `Users` テーブルを 1 回スキャンして辞書結合し N+1 クエリを回避する。`GET /api/pcs/{pc_id}` は主キー `get_item` により O(1) で取得する。  
**Constraints**: 月額コスト維持のためインフラ追加・変更なし。ECS コールドスタート時の自動リトライ（`requestWithRetry` / `ECSLoadingState`）を詳細画面にも適用すること。  
**Scale/Scope**: 社内ユーザー 20〜30 名、管理対象 PC 数十〜数百台規模。対象は Issue #33 の画面・API のみに厳格に限定する。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Layer 1: Output Language (日本語出力)**: PASS — すべての仕様書・設計書・UI メッセージ・エラー表示を日本語で記述する。
- **Layer 1: No Hallucination (スキーマ推測の禁止)**: PASS — 既存の `backend/ecs/src/models/pc.py`, `user.py`, `main.py`, `specs/001-pc-management/contracts/api.md` を直接確認し、未定義カラムを推測せず [data-model.md](./data-model.md) と [contracts/api.md](./contracts/api.md) に明文化した。
- **Layer 1: Security First**: PASS — 認証ヘッダー（`Authorization: Bearer <userId>`）および管理者チェック（`get_admin_principal`）を既存方式通りに維持し、テストではダミーデータのみを使用する。
- **Layer 2 & 3: Hybrid Responsibility & Cost-Awareness**: PASS — 資産管理コア機能（PC一覧・詳細・ステータス更新）はすべて既存の Amazon ECS で実行し、Lambda・CDK・ALB 等の追加コストは一切発生しない。
- **Layer 3: Code Standard & Naming Convention**: PASS — 新規ファイルは Next.js 予約名（`frontend/src/app/pcs/[pcId]/page.tsx`）および Python テストの `snake_case`（`backend/ecs/tests/test_pc_list_and_detail_api.py`）に従う。新用語（`Owner Name` / `Unassigned` / `Unknown User`）は実装前に `docs/ubiquitous-language.md` へ追記済み。
- **Layer 4: Strict Scope Boundaries**: PASS — Issue #33 の目的外の画面・機能（スペック編集、CSV ダウンロード、利用履歴タイムライン、インフラ変更等）には一切手を加えない。

**Post-Design Re-check**: Phase 1 設計（`data-model.md`, `contracts/api.md`, `quickstart.md`）完了後も上記すべてのゲートを PASS。違反なし。

## Project Structure

### Documentation (this feature)

```text
specs/33-fix-pc-list-and-detail/
├── plan.md              # 本ファイル（実装計画）
├── research.md          # Phase 0 調査・技術決定記録
├── data-model.md        # Phase 1 データモデル・バリデーション定義
├── quickstart.md        # Phase 1 テスト・手動検証ガイド
├── contracts/
│   └── api.md           # Phase 1 API 契約仕様
├── checklists/
│   └── requirements.md  # 仕様品質チェックリスト
└── spec.md              # 機能仕様書
```

### Source Code (repository root)

```text
backend/ecs/
├── src/
│   ├── main.py                              # [修正] GET /api/pcs の ownerName 解決（InUse のみ解決、他は null）、GET /api/pcs/{pc_id} 追加
│   └── models/
│       └── pc.py                            # [修正] Pc モデルに owner_name 追加、owner_id を Optional 許容
└── tests/
    └── test_pc_list_and_detail_api.py       # [新規] 一覧 ownerName 解決（非 InUse の null・不明ユーザー含む）、単一取得 200/404 のテスト

frontend/src/
├── types/
│   └── pc.ts                                # [修正] pcName, gpu 追加、model 型整合（不要な modelName 整理）
├── lib/
│   └── utils.ts                             # [修正] formatSpecValue（未入力/Unknown → "-"）、getPcTypeDisplay 追加
├── services/
│   └── pc-api.ts                            # [修正] getPCById、updatePCStatus 追加（requestWithRetry 対応）、returnPC の Authorization ヘッダー付与修正
└── app/pcs/
    ├── page.tsx                             # [修正] モデル名列を formatSpecValue(pc.model) へ修正
    ├── register/
    │   └── page.tsx                         # [修正] モデル名入力欄の必須化と未入力送信ブロック（画面必須）
    └── [pcId]/
        └── page.tsx                         # [新規] PC 詳細画面（スペック表示、返却導線、管理者ステータス更新、404/エラー/ECS待機対応）
```

**Structure Decision**: 既存の `backend/ecs/`（FastAPI）および `frontend/src/`（Next.js App Router）の構成をそのまま踏襲する。Lambda プロキシ（`backend/lambda/`）および AWS CDK（`infrastructure/`）は変更不要。

## Complexity Tracking

> Constitution 違反がないため該当項目なし。
