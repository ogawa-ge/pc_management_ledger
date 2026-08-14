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