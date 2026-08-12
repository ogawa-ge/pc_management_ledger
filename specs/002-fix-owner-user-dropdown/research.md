# Phase 0: Research

## Decision: `001-pc-management` と同じアーキテクチャを維持する

- **Rationale**: 対象は既存のPC登録画面と `/api/users`・`/api/pcs` の不具合修正であり、Next.js、FastAPI、Lambda/ECS、DynamoDBの境界を変える必要がない。ECS起動時の既存loading方針とコスト最適化を守れる。
- **Alternatives considered**: ユーザー一覧専用の新規Lambda/API、Users用の新規テーブル。いずれも重複経路とスキーマ推測を生み、今回の限定修正の範囲を超えるため採用しない。

## Decision: 既存 `GET /api/users` を候補一覧の取得契約として利用する

- **Rationale**: `frontend/src/services/pc-api.ts` に既に `/api/users` クライアントがあり、ECS `main.py` にもUsers scanのエンドポイントがある。Userの一次モデルは `userId/name/email/role` であり、これを表示情報と一意IDに使う。
- **Alternatives considered**: PC APIレスポンスにユーザー一覧を埋め込む方式。PC一覧と候補一覧の責務が混ざり、既存契約を不必要に変更するため採用しない。

## Decision: 取得状態と登録可否はUIとAPIの両方で制御する

- **Rationale**: UIでは取得中・取得失敗・0件を区別して誤操作を防ぎ、サーバーではUIを迂回した不正なownerIdを防ぐ必要がある。ownerIdだけを信頼せず、既存Admin/Userの認可方針を踏襲する。
- **Alternatives considered**: UIのrequired属性だけに依存する方式。API直接呼び出しや一覧取得後のユーザー無効化を防げないため不採用。

## Decision: 既存のUser/PC属性以外は追加しない

- **Rationale**: Constitutionのスキーマ推測禁止と、`001-pc-management/data-model.md` の一次定義に従う。仕様にある「利用できなくなったユーザー」は、既存の認証/Users運用で確認できる範囲をまず利用する。
- **Alternatives considered**: `isActive` 等の新規属性を追加する方式。一次資料に定義がなく、実装前に利用可能性の値と移行を決める必要があるため未決とする。

## Decision: UIは既存PC登録フォームの見た目・操作構造を維持する

- **Rationale**: ユーザー指定は `001-pc-management` と同等のPC向けUI方針であり、修正は状態メッセージ・選択制御に限定する。既存のターミナルコマンド、スペック入力、成功後遷移を変更しない。
- **Alternatives considered**: 新しいモーダルや検索コンポーネントの導入。今回のユーザー規模と不具合原因に対して過剰で、既存UI方針から逸脱するため不採用。

## Resolved technical unknowns

- Frontend依存: 既存のNext.js/React/next-authのみを利用し、新規UIライブラリは追加しない。
- Backend依存: 既存FastAPI/boto3/Pydanticを利用し、新規サービス基盤は追加しない。
- Storage: 既存 `Users` と `PCs` のみ。新規テーブル・属性は未定義として扱う。
- Test: Backendは既存pytest、Frontendは既存buildと手動確認を基線とする。自動UIテスト導入は未決事項として計画に残す。