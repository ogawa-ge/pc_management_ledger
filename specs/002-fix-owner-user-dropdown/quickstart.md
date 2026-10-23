# Quickstart: オーナーユーザー選択修正

## 前提

- Node.js 18+、Python 3.11+、既存の `.venv` またはBackend依存関係。
- `Users` にテスト用ユーザーを2名以上用意し、管理者ログインを利用できること。
- 実データや実キーは使わず、ローカル/検証環境のダミーデータと環境変数を使う。

## 起動

```powershell
cd D:\workspace\pc_management_ledger\frontend
npm run dev
```

ECS APIを既存手順で起動する場合:

```powershell
cd D:\workspace\pc_management_ledger\backend\ecs
python -m uvicorn src.main:app --reload --port 8000
```

## 自動検証

```powershell
cd D:\workspace\pc_management_ledger\frontend
npm run build

cd D:\workspace\pc_management_ledger\backend
pytest -q
```

Frontendの `npm test` は現状テスト未設定のため、buildを型・コンパイルの基線とする。APIの新規/変更ケースはpytestに追加する。

### 実装前基線（2026-08-19）

- `D:\workspace\pc_management_ledger\frontend` で `npm run build` を実行すると、アプリケーションのコンパイル完了後、既存の `.next/dev/types/validator.ts` が削除済みの `src/pages/index.js` を参照して型検査に失敗する。生成済み `.next` に由来する実装前の環境問題として記録する。
- `D:\workspace\pc_management_ledger\backend` で `pytest -q` を実行すると、`ecs/tests/test_naming_convention.py` の `from backend.ecs.src.models.pc import Pc` を解決できず、`ModuleNotFoundError: No module named 'backend'` で収集に失敗する。実装前から存在する実行ディレクトリ/import path の問題として記録する。

### 実装後の自動検証（2026-08-19）

- `frontend` の `.next` を実装前の stale 生成物として一度削除した後、`npm run build` は production build、TypeScript、全7ページの静的生成まで成功した。
- owner候補・登録・異常系のAPI契約テストは13件すべて成功した。Admin/User/未認証、camelCase、0件、複数ページ、userId重複排除、表示情報欠落、owner未指定・不存在・権限不一致・DynamoDB例外時の保存抑止を含む。
- repository全体を正しい `PYTHONPATH` で実行した結果は39成功・2失敗。2失敗は既存 `backend/ecs/tests/test_gemini_api_key.py` が存在しない旧ファイル名 `src/services/gemini-service.py` を参照する実装前からの問題で、本機能の変更起因ではない。
- `backend` 直下の `pytest -q` は実装前基線と同じ `test_naming_convention.py` の import path 問題で収集失敗する。

### 受け入れ環境での残検証

以下は、ダミーUsersを投入できるECS/DynamoDB受け入れ環境、Azure ADのAdmin/Userセッション、およびブラウザ操作が必要なため、このローカル実装セッションでは未実施。実施時は実データやトークンを本ファイルへ記録しない。

- 管理者画面での複数候補・欠落表示・取得中・0件・失敗後の再試行・選択後削除の目視と操作確認。
- 一般ユーザー本人の実登録、Notebook/Desktop、ターミナルボタンとクリップボード、実Gemini解析、N-/D-採番、DynamoDB保存形式、成功後遷移の統合確認。
- 20〜30件のダミーUsers、ECS ready、人工遅延なしでのブラウザNetwork計測3回。各計測値は未計測であり、30秒以内の合否は未判定。

### T020ダミーUsers（2026-08-19作成）

AWS Account `239188244066`、Region `ap-northeast-1` の `Users` テーブルへ、受け入れ検証専用のダミーUserを25件作成した。既存2件は変更しておらず、作成後のテーブル合計は27件。

- userId: `t020-dummy-001`〜`t020-dummy-025`
- role: 全件 `User`
- `t020-dummy-024`: name欠落時のfallback表示確認用
- `t020-dummy-025`: email欠落時のfallback表示確認用
- emailのドメインには実配送されない `example.invalid` を使用
- ダミーUserはOwner候補・件数・性能確認専用であり、Azure ADログインには利用できない

再作成または存在確認:

```powershell
cd D:\workspace\pc_management_ledger
python scripts\seed-t020-dummy-users.py `
  --expected-account-id 239188244066 `
  --region ap-northeast-1 `
  --table-name Users `
  --count 25
```

スクリプトは `attribute_not_exists(userId)` 条件を使用するため、再実行時に既存レコードを上書きしない。再実行確認では `Created: 0`、`Skipped existing: 25` となった。

T020完了後の削除:

```powershell
cd D:\workspace\pc_management_ledger
python scripts\seed-t020-dummy-users.py `
  --expected-account-id 239188244066 `
  --region ap-northeast-1 `
  --table-name Users `
  --cleanup
```

実AWS DynamoDBを使用したローカルFastAPI統合確認では、`GET /api/users` が200を返し、全27件中25件のダミーUserを取得した。API応答の参考計測3回は `0.237秒`、`0.037秒`、`0.038秒`。これはブラウザ描画と実Lambda/ECS経路を含まないため、SC-002の正式なNetwork計測結果には使用しない。

## シナリオ

1. **複数ユーザー**: 管理者で `/pcs/register` を開く。取得中表示の後、`name (email)` 形式の候補が表示され、1名を選択できることを確認する。
2. **登録紐付け**: 選択、既存のスペック入力/解析、PC登録を行い、レスポンスとDynamoDBのPC `ownerId` が選択した `userId` と一致することを確認する。
3. **取得中**: `/api/users` を遅延させ、selectと登録操作が無効で「取得中」が表示されることを確認する。
4. **取得失敗**: `/api/users` を4xx/5xxにし、明示的なエラーが表示され、空欄のまま登録できないことを確認する。
5. **0件**: Usersを空にし、「登録済みユーザーなし」が表示され、登録できないことを確認する。
6. **権限**: 一般ユーザーで画面を開き、他ユーザーのselectが表示されず、自身の表示だけであることを確認する。本人の `ownerId` による既存PC登録は成功し、API直接呼び出しによる他ユーザー指定は4xxで拒否され、PCが保存されないことを確認する。
7. **競合**: 一覧取得後に対象ユーザーを無効/削除し、登録直前のAPI検証で拒否されPCが作成されないことを確認する。
8. **FR-009回帰**: NotebookとDesktopの両方で、スペック入力、ターミナルボタン、コマンドのクリップボードコピー、Gemini解析、N-/D-管理番号採番を確認する。保存されたPCが `001-pc-management/data-model.md` の既存項目と形式を維持し、登録中は二重送信できず、成功時だけ `/pcs` へ遷移することを確認する。

## 性能計測（SC-002）

1. 受け入れ環境のECS APIがreadyであることを確認し、ブラウザやプロキシへ人工的な遅延・スロットリングを設定しない。
2. Usersに一意な `userId` を持つダミーユーザーを20〜30件用意する。実データは使用しない。
3. ブラウザの開発者ツールでNetwork記録を有効にして `/pcs/register` を開く。
4. `GET /api/users` のRequest開始時刻から、全候補が描画されselectが操作可能になった時刻までを計測する。ECSのcold startと管理者の判断時間は含めない。
5. 同じ条件で3回実施し、各計測値と環境条件を本ファイルへ記録する。3回すべてが30秒以内なら合格とする。

## 期待結果

上記シナリオが全て成功し、`spec.md` の受け入れシナリオ AC1-1〜AC1-3、AC2-1〜AC2-2、FR-001〜FR-009、SC-001〜SC-005を満たす。既存のPC種別、スペック、採番、返却処理には回帰がない。