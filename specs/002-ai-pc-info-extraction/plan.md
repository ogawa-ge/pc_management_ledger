# Implementation Plan: AI PC情報取得機能

**Branch**: `002-ai-pc-info-extraction` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-ai-pc-info-extraction/spec.md`（GitHub Issue #9対応）

## Summary

Issue #9「AIによるPC情報取得機能が未実装」への対応。実コード調査の結果、本機能は「バグ」というより「エンドツーエンドの配線が未完成」＋「実装済み部分のスキーマ不整合バグ」の複合状態であることが判明している（詳細は[研究フェーズ](./research.md)参照）。本計画は、001-pc-managementと同一のスタック・UI方針を前提に、既存コードの不整合を是正しながら、貼り付け入力→AI抽出→自動反映→手動編集→登録のフローを段階的に完成させる。

## Technical Context

**Language/Version**: TypeScript (Next.js), Python (FastAPI) — 001-pc-managementと同一。新規言語・フレームワークの追加なし。

**Primary Dependencies**: Next.js, FastAPI, Gemini API（`gemini-2.5-flash`） — 001-pc-managementと同一。

**Storage**: Amazon DynamoDB（`PCs`テーブル） — 新規テーブル・新規エンティティなし。既存スキーマのフィールド整合性のみ是正。

**Testing**: Jest (Frontend), pytest (Backend) — 001-pc-managementと同一。

**Target Platform**: AWS（Amplify + Lambda + ECS） — 001-pc-managementと同一。新規AWSリソースの追加なし。

**Project Type**: Web Application（既存のfrontend/backend構成を変更せず利用）

**Performance Goals**: 貼り付けから抽出反映まで5秒以内（SC-001）。Gemini API障害時は最大3回リトライ（FR-007）。

**Constraints**: 既存のコスト制約を維持（新規AWSリソース追加なし、ALB非利用）。既存のPC登録フロー（001-pc-management US2）の後方互換性を維持する。

**Scale/Scope**: 20〜30名ユーザー。新規エンティティなし。既存`register`画面の修正が中心。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Layer 1 - 日本語出力**: 本ドキュメント一式は日本語で記述。
- [x] **Layer 1 - スキーマ推測の禁止**: `data-model.md`／`contracts/api.md`を一次ソースとする。既存の001-pc-management側`contracts/api.md`と実コード（`gemini_service.py`, `pc.py`）の間に不整合（`rawText` vs `specsText`、`manufacturer/model` vs `gpu/motherboard`）が見つかっているため、Phase 1でこれを是正し一次ソースとして再定義する（[data-model.md](./data-model.md) Section「既存スキーマとの差分是正」参照）。
- [x] **Layer 1 - Security First**: FR-008（機微データの送信前除外）を踏まえ、Gemini APIへ送信するペイロードから抽出対象外の識別子（BIOSシリアル番号等）を除外する設計とする。ダミーデータ・環境変数運用を継続。
- [x] **Layer 3 - Hybrid Responsibility**: 本機能はECS（`backend/ecs`）と Amplify上のフロントエンドのみで完結し、Lambda側の変更は不要。
- [x] **Layer 3 - Cost-Awareness**: 新規AWSリソースを追加しない。ECS自動スリープ挙動（FR-014/015, 001側）に影響なし。
- [x] **Layer 3 - Clean Code / kebab-case**: 新規・変更ファイルは既存の命名規則（kebab-case）を踏襲。
- [x] **Layer 3 - AI Logic**: 抽出ロジックはGeminiのプロンプトベース抽出を維持し、正規表現による硬直的パースへの置き換えは行わない。リトライ（FR-007）はネットワーク/API障害対策であり、抽出ロジック自体の変更ではない。
- [ ] **Layer 3 - Ubiquitous Language**: 新用語（「貼り付け入力」「抽出リトライ」等）を`docs/ubiquitous-language.md`に追加する作業をPhase 1のタスクとして計上（未実施、Phase 1で対応）。

Constitution違反なし。Complexity Trackingへの記載は不要。

## Project Structure

### Documentation (this feature)

```text
specs/002-ai-pc-info-extraction/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output（手動検証チェックリスト）
├── contracts/
│   └── api.md            # Phase 1 output（parse-specs / pcs 契約の是正）
└── tasks.md              # Phase 2 output (/speckit-tasks command)
```

### Source Code（変更対象、リポジトリルート起点）

```text
frontend/
└── src/
    ├── app/pcs/register/page.tsx     # 貼り付け入力欄の追加、抽出結果の反映、手動編集配線、エラー/リトライUI
    └── services/pc-api.ts            # parseSpecs/registerPC のリクエスト形状を構造化フィールドベースに見直し

backend/ecs/
└── src/
    ├── services/gemini_service.py    # 抽出項目のスキーマ整合、リトライ実装、機微データ除外
    ├── services/pc_service.py        # create_pc() の入力を構造化フィールド受け取りに変更（研究フェーズで決定）
    ├── models/pc.py                  # model必須制約の見直し
    └── main.py                       # /api/pcs, /api/pcs/parse-specs のリクエストモデル調整

backend/ecs/tests/
└── test-gemini-accuracy.py           # manufacturer/model抽出・リトライ・機微データ除外のテストケース追加

docs/
└── ubiquitous-language.md            # 新用語の追加
```

**Structure Decision**: 001-pc-managementと同一のWebアプリケーション構成（Next.js frontend + FastAPI/ECS backend）を踏襲し、新規ディレクトリ・新規サービスは追加しない。すべて既存ファイルの修正で完結する。

## 実装マイルストーン（フェーズ）一覧

| フェーズ | 目的 | 前提 |
|---|---|---|
| **Phase A** | バックエンドの抽出スキーマ整合・信頼性向上（Bug 3, 4 解消 / FR-003, FR-007, FR-008） | なし（最初に着手） |
| **Phase B** | フロントエンドに貼り付け入力UIを新設（Bug 1 解消 / FR-002） | なし（Aと並行可） |
| **Phase C** | 抽出結果の自動反映と手動編集の配線（Bug 2 解消 / FR-004, FR-005） | Phase A・B 完了後 |
| **Phase D** | エラー・リトライ状態のUI実装（FR-006, FR-007のUI側 / SC-003, SC-004） | Phase C 完了後 |
| **Phase E** | 検証・受け入れテスト（SC-001, SC-002含む全体検証） | Phase D 完了後 |

## 各フェーズのステップ

### Phase A: バックエンド抽出スキーマ整合・信頼性向上

**A1. Geminiプロンプトの抽出項目をPCエンティティに整合させる**
- **目的**: 抽出結果と`Pc`エンティティのフィールド不一致（`gpu`/`motherboard` vs `manufacturer`/`model`）を解消する。
- **作業内容**: `gemini_service.py`のプロンプトを `cpu, memory, storage, os, manufacturer, model` の6項目（`docs/ubiquitous-language.md`の「Specs」定義と一致）に修正。`gpu`/`motherboard`は削除。
- **Done条件**: `parse_specs()`の返り値キーが`data-model.md`の6項目と完全一致することをユニットテストで確認。
- **影響ファイル案**: `backend/ecs/src/services/gemini_service.py`, `backend/ecs/tests/test-gemini-accuracy.py`

**A2. `model`フィールドの必須制約を緩和**
- **目的**: 抽出できなかった場合にPydanticバリデーションエラーで500になる不具合（診断済みBug）を解消する。
- **作業内容**: `Pc.model: str`（必須）を`Optional[str] = None`に変更。未取得時は`None`のまま許容し、フロントの必須バリデーション（登録ボタン押下時）で担保する。
- **Done条件**: manufacturer/modelが未抽出のケースでも登録APIが500を返さない。
- **影響ファイル案**: `backend/ecs/src/models/pc.py`, `backend/ecs/src/services/pc_service.py`

**A3. Gemini API呼び出しのリトライ実装（FR-007）**
- **目的**: Gemini API障害時に最大3回まで自動リトライする。
- **作業内容**: `gemini_service.py`にリトライループ（指数バックオフ推奨）を実装。3回失敗時は`{"error": "...", "retriesExhausted": true}`形式の構造化エラーを返す。
- **Done条件**: 疑似的にAPIエラーを注入するテストで、3回リトライ後にエラーが返ることを確認。
- **影響ファイル案**: `backend/ecs/src/services/gemini_service.py`, `backend/ecs/tests/test-gemini-accuracy.py`

**A4. 機微データの送信前除外（FR-008）**
- **目的**: BIOSシリアル番号等、抽出対象6項目に含まれない識別子をGemini API送信前に除外する。
- **作業内容**: 受け取ったJSONテキストをパースし、抽出対象外キー（`BiosSerialNumber`等）をプロンプト組み立て前に除去するサニタイズ処理を追加。
- **Done条件**: `BiosSerialNumber`を含むテスト入力で、Gemini APIへの実リクエストペイロードに当該値が含まれないことをモックテストで確認。
- **影響ファイル案**: `backend/ecs/src/services/gemini_service.py`

### Phase B: フロントエンドに貼り付け入力UIを新設

**B1. ターミナル出力貼り付け用テキストエリアの追加**
- **目的**: ユーザーが実行結果を入力できるUIを新設する（現状は存在しない）。
- **作業内容**: `register/page.tsx`に`<textarea>`（例: `id="terminalOutput"`）を新設し、`useState`で管理。ラベル「ターミナル実行結果を貼り付けてください」を明示的に関連付ける。
- **Done条件**: コマンド表示エリアの下に貼り付け欄が表示され、入力値がstateに反映される。
- **影響ファイル案**: `frontend/src/app/pcs/register/page.tsx`

**B2. 貼り付け内容を抽出APIに渡すよう修正**
- **目的**: 診断済みBug（コマンド文字列そのものを送信していた誤り）を解消する。
- **作業内容**: `handleSubmit`内の`parseSpecs(terminalCommand)`を、B1で新設した`terminalOutput`（実際の貼り付け内容）に差し替える。
- **Done条件**: 実際の`Get-ComputerInfo`出力を貼り付けて送信すると、コマンド文字列ではなく貼り付け内容がAPIに送信されることをネットワークログで確認。
- **影響ファイル案**: `frontend/src/app/pcs/register/page.tsx`

### Phase C: 抽出結果の自動反映と手動編集の配線

**C1. フォームフィールドの是正と抽出結果の自動反映（FR-004）**
- **目的**: 現行フォームには`manufacturer`/`model`欄が存在せず、代わりにPcエンティティに存在しない`gpu`欄がある不整合を是正した上で、抽出結果を自動反映する。
- **作業内容**: `manufacturer`・`model`の入力欄を追加し、`gpu`欄は削除（Specs定義外のため）。`parseSpecs()`の戻り値を`setCpu`/`setMemory`/`setStorage`/`setOs`/`setManufacturer`/`setModel`に反映。
- **Done条件**: 貼り付け→抽出後、CPU・メモリ・ストレージ・OS・メーカー・モデルの各欄に値が自動入力される。
- **影響ファイル案**: `frontend/src/app/pcs/register/page.tsx`

**C2. 手動編集を送信データに反映（FR-005）**
- **目的**: 診断済みBug（手動編集した値が送信データに反映されない）を解消する。
- **作業内容**: `handleSubmit`が`registerPC()`に渡すデータを、stateから構築した構造化オブジェクト（`cpu, memory, storage, os, manufacturer, model`）に変更する。**設計判断（要合意、リスクR1参照）**: `POST /api/pcs`の契約を「生テキストを受け取りサーバー側で再度Gemini抽出する」方式から「クライアントで確定済みの構造化フィールドを受け取る」方式に変更する。これを行わないと、サーバー側で`create_pc()`が`specs_text`を再度Geminiに投げて上書きしてしまい、ユーザーの手動編集が反映されない。
- **Done条件**: 自動反映後に手動でCPU欄を書き換えて登録すると、書き換え後の値でPCが登録される。
- **影響ファイル案**: `frontend/src/app/pcs/register/page.tsx`, `frontend/src/services/pc-api.ts`, `backend/ecs/src/main.py`, `backend/ecs/src/services/pc_service.py`, `specs/002-ai-pc-info-extraction/contracts/api.md`

### Phase D: エラー・リトライ状態のUI実装

**D1. JSON解析エラー表示（FR-006）**
- **目的**: 貼り付け内容が不正な場合に登録前にブロックする。
- **作業内容**: 送信前にクライアント側で`JSON.parse`を試行し、失敗時はエラーメッセージを表示してAPI呼び出しをスキップする。
- **Done条件**: 不正なJSONを貼り付けて送信すると、APIを呼ばずにエラーメッセージが表示される。
- **影響ファイル案**: `frontend/src/app/pcs/register/page.tsx`

**D2. Gemini API失敗時のローディング・エラー表示（FR-007のUI側, SC-004）**
- **目的**: 抽出中の状態表示と、3回リトライ後の失敗時に手動入力を促す。
- **作業内容**: 抽出中はローディング表示（ボタン`disabled`＋`aria-busy`）。バックエンドが`retriesExhausted: true`を返した場合、エラーメッセージを表示し「手動で入力してください」の案内を出す。**貼り付け内容（textarea）はエラー時もクリアしない**（再試行時のデータ損失防止）。
- **Done条件**: バックエンドのモックエラーレスポンスに対し、3回リトライ後のエラーメッセージがUIに表示され、貼り付け内容が保持されている。
- **影響ファイル案**: `frontend/src/app/pcs/register/page.tsx`, `frontend/src/services/pc-api.ts`

### Phase E: 検証・受け入れテスト

**E1. バックエンド単体テスト拡充**
- **目的**: SC-002（抽出精度）、FR-007/FR-008のテストカバレッジ確保。
- **作業内容**: `test-gemini-accuracy.py`に manufacturer/model抽出ケース、リトライケース、機微データ除外ケースを追加。
- **Done条件**: pytest全件成功。
- **影響ファイル案**: `backend/ecs/tests/test-gemini-accuracy.py`

**E2. 手動E2E検証**
- **目的**: SC-001〜SC-004を実環境（Windows 11 / PowerShell）で確認する。
- **作業内容**: [quickstart.md](./quickstart.md)のチェックリストに沿って実施。
- **Done条件**: 全チェック項目パス。
- **影響ファイル案**: なし（検証のみ）

## 受け入れ条件との対応（Step → AC）

| Step | 対応する受け入れ条件（spec.md） |
|---|---|
| A1 | FR-003（Gemini抽出6項目） |
| A2 | US1 Acceptance Scenario 2（判断可能な項目のみ反映、欠落は空欄） |
| A3 | FR-007, US1 Acceptance Scenario 4, SC-004 |
| A4 | FR-008（機微データ除外） |
| B1 | FR-002（貼り付け入力欄） |
| B2 | US1 Acceptance Scenario 1（貼り付け→抽出） |
| C1 | FR-004（自動反映） |
| C2 | FR-005, US2 Acceptance Scenario 1（手動編集の反映） |
| D1 | FR-006, US1 Acceptance Scenario 3, SC-003 |
| D2 | FR-007のUI側, US1 Acceptance Scenario 4, SC-004 |
| E1 | SC-002（抽出精度95%以上） |
| E2 | SC-001（5秒以内反映）, SC-001〜SC-004 全体 |

## リスク・未決事項（決めるべき順番）

1. **R1（最優先・Phase C着手前に決定必須）**: `POST /api/pcs`の契約を「生テキスト＋サーバー側再抽出」から「クライアント確定済みの構造化フィールド受け取り」に変更するか。
   - 推奨: 変更する。理由: 変更しない限り、手動編集（FR-005）が登録直前にサーバー側の再抽出で上書きされてしまう。
2. **R2（Phase A2着手前に決定必須）**: `Pc.model`を必須のままにするか、Optionalに緩和するか。
   - 推奨: Optionalに緩和し、フロントの送信前バリデーションで実質必須を担保する。
3. **R3（Phase A1着手前に決定）**: `Pc.serial_number`フィールド（`data-model.md`未記載だがコードに存在）を今回削除するか、将来のバーコード/シリアル読み取り機能のために残すか。
   - 推奨: 002のスコープ外として現状維持（削除も抽出対象追加もしない）。別issueで扱う。
4. **R4（002スコープ外、別途整理）**: `register/page.tsx`の「PC名」入力欄は`Pc`エンティティに存在しないフィールドであり、現状も送信されていない。002では触れず、別issueとして切り出すか、001側の設計判断を仰ぐか。
5. **R5（実装事項、決定不要）**: `manufacturer`/`model`欄がフォームに存在しない、`gpu`欄が余剰である点はPhase C1で機械的に是正する。

## Complexity Tracking

> Constitution Check に違反なし。記載事項なし。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
