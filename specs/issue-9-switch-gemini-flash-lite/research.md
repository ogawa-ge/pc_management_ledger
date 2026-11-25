# Research: AI抽出モデルの軽量モデルへの切り替え

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-25

## Decision 1: 本番で「通信エラー」になる原因

- **Decision**: 原因は、AI抽出に使っている `gemini-3.6-flash` の応答の遅れ・混雑であり、Lambda のプロキシが ECS の応答を待つ上限（read timeout 25秒、`backend/lambda/src/main.py`）を超えて 502 を返していることと判断する。
- **Rationale**（2026-11-20 の本番調査の結果）:
  - Lambda のログに `POST /api/pcs/parse-specs 502` が記録され、リクエストを受けてから約26秒後に 502 を返していた。
  - フロントエンドの「AIによる自動抽出中に通信エラーが発生しました」は、API 呼び出しが例外になった場合（502 を含む）に表示される（`frontend/src/app/pcs/register/page.tsx`）。
  - ローカルから本番と同じプロンプトで `gemini-3.6-flash` を呼ぶと、13.0〜28.4秒かかるか、503（high demand）が返った。
- **Alternatives considered**:
  - API キーの問題 → 新しいキーで 402 は解消し、ローカルからの呼び出しは成功しているため否定。
  - ECS の POST が固まる不具合（Issue #30 / 007-fix-pc-registration）→ 11/19 に修正済みで、本番の ECS にも反映済みとみられるため、主な原因ではないと判断。

## Decision 2: 切り替え先のモデル

- **Decision**: `gemini-3.5-flash-lite` を使う。
- **Rationale**:
  - ローカルでの比較（本番と同じプロンプト、同じサンプル入力、各2回）の結果:

    | モデル | 応答時間 | 結果 |
    |---|---|---|
    | `gemini-3.6-flash`（現行） | – | 2回とも 503（混雑） |
    | `gemini-3.8-flash` | 60秒以上 | 2回とも時間切れ |
    | `gemini-3.5-flash-lite` | 1.9〜3.1秒 | 2回とも成功、結果も同じ |
    | `gemini-3.1-flash-lite` | 1.1〜1.9秒 | 成功したが、2回で値が違った |
    | `gemini-flash-lite-latest` | 1.0〜3.9秒 | 成功 |

  - Google 公式の deprecations ページ（2026-11-25 時点）で、`gemini-3.5-flash-lite` は安定版（2026-07-21 提供開始）、提供終了日は未発表、後継モデルの指定なし。Google は新規プロジェクトに「Gemini 4 Hydrogen または 3.5 Flash-Lite」を推奨している。
- **Alternatives considered**:
  - `gemini-3.1-flash-lite`: 結果が安定せず、2027-05-07 以降に提供終了予定のため不採用。
  - `gemini-flash-lite-latest`: Google が中身のモデルを差し替える別名で、知らないうちに挙動が変わるため本番には不採用。
  - 思考レベル（`thinkingLevel`）を下げる: `low` でも 28.4秒、`minimal` は 503 となり、改善しなかったため不採用。

## Decision 3: GB 値の換算方法

- **Decision**: プロンプトの指示（「単位はGB、小数点第1位まで」）は変えず、1000単位・1024単位のどちらで換算するかは AI に任せる。
- **Rationale**: ユーザーの決定（2026-11-25）。`gemini-3.5-flash-lite` は 1024単位の値（メモリ 15.7 / ストレージ 476.9）を返し、`gemini-3.6-flash` はスペック表に近い値（16.0 / 512.0）を返したが、どちらでもよい。
- **Alternatives considered**: プロンプトで換算方法を指定する → ユーザーが不要と判断したため不採用。

## Decision 4: 変更の範囲

- **Decision**: `backend/ecs/src/services/gemini_service.py` の API URL に含まれるモデル名だけを変更する。モデル名を環境変数や CDK の設定に切り出すことはしない。
- **Rationale**: Constitution Layer 4-2（変更の最小化）。モデル名は 1 か所でしか使われておらず、設定化すると CDK（`infrastructure/stacks/ecs_stack.py`）の変更とテストも必要になる。
- **Alternatives considered**:
  - モデル名を環境変数にする → 将来の切り替えは楽になるが、今回の Issue の目的から外れるため不採用（必要になれば別 Issue）。
  - Lambda の待ち時間の上限を延ばす → API Gateway（HTTP API）と Lambda の上限が 30 秒のため、数秒しか延ばせず根本的な解決にならない。
  - 非同期化（受付後に結果を取りに行く方式）→ Lambda・ECS・フロントエンドにまたがる大きな変更になるため、本 Issue の範囲外。
  - `backend/ecs/tests/test_gemini_direct.py` に残っている古いモデル名（`gemini-pro`）の修正 → 本番の処理とは関係しない手動確認用スクリプトのため、範囲外とする。
