# Phase 0: Research

本フェーズでは、Technical Contextに残るNEEDS CLARIFICATIONはない（001-pc-managementのスタックをそのまま踏襲するため）。代わりに、実コード調査で判明した不整合・設計判断が必要な項目を「Decision」としてここに記録する。

## Decision 1: バグの根本原因の切り分け

**Decision**: Issue #9は「実装済み機能のバグ」ではなく、「フロントエンドのUI配線が未完成」＋「バックエンドのスキーマ不整合バグ」の複合状態と判断する。

**Rationale**: 実コード調査により以下を確認した。
- `frontend/src/app/pcs/register/page.tsx`には、ユーザーがターミナル実行結果を貼り付けるUIが存在しない。`handleSubmit`は表示用のコマンド文字列自体を抽出APIに渡している。
- 手動入力欄（CPU/メモリ等のstate）はUI上に存在するが、`handleSubmit`で一切参照されておらず、送信データに反映されない。
- `backend/ecs/src/services/gemini_service.py`のプロンプトは`cpu, memory, storage, os, gpu, motherboard`を抽出対象としているが、`backend/ecs/src/services/pc_service.py`は`manufacturer, model, serial_number`を読み取ろうとしており、キーが一致しない。
- `backend/ecs/src/models/pc.py`の`Pc.model`は必須（`str`）だが、上記の不一致により常に`None`となり、Pydanticバリデーションエラー（500）が発生する。

**Alternatives considered**: 「軽微なバグ修正のみ」として扱う案は棄却した。UIの主要な入力経路（貼り付け欄）自体が存在しないため、バグ修正だけでは受け入れ条件を満たせない。

## Decision 2: Gemini API障害時のリトライ戦略

**Decision**: 最大3回の自動リトライを行い、指数バックオフ（例: 1秒→2秒→4秒）を採用する。3回失敗した場合は構造化エラー（`{"error": "...", "retriesExhausted": true}`）を返し、フロントエンドはエラー表示＋手動入力への切り替えを促す。

**Rationale**: `/speckit-clarify`セッションでユーザーが「Bでエラー情報を画面上に表示、リトライ数は3回」と明示的に決定済み（`spec.md`の`Clarifications`参照）。指数バックオフは一時的なネットワーク瞬断・レートリミットに対する一般的なベストプラクティスであり、Gemini API公式クライアントも同様の戦略を推奨している。

**Alternatives considered**: 即時失敗（リトライなし）はユーザー体験を損なうため棄却。無制限リトライはコスト・応答時間の両面でSC-001（5秒以内）と矛盾するため棄却。

## Decision 3: 機微データのフィルタリング方式

**Decision**: Gemini APIへ送信するプロンプト構築前に、抽出対象6項目（cpu, memory, storage, os, manufacturer, model）に無関係なキー（`BiosSerialNumber`等）をサーバー側（`gemini_service.py`）で除去する。クライアント側でのフィルタリングは行わない。

**Rationale**: クライアント側フィルタリングは改ざん・実装漏れのリスクがあり、Security First原則（constitution Layer 1）に基づき、外部送信の最終防衛線はサーバー側に置くべきと判断。

**Alternatives considered**: クライアント側での事前除外（案C、`/speckit-analyze`時点で検討したが不採用）。理由: 貼り付け内容の解析をクライアント・サーバーで二重実装する必要が生じ、Clean Code原則に反する。

## Decision 4: PC登録APIの契約変更（生テキスト再抽出 → 構造化フィールド受け取り）

**Decision**: `POST /api/pcs`の入力を、現行の`specs_text`（生テキスト、サーバー側で再度Gemini抽出）から、`cpu, memory, storage, os, manufacturer, model`の構造化フィールドを直接受け取る方式に変更する。`POST /api/pcs/parse-specs`は「プレビュー用の抽出専用エンドポイント」として現状のまま維持する。

**Rationale**: ユーザーが抽出結果を確認・手動編集できること（FR-005, US2）が要件である以上、登録APIが生テキストを再度サーバー側で解析してしまうと、ユーザーの編集内容が登録直前に上書きされてしまう。UIで一度確定した値をそのまま登録する設計でなければFR-005を満たせない。

**Alternatives considered**: 「生テキストを保持し続け、編集内容も含めて再度テキスト化してGeminiに再送する」案は、往復のたびに抽出結果が微妙に変化するリスク（LLMの非決定性）があり、ユーザーが見た値と登録される値が異なりうるため棄却。

## Decision 5: `Pc.model`必須制約の緩和

**Decision**: `Pc.model: str`（必須）を`Optional[str] = None`に変更する。

**Rationale**: 001-pc-managementのEdge Case方針「判断できる情報だけを利用する」との整合性を取るため、抽出できなかった項目はAPIレベルでは許容し、UI側の送信前バリデーション（必須項目チェック）で担保する方が、既存の「登録自体は失敗させない」という設計思想に合致する。

**Alternatives considered**: `model`にダミー値（例: "Unknown"）を自動設定する案は、実データとダミーデータの区別がつかなくなり、後続の一覧表示・CSV出力で誤解を招くため棄却。

## Decision 6: `serial_number`フィールドの扱い

**Decision**: 今回のスコープでは変更しない（抽出対象に追加せず、`Pc`モデルからも削除しない）。

**Rationale**: `serial_number`は001-pc-managementの`data-model.md`にもUIにも存在しない、コード上のみの残存フィールドである。削除・活用のいずれも002のスコープ（AI抽出フローの完成）を超えるため、`plan.md`のリスクR3として別途整理する。
