# Research & Technical Decisions: PC一覧の表示不整合修正およびPC詳細画面の実装

**Feature**: Issue #33 (`specs/33-fix-pc-list-and-detail`)  
**Date**: 2026-11-25

---

## 1. PC一覧・詳細における `ownerName` 解決方式

- **Decision**: バックエンド（Amazon ECS / FastAPI）の `GET /api/pcs` および新規 `GET /api/pcs/{pc_id}` 内で `Users` テーブルからオーナー名を解決し、レスポンスモデルの `ownerName` フィールドとして返却する。
  - `GET /api/pcs` では `UserRepository.get_all_users()` で 1 回だけユーザー一覧を取得し、`user_id -> name (fallback: email)` の辞書マップを作成して各 PC に割り当てる（N+1 クエリ回避）。
  - `GET /api/pcs/{pc_id}` では `UserRepository.get_user_by_id(owner_id)` で単一ユーザーを取得して解決する。
  - `ownerId` が空または `None` の場合、および `status != "InUse"`（`Unused` / `PendingDisposal` / `Disposed` — DB には過去の `ownerId` が残っていても現在利用中ではない状態）の場合は `ownerName = None`（フロントエンドで「未割り当て」と表示）。
  - `status == "InUse"` かつ `ownerId` が設定されているが `Users` テーブルに該当ユーザーが存在しない場合は `ownerName = "不明なユーザー"` とし、画面エラーを防ぎつつ未割り当てと区別できるようにする。
- **Rationale**:
  - `GET /api/users` は管理者専用（`get_admin_principal`）であり、一般ユーザーが PC 一覧画面から `/api/users` を呼んでフロントエンド側で名前解決することは権限設計上できない。
  - Issue #30 にて `EcsStack` へ `Users` テーブルの読み取り権限が付与済みのため、インフラ（AWS CDK）の追加変更なしで安全に実装できる。
  - ユーザー数は 20〜30 名の小規模運用であり、一覧時の 1 回スキャンは十分に高速でコスト影響もない。
- **Alternatives considered**:
  - **フロントエンド側で `/api/users` を呼んで結合する案**: 一般ユーザーに `/api/users` のアクセス権を与える必要があり、最小権限の原則に反するため却下。
  - **PC 登録時に `ownerName` を `PCs` テーブルへ非正規化保存する案**: 既存データの一括マイグレーションが必要になり、ユーザーの氏名変更時にも不整合が生じるため却下。

---

## 2. 一覧の「モデル名」表示修正と新規登録時のモデル名必須化

- **Decision**:
  - フロントエンド全PC一覧画面（`frontend/src/app/pcs/page.tsx`）の参照フィールドを誤った `pc.modelName` からバックエンドの正規フィールドである `pc.model` へ統一する。
  - 既存の 5 列構成（「管理番号」「ユーザー」「モデル名」「ステータス」「操作」）を維持する。
  - PC 新規登録画面（`frontend/src/app/pcs/register/page.tsx`）においてモデル名入力欄を必須化し、未入力（空白のみ含む）の場合は送信をブロックしてエラーメッセージを表示する（AI 抽出でモデル名が取得できなかった場合も、利用者が手入力して登録する）。
  - モデル名の必須チェックはフロントエンド画面のみで行い、バックエンド `POST /api/pcs` の既存バリデーション・テスト契約は変更しない。
  - 既存登録データ等で `model` やその他任意スペック項目が未入力・`None`・`"Unknown"`（大文字小文字問わず）の場合は、共通フォーマット関数（`formatSpecValue`）により統一表記 `"-"` として表示する。
- **Rationale**:
  - Issue #33 の仕様確定（Option B + 画面上モデル名必須化）に合致し、既存の一覧レイアウトや型定義（`PC.model`）との整合性が最も高い。
  - 画面上での必須チェックにより通常の登録導線での未入力を防ぎつつ、既存の `specsText` ベースのバックエンドテストや API 互換性を壊さずに済む。
- **Alternatives considered**:
  - **バックエンドのレスポンスに `modelName` エイリアスを追加する案**: 既存の未使用PC一覧（`frontend/src/app/pcs/unused/page.tsx`）や `specs/001-pc-management/contracts/api.md` ではすでに `model` が正となっているため、フロントエンド一覧画面側を `model` に統一する方がフィールド重複を防げる。

---

## 3. 単一 PC 取得 API（`GET /api/pcs/{pc_id}`）と認証・ルーティング

- **Decision**:
  - `backend/ecs/src/main.py` に `GET /api/pcs/{pc_id}`（`response_model=Pc`）を追加する。
  - `PCs` テーブルから `pcId` をキーに `get_item` で取得し、存在しない場合は `404 Not Found`（`{"detail": "PC not found: <pc_id>"}`）を返す。
  - フロントエンドの `frontend/src/services/pc-api.ts` に `getPCById` および `updatePCStatus` を追加し、既存の `requestWithRetry` 経由で呼び出すことで ECS コールドスタート時の自動待機・再試行（`ECSLoadingState` 連携）をそのまま継承する。
- **Rationale**:
  - Lambda プロキシ（`/api/{path:path}`）はすべての `/api/*` パスを ECS へ転送する設計のため、Lambda や CDK の変更は不要。
  - 既存の `GET /api/pcs` と同様に一般ユーザー・管理者いずれも PC 詳細を閲覧できる設計と整合する。
- **Alternatives considered**:
  - **フロントエンドで `GET /api/pcs` 全件取得してクライアント側で絞り込む案**: URL 直アクセス時に不要な全件スキャンとデータ転送が発生し、存在しない `pcId` の 404 判定も曖昧になるため却下。

---

## 4. PC 詳細画面（`frontend/src/app/pcs/[pcId]/page.tsx`）の UI・導線設計

- **Decision**:
  - `frontend/src/app/pcs/[pcId]/page.tsx` を Client Component として新規作成し、既存の `frontend/src/app/pcs/page.tsx` や `frontend/src/app/pcs/[pcId]/return/page.tsx` と同じ UI コンポーネント（`Button`, `Card`, `ECSLoadingState`, `getStatusDisplay`, `getStatusColor`）を再利用する。
  - 返却手続きボタン（`/pcs/${pc.pcId}/return` へのリンク）は、`pc.status === 'InUse'` かつ（`session.user.id === pc.ownerId` または `session.user.role === 'Admin'`）の条件を満たす場合のみ表示する。
  - ステータス更新フォームは `session.user.role === 'Admin'` の場合のみ表示し、既存の `PATCH /api/pcs/{pc_id}/status` を呼び出して更新後のステータス・更新日時を即時反映する（バックエンド側でも `get_admin_principal` による権限制御が既に実装済み）。
  - `404` 応答時は専用 Not Found UI（「指定された PC は見つかりませんでした」＋「PC一覧に戻る」ボタン）を表示し、それ以外の通信・タイムアウトエラー時はエラーメッセージと「再試行」ボタンを表示する。
- **Rationale**:
  - 既存の返却ページ・ステータス更新 API・ECS 起動待機 UI をそのまま活かせるため、最小限の変更で高い一貫性と保守性を実現できる。
- **Alternatives considered**:
  - **Next.js Server Component で詳細データを直接取得する案**: 本システムはコールドスタート時の 503 自動リトライ＋カウントダウン表示（`ECSLoadingState`）がクライアント側で実装されているため、既存の `/pcs` 画面と同じ Client Component 構成が必須。
