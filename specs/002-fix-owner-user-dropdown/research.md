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

## Decision: 既存の認証主体転送契約を補完する

- **確認結果**: NextAuth は Azure AD の `oid` を JWT の `sub` に設定し、session に access token と Users から取得した role を保持する。ブラウザの既存 API クライアントは Authorization を付与していなかった。Next.js rewrite はリクエストを Lambda へ転送し、Lambda プロキシは Host を除くヘッダーと ECS の status/body を変更せず転送する。ECS の既存コードは `Authorization: Bearer <userId>` の資格情報を userId として Users に照合する簡易契約であり、JWT 検証は未実装である。
- **Decision**: 今回はアーキテクチャ境界を変更せず、NextAuth の `sub` を session の user ID としてクライアントへ公開し、PC/Users API 呼び出しで `Authorization: Bearer <userId>` を送る。ECS は受信値の role を信頼せず、毎回 Users の存在と role を再確認して主体を解決する。ownerId は別途 Users に再照合する。
- **Scope**: Azure access token/JWT の完全検証への置換は、既存認証基盤全体に影響するため本Issueの対象外とする。現行の簡易トークン契約を文書化し、受信した ownerId やクライアント側 role だけで認可しない。

## Decision: 利用可能性は Users の登録時存在で判定する

- **確認結果**: Users を削除する実装済み API や運用コードは存在せず、Lambda の UserRepository に未実装の削除 stub があるだけである。一次モデルにも `isActive` 等の属性はない。
- **Decision**: 「利用可能なユーザー」は PC 登録時点で Users に存在する Owner Candidate とする。一覧取得後に削除された場合も登録直前の存在確認で拒否する。
- **用語**: `docs/ubiquitous-language.md` に Owner、Owner ID、Owner Candidate、Available User が定義済みであることを確認した。