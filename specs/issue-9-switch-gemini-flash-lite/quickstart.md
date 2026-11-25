# Quickstart: AI抽出モデルの軽量モデルへの切り替え

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-25

モデル切り替えが正しく動くことを確かめる手順。

## 前提

- Gemini API キー（会社の Google Workspace アカウントで発行した無料枠のキー）を手元に用意する。キーはファイルやチャットに残さない。
- リポジトリ直下の `.venv` が使えること。
- 本番の確認では、AWS の新アカウント（プロファイル `pcledger-new-mfa`）と本番 URL（https://main.dtlqgaeqnt7wq.amplifyapp.com ）を使う。

## 1. 既存の自動テスト（モックを使うもの）が通ること

`backend/ecs` で既存のテストを実行し、失敗がないことを確認する。モデル名の変更でテストが壊れないことの確認であり、Gemini API は呼ばない。

## 2. ローカルで実際に Gemini を呼んで確認する（SC-002, SC-003）

環境変数 `GEMINI_API_KEY` にキーを設定し、`backend/ecs/src/services/gemini_service.py` の `parse_specs` に、サンプル入力（PowerShell の実行結果の JSON）を渡して呼び出す。

**期待する結果**:

- 数秒以内に結果が返る。
- `cpu`, `memory`, `storage`, `os`, `manufacturer`, `model`, `gpu`, `pcName` の 8 項目がすべて入っている。
- `memory` と `storage` は GB 単位の小数点第1位までの数値（例: 15.7 / 476.9、または 16.0 / 512.0）。

## 3. 本番で確認する（SC-001）

ECS を再デプロイして新しいコードを反映したあと、次を行う。

1. 本番 URL に Google アカウントでログインし、PC 登録画面を開く。
2. 画面のコマンドを PowerShell で実行し、結果を貼り付けて AI 抽出を実行する。1回目は、ECS が停止していれば起動を待つ。
3. ECS が起動済みの状態で、AI 抽出を 5 回続けて実行する。

**期待する結果**:

- 5 回とも「通信エラー」にならず、10 秒以内に各項目がフォームに反映される。
- Lambda のログ（`/aws/lambda/LambdaStack-ApiLambda...`）に `POST /api/pcs/parse-specs 502` が出ていない。

## 検証結果（2026-11-25）

### 1. 既存の自動テスト（T001・T003）

- 実行方法: リポジトリのルートで `backend/ecs/venv` の Python から `pytest backend/ecs/tests` を実行（`GEMINI_API_KEY` なし、`test_gemini_api_key.py` と `test_gemini_direct.py` を除外）。ルート直下の `.venv` には pytest が入っていないため、`backend/ecs/venv` を使った。`backend/ecs` から実行すると `test_naming_convention.py` が `backend.ecs...` を import できずに失敗するため、ルートから実行する。
- 変更前（T001）: 60 passed
- 変更後（T003）: 60 passed（新たな失敗なし）

### 2. ローカルでの実呼び出し（T004）

変更後の `parse_specs` をサンプル入力で 2 回呼び出した結果:

| 回 | 時間 | 欠けている項目 |
|---|---|---|
| 1 | 5.7 秒 | なし |
| 2 | 1.2 秒 | なし |

抽出結果（2 回とも同じ）: `cpu`: Intel(R) Core(TM) i5-1235U / `memory`: 15.7 / `storage`: 476.9 / `os`: Microsoft Windows 11 Pro / `manufacturer`: Dell Inc. / `model`: Latitude 5430 / `gpu`: Intel(R) Iris(R) Xe Graphics / `pcName`: SAMPLE-PC
