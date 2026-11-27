# Quickstart Validation Guide: Issue #33

**Feature**: PC一覧の表示不整合修正およびPC詳細画面の実装 (`specs/33-fix-pc-list-and-detail`)  
**References**: [spec.md](./spec.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md)

---

## 1. 前提条件

- ブランチ `issue-33-fix-pc-list-and-detail` にチェックアウト済みであること
- バックエンド（Python / pytest）およびフロントエンド（Node.js / Next.js）の依存関係がインストール済みであること

---

## 2. 自動テストによる検証

### 2.1 バックエンド単体・API テスト（ECS / FastAPI）

```powershell
cd backend/ecs
pytest
```

**期待結果**:
- 既存テスト（`test_owner_registration_api.py`, `test_idempotent_pc_operations.py`, `test_naming_convention.py` 等）がすべてパスすること
- 新規追加テスト（`GET /api/pcs` の `ownerName` 解決・非 `InUse` ステータス（`Unused` / `PendingDisposal` / `Disposed`）の `null` 扱い・不明ユーザーフォールバック、`GET /api/pcs/{pc_id}` の 200/404）がすべてパスすること

### 2.2 フロントエンド ビルド・型チェック

```powershell
cd frontend
npx tsc --noEmit
npm run build
```

**期待結果**:
- TypeScript の型エラーなくビルドが成功すること（`frontend/src/app/pcs/[pcId]/page.tsx` を含む）

---

## 3. エンドツーエンド手動確認シナリオ

1. **PC 新規登録でのモデル名必須化確認（US1 / FR-003）**:
   - `/pcs/register` を開き、モデル名を空欄またはスペースのみにして登録ボタンを押す
   - **期待結果**: 必須エラーが表示され、登録がブロックされる
   - モデル名を入力して登録すると成功し、`/pcs` へ遷移する
2. **PC 一覧のユーザー名・モデル名表示確認（US1 / FR-001〜FR-004）**:
   - `/pcs` を開く
   - **期待結果**: 登録した PC の「ユーザー」列にオーナー氏名、「モデル名」列に登録したモデル名が表示される（既存データで未入力/`Unknown` の場合は `-`、オーナー未割当は「未割り当て」）
3. **PC 詳細画面の表示確認（US2 / FR-005〜FR-007）**:
   - `/pcs` および `/pcs/unused` の「詳細」リンクをクリックする
   - **期待結果**: 404 にならず `/pcs/{pcId}` が表示され、管理番号・オーナー名・PC種別・ステータス・全スペック・登録/更新日時が確認できる。「PC一覧に戻る」で `/pcs` へ戻れる
4. **存在しない管理番号へのアクセス確認（US2 / FR-010）**:
   - `/pcs/N-999999` へ直接アクセスする
   - **期待結果**: 「指定された PC は見つかりませんでした」の案内と「PC一覧に戻る」ボタンが表示される
5. **返却手続き導線・返却送信・管理者ステータス更新の確認（US3 / FR-008, FR-009）**:
   - 一般ユーザーで自身の「利用中」PC 詳細を開く → 「返却手続き」ボタンが表示され `/pcs/{pcId}/return` へ遷移し、返却理由・状態を入力して送信すると 401 エラーにならず返却完了し、一覧・詳細で「未使用」「未割り当て」と表示される。ステータス変更 UI は表示されない
   - 一般ユーザーで他人の PC または「利用中」以外の PC 詳細を開く → 「返却手続き」ボタンが表示されない
   - 管理者で PC 詳細を開く → ステータス変更 UI が表示され、ステータスを更新すると画面表示と `/pcs` 一覧の両方に反映される
