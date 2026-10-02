# Phase 1: Data Model

本機能は新規エンティティを追加しない。既存の`PC`エンティティ（[001-pc-management/data-model.md](../001-pc-management/data-model.md)）を変更せずに再利用するが、実コードと既存ドキュメントの間に発見された不整合を、本機能のPhase Aで是正する。

## 既存スキーマとの差分是正

| 項目 | 001の`data-model.md` | 001の`contracts/api.md` | 実コード（是正前） | 本機能での是正内容 |
|---|---|---|---|---|
| PC種別フィールド名 | `manufacturer`, `model` | `manufacturer`, `model` | Geminiプロンプトは`gpu`, `motherboard`を抽出 | プロンプトを`manufacturer`, `model`を抽出するよう修正（Step A1） |
| parse-specsリクエスト | (記載なし) | `{"rawText": "string"}` | `PcParseRequest.specs_text`（camelCaseエイリアス`specsText`） | `contracts/api.md`（本機能）を実コードに合わせて`specsText`に統一（下記参照） |
| `model`の必須性 | 記載なし（テーブル定義のみ） | 記載なし | `Pc.model: str`（必須、Optionalでない） | `Optional[str] = None`に緩和（Step A2） |
| `serial_number` | 未定義（テーブルに存在しない） | 未定義 | `Pc.serial_number: Optional[str]`が存在 | 変更しない（[research.md](./research.md) Decision 6, plan.mdリスクR3） |

## PC エンティティ（変更点のみ、DynamoDBスキーマ自体は無変更）

| Field | Type | 変更内容 |
|---|---|---|
| `cpu` | Optional[String] | 変更なし |
| `memory` | Optional[String] | 変更なし |
| `storage` | Optional[String] | 変更なし |
| `os` | Optional[String] | 変更なし |
| `manufacturer` | Optional[String] | 変更なし（既にOptional） |
| `model` | ~~String（必須）~~ → **Optional[String]** | **本機能で必須制約を緩和**（[research.md](./research.md) Decision 5） |

DynamoDBはスキーマレスであるため、テーブル定義自体（`infrastructure/stacks/database-stack.py`）の変更は不要。Pydanticモデル（アプリケーション層のバリデーション）のみの変更となる。

## リクエスト/レスポンスの構造化フィールド（新規契約、[research.md](./research.md) Decision 4）

`POST /api/pcs`が受け取る構造化フィールドは、Geminiの抽出結果と1:1で対応させる。

| Field | Type | 由来 |
|---|---|---|
| `cpu` | string \| null | 抽出結果 or ユーザー手動編集 |
| `memory` | string \| null | 抽出結果 or ユーザー手動編集 |
| `storage` | string \| null | 抽出結果 or ユーザー手動編集 |
| `os` | string \| null | 抽出結果 or ユーザー手動編集 |
| `manufacturer` | string \| null | 抽出結果 or ユーザー手動編集 |
| `model` | string \| null | 抽出結果 or ユーザー手動編集 |

## 永続化と復旧方針

- **`parse-specs`は無状態**: Gemini抽出処理はDynamoDBへの書き込みを一切伴わない。抽出に失敗しても孤立データやロールバックが必要な中間状態は発生しない。
- **PC登録は単一のアトミックな書き込み**: `PcRepository.create_pc()`は単一の`put_item`で完結し、部分書き込みは発生しない。登録APIが失敗した場合、DynamoDB側には何も残らないため、ユーザーは安全に再送信できる。
- **リトライの冪等性については保証しない**: `pc_id`はリトライ時点の既存データから採番されるため、同一リクエストを2回送信すると2件のPCが作成されうる（001-pc-management Edge Caseで「同時登録の重複はレアケースとして許容」と既に合意済みの方針を踏襲）。UI側は登録ボタンを送信中は`disabled`にすることで多重送信を防止する（Step D2で実装するローディング制御と同一の仕組みを流用）。
- **入力データの保持**: Gemini API呼び出しが3回のリトライ後も失敗した場合、フロントエンドは貼り付け済みのテキスト（`terminalOutput`）をクリアしない。これにより、ユーザーは再試行や手動入力への切り替え時に貼り付け内容を再入力する必要がない（[plan.md](./plan.md) Step D2）。
