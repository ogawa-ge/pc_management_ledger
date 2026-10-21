# Phase 0: Research — ログイン方式のGoogle Workspaceへの変更

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 現状調査（As-Is）

| 項目 | 現状 | 参照 |
|---|---|---|
| 認証ライブラリ | NextAuth v4（`next-auth@^4.24`）の `AzureADProvider` | `frontend/src/app/api/auth/[...nextauth]/route.ts` |
| ユーザーID | Azure AD の `oid` を `token.sub` に入れ、`session.user.id` として使用 | 同上 `jwt` コールバック |
| 権限取得 | `session` コールバックで Lambda の `POST /api/auth/user-permissions` を呼び、`role` を取得 | `frontend/src/lib/auth-service.ts`、`backend/lambda/src/main.py` |
| 初回ログイン時のユーザー登録 | **処理が存在しない**。Users に未登録のユーザーは `role` が無いため `User` 扱いになるが、Users には登録されない（オーナー候補に出ない） | `backend/lambda/src/services/auth_service.py` |
| 未ログイン時のリダイレクト | `middleware.ts` が NextAuth の JWT（`NEXTAUTH_SECRET`）の有無で判定 | `frontend/src/middleware.ts` |
| バックエンドへの認可 | フロントエンドが `Authorization: Bearer <userId>` を送り、ECS が Users から role を引く（トークン検証なし） | `backend/ecs/src/main.py` `get_request_principal`、`frontend/src/services/pc-api.ts` |
| ブラウザ→API の経路 | Next.js の `rewrites` で同一オリジンの `/api/pcs/*` などを API Gateway に転送 | `frontend/next.config.js` |
| Lambda の Azure 用シークレット | CDK で `AzureAdSecrets` を参照し `AZURE_AD_SECRET_NAME` を設定しているが、**Lambda のコードからは使われていない** | `infrastructure/stacks/lambda_stack.py` |
| フロントエンドのテスト基盤 | なし（`package.json` にテストランナー無し） | `frontend/package.json` |
| バックエンドのテスト基盤 | pytest（`backend/tests/`、`backend/ecs/tests/`） | — |

---

## R-1. 認証プロバイダ

- **Decision**: NextAuth v4 の `GoogleProvider`（`next-auth/providers/google`）に置き換える。
- **Rationale**: 既存の NextAuth の構成（JWT セッション、`middleware.ts`、`session` コールバック）をそのまま使えるため、変更箇所が最小になる（Constitution Layer 4「変更の最小化」）。Google の OpenID Connect で `sub`・`email`・`email_verified`・`hd`・`name` が取得できる。
- **Alternatives considered**:
  - Amazon Cognito + Google IdP: ユーザープール等の新規リソースが増え、コストと構成が重くなる。
  - Auth.js v5 への移行: 本 Issue の範囲を超える。

## R-2. ユーザーID（`userId`）に使う値

- **Decision**: Google の `sub` クレーム（Google アカウントごとに不変の一意 ID）を `userId` とする。メールアドレスと氏名は属性として保持する。
- **Rationale**: `sub` は変わらず、再利用もされない。メールアドレスは改名などで変わりうるため、主キーには向かない。`GoogleProvider` では `token.sub` に既定で `sub` が入るため、Azure 用の `oid` 付け替え処理を削除するだけで済む。
- **Alternatives considered**:
  - メールアドレスを `userId` にする: 読みやすいが、アドレス変更時に PC の `ownerId` などの参照がすべて切れる。

## R-3. ドメイン判定の場所と方法

- **Decision**: NextAuth の `signIn` コールバック（Amplify 上のサーバー側で実行）で判定する。次の **すべて** を満たす場合のみ許可する。
  1. `profile.email_verified === true`
  2. メールアドレスを最後の `@` で分割したドメイン部分が、`ALLOWED_EMAIL_DOMAIN` と完全一致する（小文字化して比較）
  3. `profile.hd`（Google Workspace のドメイン）が `ALLOWED_EMAIL_DOMAIN` と完全一致する（小文字化して比較）

  あわせて `GoogleProvider` の `authorization.params.hd` に許可ドメインを指定する。これはアカウント選択画面の絞り込み（使い勝手）のためで、判定には使わない。
- **Rationale**: FR-002・FR-004（サーバー側で必ず判定）を満たす。`hd` は Google が付与する値で、個人 Gmail には付かない。メールのドメインとの二重チェックで、サブドメイン・類似ドメインを確実に弾ける（Edge Cases）。`hd` パラメータはクライアント側で書き換え可能なため、判定に使うのは不可。
- **Alternatives considered**:
  - `hd` パラメータのみ: 書き換え可能で FR-004 違反。
  - `endsWith('genuine-pt.jp')` での判定: `@xgenuine-pt.jp` や `@sub.genuine-pt.jp` を通してしまう。

## R-4. ログイン時のユーザー登録（FR-006）

- **Decision**: Lambda に `POST /api/auth/sync-user` を新設する。`signIn` コールバックでドメイン判定に通った後に呼び出し、Users に upsert する。
  - 未登録の場合: `role = User` で新規作成する
  - 登録済みの場合: `name`・`email`・`updatedAt` だけを更新し、`role` は変えない

  DynamoDB の `update_item` で `role = if_not_exists(role, :user)`・`createdAt = if_not_exists(createdAt, :now)` とし、1 回の呼び出しで冪等にする。
- **Rationale**: 現状は登録処理が無く、FR-006 を満たすには新設が必要。Lambda で処理すれば ECS は起動しない（FR-010、Constitution「Hybrid Responsibility」）。
- **Failure handling**: Lambda の呼び出しに失敗した場合はログインを拒否し、ログイン画面で「しばらくしてから再度お試しください」を表示する（FR-008）。未登録のままログインさせると、オーナー候補に出ないなどの不整合が起きるため。
- **Alternatives considered**:
  - 既存の `POST /api/auth/user-permissions` に登録処理を混ぜる: このエンドポイントはリクエストのたびに呼ばれ（`session` コールバック）、取得専用であるべきため不採用。
  - Next.js から DynamoDB に直接書き込む: Amplify に AWS 認証情報が必要になり、構成が増える。

## R-5. Lambda 側でのドメイン再チェック（多層防御）

- **Decision**: `POST /api/auth/sync-user` でも、`email` のドメインが Lambda の環境変数 `ALLOWED_EMAIL_DOMAIN` と完全一致しない場合は 403 を返して登録しない。
- **Rationale**: このエンドポイントは API Gateway から直接呼べるため、ここで弾かないと任意のメールアドレスのユーザーを Users に登録できてしまう。判定は小さな関数で済む。
- **Alternatives considered**: フロントエンドのみで判定する → API を直接呼ばれた場合に防げない。

## R-6. 拒否時のログ記録（FR-012）

- **Decision**: `signIn` コールバックで拒否したときに、`console.warn` で構造化ログ（JSON 1 行: `event`・`reason`・`email`・`timestamp`）を出力する。Amplify Hosting（SSR）のコンピューティングログとして CloudWatch Logs に出る。Lambda 側（R-5）で拒否した場合も同じ形式で出力する。
- **Rationale**: 新しいリソースが要らない（Cost-Awareness）。画面での閲覧機能は不要（FR-012）。
- **Note**: Amplify のコンピューティングログを CloudWatch に出すには、Amplify アプリにサービスロールの設定が必要な場合がある。quickstart.md で確認手順を示す。

## R-7. ログイン失敗時の画面表示（FR-008、Edge Cases）

- **Decision**: NextAuth の `pages` に `signIn: '/login'` と `error: '/login'` を指定し、ログイン画面でクエリ `?error=` の値に応じて日本語メッセージを出し分ける。

  | `error` の値 | 発生条件 | 表示 |
  |---|---|---|
  | `DomainNotAllowed` | `signIn` コールバックがドメイン判定で拒否（`/login?error=DomainNotAllowed` を返す） | 会社のGoogleアカウントでログインしてください |
  | `RegistrationFailed` | `sync-user` の呼び出しに失敗 | しばらくしてから再度お試しください |
  | ユーザーが同意画面・アカウント選択でキャンセルした場合の値 | Google 側でキャンセル | 表示しない（通常のログイン画面） |
  | 上記以外（`OAuthSignin`、`OAuthCallback`、`Callback` など） | Google 側の障害など | しばらくしてから再度お試しください |

  メッセージは固定文言とし、ドメイン名は含めない（FR-003）。許可ドメインをブラウザ側に渡すための `NEXT_PUBLIC_` 付き環境変数は作らない。
- **Rationale**: 内部のエラー詳細を出さない（FR-008）。キャンセル時はエラー扱いしない（Edge Cases）。
- **Note**: キャンセル時に NextAuth v4 が付ける `error` の値は、実装時に実機で確認して確定する（tasks で確認タスクを設ける）。

## R-8. 切り替え前のセッションの無効化（Edge Cases）

- **Decision**: 切り替え時に `NEXTAUTH_SECRET` を新しい値に変更する。
- **Rationale**: 旧 Microsoft ログインで発行された JWT が復号できなくなり、`middleware.ts` が未ログインと判定してログイン画面に戻す。コード変更は不要。

## R-9. 既存データの扱い（FR-006a）

- **Decision**: DynamoDB のテーブル定義（テーブル名・パーティションキー）は変更しない。切り替え時に `Users`・`PCs`・`ReturnRecords`・`PCUsageHistories` の全アイテムを削除する。手順は quickstart.md に AWS CLI の手順として記載し、移行用のプログラムは作らない。`SystemActivity`（ECS の自動停止用）はユーザーデータではないため対象外。
- **Rationale**: DynamoDB はスキーマレスで、`userId` の中身が `oid` から Google `sub` に変わってもテーブル定義の変更は不要。「必要に応じて作り直す」（FR-006a）のうち、今回は作り直しが不要と判断した。開発途中で本番データが無いため、全削除で問題ない。
- **Alternatives considered**: CDK でテーブルを作り直す → テーブル名が同じため削除・再作成の手順が必要になり、手間に見合わない。

## R-10. 不要になる Azure AD 関連の設定

- **Decision**:
  - `frontend`: `AzureADProvider` の import と `oid` の付け替え処理を削除する。`session.accessToken` は利用箇所が無く、Google のアクセストークンをブラウザに渡す理由がないため削除する。
  - `infrastructure/stacks/lambda_stack.py`: `AzureAdSecrets` の参照・`grant_read`・環境変数 `AZURE_AD_SECRET_NAME` を削除し、環境変数 `ALLOWED_EMAIL_DOMAIN` を追加する。値は CDK のデプロイ時に環境変数から読み込む（ソースコードにドメインを書かない、FR-003）。未設定の場合はデプロイを続行して警告を出す。他メンバーの CDK デプロイを妨げないためで、未設定のままでも Lambda 側がログインを拒否するため安全側に倒れる。
  - Secrets Manager 上の `AzureAdSecrets`: CDK の参照削除をデプロイした後に、手動で削除してよい（本 Issue のタスクには含めない）。
- **Rationale**: SC-003（Microsoft の経路が残っていない）。

## R-11. 範囲外とするもの（Constitution Layer 4「Strict Scope Boundaries」）

| 項目 | 判断 | 理由 |
|---|---|---|
| バックエンドの CORS 設定（新 Amplify の URL 追加） | 本 Issue では扱わない | ブラウザからの API 呼び出しは Next.js の `rewrites` 経由（同一オリジン）で、`sync-user` はサーバー間通信のため、ログイン機能には影響しない。新 Amplify への移行作業として別途扱う |
| `Authorization: Bearer <userId>` の簡易認可（トークン検証なし） | 本 Issue では扱わない | 既存の課題で、ログイン方式の変更とは独立。Google 移行後も同じ方式で動作する。社内用の管理アプリで、現時点ではそこまでの厳密さを求めないため、現状のままとする（2026-10-19 判断） |
| `/api/auth/me`・`/api/auth/validate`（固定シークレットの JWT 検証） | 変更しない | 現在のログインの流れでは使われていない |
| フロントエンドのテスト基盤の導入 | 導入しない | 判定ロジックは Lambda 側（pytest）で自動テストし、フロントエンドは quickstart.md の手動シナリオで確認する |
