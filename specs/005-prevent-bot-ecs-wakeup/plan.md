# Implementation Plan: ボットアクセスによる不要起動防止と自動停止の確実化

**Branch**: `005-prevent-bot-ecs-wakeup` | **Date**: 2026-11-06 | **Spec**: [spec.md](file:///c:/Users/hagihara/pc_management_ledger/specs/005-prevent-bot-ecs-wakeup/spec.md)

**Input**: Feature specification from `/specs/005-prevent-bot-ecs-wakeup/spec.md` (GitHub Issue #27)

---

## Summary

インターネット上のボットや検索クローラーによる `/robots.txt` 等の非業務パスアクセスで発生していた ECS 不要起動の根本遮断と、単発起動要求・早期離脱時に `lastActivityAt` が未設定となり定期パトロールで自動停止がスキップされる不具合の修正を行う。

FastAPI のルーティングを `/api/{path:path}` に制限して非業務アクセスを即座に 404 遮断するとともに、`SystemActivity` テーブルへの起動要求受付時点で `lastActivityAt` を現在時刻で初期化し、孤立した起動中タスクも規定アイドル時間（2時間）経過後に安全に自動停止するようロジックを強化する。

新規ライブラリや外部技術の追加は一切行わず、既存の FastAPI・boto3・DynamoDB の範囲内で最小限のコード修正により完全に対策する。

---

## Technical Context

**Language/Version**: Python 3.11 / 3.12  
**Primary Dependencies**: FastAPI (0.104.1), boto3 (1.34.11), botocore, mangum (0.17.0) （※新規ライブラリ追加なし）  
**Storage**: Amazon DynamoDB (`SystemActivity` テーブル、キー: `entityId="global"`, スキーマ変更なし)  
**Testing**: pytest (FastAPI TestClient, unittest.mock, botocore stub)  
**Target Platform**: AWS Lambda (Python 3.11) + AWS ECS Fargate  
**Project Type**: Serverless Web API Proxy / Hybrid Backend Architecture  
**Performance Goals**: 非業務パス・ボット遮断時のレスポンス時間 < 50ms、起動中通知（503）時のオーバーヘッド最小化  
**Constraints**: 
- Constitution Layer 4 厳守: Issue #27 のバグ修正に限定し、無関係なリファクタリングや画面修正は行わない。
- ユーザー指定制約: 既存技術のみを使用し、新規技術・ライブラリの導入は行わない。
- AWS コスト最小化: ボットアクセスによる稼働時間を月間0分にし、放置タスクを最大2時間15分以内に100%停止させる。  
**Scale/Scope**: バックエンド Lambda 関数 2 ファイル (`main.py`, `ecs_manager.py`) および関連テストの修正。

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 憲法規定 / 原則 | 適合状況 | 判定 |
|---|---|---|
| **Layer 1: Output Language** | すべての設計ドキュメント、計画、タスク、解説を日本語で記述 | **PASS** |
| **Layer 1: No Hallucination** | `spec.md`, `data-model.md`, `contracts/api.md` を一次情報として参照し、既存の `SystemActivity` スキーマを正確に使用 | **PASS** |
| **Layer 1: Security First** | 機密情報や実キーのハードコードなし。内部通信の署名検証ロジックを完全に維持 | **PASS** |
| **Layer 2: Project Mission** | ボットによる無駄な ECS 稼働と課金を完全に排除し、月額コスト最小化に直接寄与 | **PASS** |
| **Layer 3: Hybrid Responsibility** | 軽量ルーティング・受付判定・自動停止制御を Lambda で行い、業務処理のみを ECS で行う役割分担を維持 | **PASS** |
| **Layer 3: Cost-Awareness** | 2時間未使用での確実な自動停止を補強 | **PASS** |
| **Layer 3: Code Standard** | 既存のディレクトリ構成・命名規約に準拠（kebab-case / PEP 8 snake_case） | **PASS** |
| **Layer 4: Strict Scope Boundaries** | Issue #27 に特化。フロントエンド、DBスキーマ、認証基盤、CDKスタックには一切手を加えない最小変更 | **PASS** |

---

## Project Structure

### Documentation (this feature)

```text
specs/005-prevent-bot-ecs-wakeup/
├── spec.md              # 仕様書 (User Stories, Requirements, Success Criteria)
├── checklists/
│   └── requirements.md  # 仕様レビュー・品質チェックリスト
├── research.md          # 技術調査と決定事項 (ルーティング制限, lastActivityAt初期化方針)
├── data-model.md        # SystemActivity の状態管理と属性定義
├── contracts/
│   └── api.md           # API コントラクト (ルーティングゲート, 404/503/200 レスポンス)
├── quickstart.md        # 検証ガイド・テスト実行手順
├── plan.md              # 本実装計画書
└── tasks.md             # タスクリスト (speckit.tasks で生成)
```

### Source Code (repository root)

```text
backend/
└── lambda/
    ├── src/
    │   ├── main.py                     # 【変更】ECSプロキシのルートを /api/{path:path} に制限し 404 遮断
    │   └── services/
    │       └── ecs_manager.py          # 【変更】lastActivityAt の初期化と孤立タスク停止ロジックの強化
    └── tests/
        ├── test_lambda_ecs_proxy.py    # 【変更/追加】非業務パス 404 遮断テスト
        ├── test_lambda_activity_tracking.py # 【変更/追加】lastActivityAt 初期化・アイドル停止テスト
        └── test_ecs_manager.py         # 【変更/追加】孤立タスクの自動停止テスト
```

**Structure Decision**:
既存の `backend/lambda/` の構成を踏襲。新たなディレクトリやパッケージは作成せず、修正対象ファイルのみを最小限の変更で対応する。

---

## Implementation Details & Strategy

> **Note（フェーズ番号について）**: 以下の「Phase 1〜3」はコード実装上の作業グループであり、`tasks.md` の「Phase 1〜6（Setup / Foundational / User Story 1〜3 / Polish）」とは別の区分です。実装の実行順序は必ず `tasks.md` の依存関係グラフに従ってください。

### Phase 1: ルーティングゲートの制限 (`backend/lambda/src/main.py`)
1. `@app.api_route("/{path:path}", ...)` を `@app.api_route("/api/{path:path}", ...)` に変更する。
2. 転送先 URL 生成時に、`target_url = f"http://{public_ip}:80/api/{path}{query_string}"` とし、署名対象パスを `f"/api/{path}{query_string}"` とする。
3. 非 `/api/*` パス（`/robots.txt`, `/favicon.ico` 等）に対するアクセスは、FastAPI のデフォルトルーティングにより自動的に HTTP 404 Not Found となり、ECS 起動関数（`ensure_ecs_running`）は呼び出されない。

### Phase 2: 活動時刻の初期化と孤立タスク停止の強化 (`backend/lambda/src/services/ecs_manager.py`)
1. **初期活動時刻の設定**:
   - 正規業務 API 要求到着時、まず `record_request_accepted` が呼び出され、続いて停止中であれば `_claim_start` が呼び出される。この両方の `UpdateExpression` において `lastActivityAt=if_not_exists(lastActivityAt, :now)`（または起動開始時の現在時刻設定）を追加する。
   - 初回要求受付時および ECS 起動要求時に、`lastActivityAt` が現在時刻（ISO8601）で確実に初期化されることを保証する。
2. **`check_and_auto_sleep` の停止条件拡張**:
   - `lastActivityAt` が未設定または読み取れない場合のフォールバックとして、`startRequestedAt`（第1候補）→ `lastAcceptedAt`（第2候補）の優先順位で評価する。両方欠落する場合は `invalid_runtime_activity` として監査ログを記録し、既存の安全装置（フェイルオープン：停止見送り）に委ねる。
   - `runtimeState` が `STARTING` のまま孤立しているタスクについて、`startLockExpiresAt <= nowEpoch` かつ `inFlightCount == 0` かつアイドル時間（7,200秒＝2時間）を経過している場合、停止処理（`STOPPING` -> `STOPPED`）を実行できるように条件式（`ConditionExpression`）を拡張する。

### Phase 3: テストの作成と品質保証 (`backend/lambda/tests/`)
1. `test_lambda_ecs_proxy.py`:
   - `/robots.txt`、`/favicon.ico` 等へのアクセスで 404 が返り、ECS 起動処理が一切呼び出されないことを検証（T004 → T012 の順番で書き込み）。
   - 正規の `/api/pcs` へのアクセスで、停止時は 503（`Retry-After: 15`）、稼働時は正しくプロキシ転送されることを検証。
2. `test_lambda_activity_tracking.py` / `test_ecs_manager.py`:
   - 起動要求時に `lastActivityAt` が初期化されることを検証（T007）。
   - 後続リクエスト 0 件で 2 時間経過後に `check_and_auto_sleep` を実行した際、正常に自動停止（`auto_slept`）へ遷移すること、およびフォールバック評価を検証（T008）。
3. 監査ログ（FR-007）: `_log_audit` による監査ログが起動要求受付時・`lastActivityAt` 初期化時・自動停止判定時に出力されることを確認し、欠落がある場合は追加する（T016）。

### 要件・テスト・タスク カバレッジマトリクス

| 要件 / 成功基準 | 対応ストーリー | 実装タスク | 検証テストタスク |
|---|---|---|---|
| **FR-001, SC-001** (非業務パス 404 遮断) | US1 (P1) | T005, T006 | T004, T015 |
| **FR-002, SC-003** (正規 API 503 起動・転送維持) | US3 (P2) | T005, T006, T013 | T012, T014, T015 |
| **FR-003** (`lastActivityAt` 初期化) | US2 (P1) | T003, T009 | T007, T015 |
| **FR-004, FR-005, SC-002** (2時間後自動停止・孤立救済) | US2 (P1) | T010, T011 | T008, T015 |
| **FR-006** (停止中と新規要求の競合・再起動優先) | US3 (P2) | T013 | T013, T014 |
| **FR-007** (監査ログ記録) | US2 / Cross-Cutting | T016 | T015, T016 |
| **SC-004** (ボット起因の不要稼働時間 0 分) | US1, US2 | T005, T009, T010, T011 | T004, T007, T008, T014 |

---

## Complexity Tracking

*Constitution 違反なし。複雑性の追加はありません。*

| 項目 | 理由 | 代替案を却下した理由 |
|---|---|---|
| なし | 既存のコードベース・設計方針をそのまま活用した最小修正 | N/A |
