---

description: "Task list for ログイン方式のGoogle Workspaceへの変更 (Issue #19)"
---

# Tasks: ログイン方式のGoogle Workspaceへの変更

**Input**: Design documents from `specs/004-google-workspace-login/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Lambda の `sync-user` とドメイン判定は pytest で自動テストする（plan.md「Testing」、quickstart.md「3. 自動テスト」）。フロントエンドはテスト基盤がないため、quickstart.md の手動シナリオで確認する（research.md R-11）。

**Organization**: spec.md の User Story ごとにまとめる。US1・US2 はどちらも P1 で、本番に出すには両方が必要。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並行して進められる（別ファイルで、未完了タスクへの依存がない）
- **[Story]**: 対応する User Story（US1 / US2）

## Path Conventions

- フロントエンド: `frontend/src/`
- Lambda: `backend/lambda/src/`（import は `from src.…` 形式）
- テスト: `backend/tests/`
- インフラ: `infrastructure/stacks/`

---

## Phase 1: Setup

**Purpose**: 用語の同期とローカル環境の準備

- [X] T001 `docs/ubiquitous-language.md` の「1. ユーザー・権限関連」の **User** 行の定義を「システムを利用する人物。Google Workspace アカウント（`@genuine-pt.jp`）でログインする。」に変更し、備考に「`userId` は Google の `sub`」を追記する（FR-011、Constitution L3 Ubiquitous Language。実装前に行う）
- [ ] T002 [P] 開発者のローカル環境の `frontend/.env.local`（git 管理外）から `AZURE_AD_*` を削除し、`GOOGLE_CLIENT_ID`・`GOOGLE_CLIENT_SECRET`・`ALLOWED_EMAIL_DOMAIN=genuine-pt.jp` を追加する（environment-setup.md「3」。リポジトリにはコミットしない）

---

## Phase 2: Foundational（全 User Story の前提）

**Purpose**: ドメイン判定の共通関数と、Lambda の環境変数の準備

**⚠️ CRITICAL**: このフェーズが終わるまで User Story の作業は始めない

- [ ] T003 [P] `frontend/src/lib/email-domain.ts` を新規作成し、ドメイン判定の純粋関数 `isAllowedGoogleAccount({ email, emailVerified, hostedDomain }, allowedDomain): boolean` を実装する。判定は research.md R-3 の 3 条件（`emailVerified === true`、メールを最後の `@` で分割したドメインが `allowedDomain` と完全一致、`hostedDomain` が `allowedDomain` と完全一致。いずれも小文字化して比較）をすべて満たす場合のみ `true`。`allowedDomain` が空なら常に `false`。あわせて拒否理由を返す `getRejectionReason(...)`（`'email_not_verified' | 'domain_not_allowed' | null`）も実装する
- [ ] T004 [P] `backend/lambda/src/services/auth_service.py` に `is_allowed_email_domain(email: str, allowed_domain: str) -> bool` を追加する。メールを最後の `@` で分割し、ドメイン部分を小文字化して `allowed_domain.lower()` と完全一致する場合のみ `True`。`@` を含まない・ドメインが空・`allowed_domain` が空の場合は `False`（research.md R-5、data-model.md「バリデーションルール」）
- [ ] T005 [P] `infrastructure/stacks/lambda_stack.py` を変更する。`AzureAdSecrets` の `from_secret_name_v2` 参照・`azure_ad_secrets.grant_read(api_lambda)`・環境変数 `AZURE_AD_SECRET_NAME` を削除し、`ApiLambda` の `environment` に `ALLOWED_EMAIL_DOMAIN` を追加する。値はデプロイ時の環境変数 `os.environ.get("ALLOWED_EMAIL_DOMAIN")` から読み、未設定・空の場合は警告を出力し、空文字を設定する（synth は失敗させない。他メンバーの CDK デプロイを妨げないため）。空の場合、Lambda の `sync-user` は 500 を返す（T015）（research.md R-10、FR-003）。未使用になる `aws_secretsmanager` の import は、他で使っていなければ削除する

**Checkpoint**: 判定関数と Lambda の設定がそろい、User Story の実装を始められる

---

## Phase 3: User Story 1 - Google Workspaceアカウントでのログイン (Priority: P1) 🎯 MVP

**Goal**: `@genuine-pt.jp` のアカウントで Google ログインでき、初回ログイン時に Users に `role = User` で登録され、権限に応じた PC 一覧画面が表示される

**Independent Test**: quickstart.md「4. 手動での確認シナリオ」の 1〜5・9 と、pytest の新規・更新ケースが通ること

### Tests for User Story 1

> 先に書き、実装前に失敗することを確認する

- [ ] T006 [US1] `backend/tests/test_sync_user.py` を新規作成し、`sync_user` の正常系テストを書く。`backend/lambda` を `sys.path` に追加して `from src.services.auth_service import ...` で読み込み、DynamoDB テーブルは `unittest.mock` でモックする。ケース: (1) 未登録ユーザー → `update_item` が `role = if_not_exists(role, :user)`・`createdAt = if_not_exists(createdAt, :now)` を含む式で 1 回呼ばれ、戻り値が `role = User`・`created = True`、(2) 登録済みで `role = Admin` → 戻り値が `role = Admin`・`created = False`、(3) `email` は小文字化して保存される、(4) `email` が空 → `ValueError`（quickstart.md「3」の表）

### Implementation for User Story 1

- [ ] T007 [US1] `backend/lambda/src/services/auth_service.py` に `sync_user(user_id: str, email: str, name: Optional[str]) -> dict` を追加する。`dynamodb.Table('Users').update_item` を 1 回だけ呼び、`SET email = :email, updatedAt = :now, #role = if_not_exists(#role, :user), createdAt = if_not_exists(createdAt, :now)`（`name` があれば `#name = :name` も）とし、`ReturnValues="ALL_NEW"` の結果から `{"userId", "role", "created"}` を返す。`created` は返却された `createdAt` と今回の `:now` が一致するかで判定する。`user_id` または `email` が空なら `ValueError`（data-model.md「ライフサイクル」、contracts/api.md）
- [ ] T008 [US1] `backend/lambda/src/main.py` に `POST /api/auth/sync-user` を追加する。リクエストは pydantic モデル（`userId: str`、`email: str`、`name: Optional[str] = None`）。`ValueError` は 400 `{"detail": "userId and email are required"}`、その他の例外は 500 `{"detail": "Failed to sync user"}` を返す。**`proxy_to_ecs` のキャッチオールルートより前に定義する**（ECS を起動しないため。FR-010）（contracts/api.md）
- [ ] T009 [P] [US1] `frontend/src/lib/auth-service.ts` に `syncUser({ userId, email, name }): Promise<{ userId: string; role: 'Admin' | 'User'; created: boolean }>` を追加する。`${process.env.NEXT_PUBLIC_API_URL}/api/auth/sync-user` に POST し、レスポンスが 2xx 以外なら例外を投げる（呼び出し側でログインを拒否するため、既存の `get_user_auth_info` のように握りつぶさない）
- [ ] T010 [US1] `frontend/src/app/api/auth/[...nextauth]/route.ts` を変更する。(1) `AzureADProvider` を `GoogleProvider`（`next-auth/providers/google`）に置き換え、`clientId: process.env.GOOGLE_CLIENT_ID!`、`clientSecret: process.env.GOOGLE_CLIENT_SECRET!`、`authorization: { params: { hd: process.env.ALLOWED_EMAIL_DOMAIN } }` を指定する。(2) `pages: { signIn: '/login', error: '/login' }` を追加する。(3) `signIn` コールバックを追加し、`syncUser({ userId: profile.sub, email: profile.email, name: profile.name })` を呼ぶ。失敗したら `'/login?error=RegistrationFailed'` を返す。(4) `jwt` コールバックから `oid` の付け替え処理と `accessToken` の保存を削除する。(5) `session` コールバックから `session.accessToken` の設定を削除する（research.md R-1・R-2・R-4・R-10）
- [ ] T011 [P] [US1] `frontend/src/types/next-auth.d.ts` から `Session.accessToken` を削除する（contracts/api.md「Frontend (NextAuth)」）
- [ ] T012 [US1] `frontend/src/app/login/page.tsx` を変更する。説明文を「会社のGoogleアカウントでログインしてください」、ボタンを「Googleアカウントでログイン」にし、`signIn('google', { callbackUrl: '/pcs' })` を呼ぶ。`useSearchParams` で `error` を読み、`RegistrationFailed` とそれ以外の未知の値には「ログインに失敗しました。しばらくしてから再度お試しください」を表示する（`useSearchParams` を使うため `Suspense` で囲む）。Microsoft の表記はすべて削除する（FR-005、FR-008、contracts/api.md「ログイン画面のエラー表示」）
- [ ] T013 [US1] ローカルで Google のアカウント選択画面をキャンセルし、ログイン画面に戻ったときの `?error=` の値を確認する。その値を `frontend/src/app/login/page.tsx` で「表示しない」扱いにし、確認した値を `specs/004-google-workspace-login/contracts/api.md` の「キャンセル時の値（実装時に確定）」に記入する（research.md R-7、spec Edge Cases）

**Checkpoint**: `@genuine-pt.jp` でログインでき、Users に登録される（この時点ではドメイン判定は Google の `hd` による絞り込みのみで、本番には出さない）

---

## Phase 4: User Story 2 - `@genuine-pt.jp` 以外のアカウントの拒否 (Priority: P1)

**Goal**: `@genuine-pt.jp` 以外のアカウントはフロントエンドと Lambda の両方で拒否され、Users に登録されず、拒否ログが残る

**Independent Test**: quickstart.md「4」のシナリオ 6〜8 と、pytest の拒否ケースが通ること

### Tests for User Story 2

- [ ] T014 [US2] `backend/tests/test_sync_user.py` に拒否系のテストを追加する。`is_allowed_email_domain` について `@gmail.com`・`@sub.genuine-pt.jp`・`@genuine-pt.jp.example.com`・`@xgenuine-pt.jp`・`@` なし → `False`、`@GENUINE-PT.JP` → `True`、`allowed_domain` が空 → `False`。`POST /api/auth/sync-user` のハンドラ関数について、許可外ドメインで 403 を返し `update_item` が呼ばれないこと、`ALLOWED_EMAIL_DOMAIN` 未設定で 500 を返すこと（quickstart.md「3」の表）

### Implementation for User Story 2

- [ ] T015 [US2] `backend/lambda/src/main.py` の `POST /api/auth/sync-user` で、`sync_user` を呼ぶ前に `os.environ.get("ALLOWED_EMAIL_DOMAIN")` を確認する。未設定・空なら 500 `{"detail": "Failed to sync user"}`。`is_allowed_email_domain` が `False` なら、`print(json.dumps({"event": "login_rejected", "reason": "domain_not_allowed", "email": ..., "timestamp": <UTC ISO 8601>, "source": "lambda"}))` で拒否ログを出し、403 `{"detail": "Email domain is not allowed"}` を返す（research.md R-5・R-6、contracts/api.md「拒否ログの形式」、FR-012）
- [ ] T016 [US2] `frontend/src/app/api/auth/[...nextauth]/route.ts` の `signIn` コールバックの先頭（`syncUser` より前）で、`isAllowedGoogleAccount({ email: profile.email, emailVerified: profile.email_verified, hostedDomain: profile.hd }, process.env.ALLOWED_EMAIL_DOMAIN ?? '')` を判定する。`false` の場合は `getRejectionReason` の値を使って `console.warn(JSON.stringify({ event: 'login_rejected', reason, email, timestamp, source: 'frontend' }))` を出力し、`'/login?error=DomainNotAllowed'` を返す（`syncUser` は呼ばない）（research.md R-3・R-6、FR-002・FR-004・FR-012、US2 シナリオ 3）
- [ ] T017 [US2] `frontend/src/app/login/page.tsx` で、`error=DomainNotAllowed` のときに「会社のGoogleアカウントでログインしてください」を表示する（US2 シナリオ 1・2、contracts/api.md）

**Checkpoint**: US1・US2 がそろい、本番に出せる状態

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Microsoft の経路が残っていないことの確認と、切り替え作業

- [ ] T018 `frontend/`・`backend/lambda/`・`infrastructure/` を `azure|AzureAD|azure-ad|AZURE_AD` で検索し、ログイン関連の参照が残っていないことを確認する（SC-003）。`backend/tests/test_e2e.py` の Microsoft アカウントでのログインのテスト（`test_login_with_valid_microsoft_account` など）は、Google アカウントでのログインの内容に書き換える（`microsoft_account` → `google_account` など。テスト名・docstring・コメントも含む）。ただし、同等の Google アカウントでのログインのテストが別に存在する場合は、書き換えずに Microsoft のテストを削除する。`backend/ecs/tests/test-gemini-accuracy.py` の参照は、ログインと無関係（PC のスペックなど）であることを確認したうえで変更しない（Constitution L4-2）
- [ ] T019 `cd backend && pytest tests -k sync_user` を実行し、すべて成功することを確認する
- [ ] T020 `cd frontend && npm run build` を実行し、型エラー・ビルドエラーがないことを確認する
- [ ] T021 quickstart.md「4. 手動での確認シナリオ」の 1〜9 をローカルで実施し、結果を確認する
- [ ] T022 quickstart.md「5. 本番（新 Amplify）への切り替え手順」に沿って切り替える（`NEXTAUTH_SECRET` の変更、CDK デプロイ、「6. 既存データの削除」、Amplify 再デプロイ、本番 URL でシナリオ 1〜9、「7. 最初の管理者の設定」）。Amplify の環境変数が実行時に読めない場合は、environment-setup.md「2」の amplify.yml の対応を行う
- [ ] T023 CDK デプロイ後、Secrets Manager 上の `AzureAdSecrets` を手動で削除する（environment-setup.md「5」）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1（Setup）**: 依存なし。T001 は Constitution により実装より先に行う
- **Phase 2（Foundational）**: Phase 1 の後。US1・US2 の両方をブロックする
- **Phase 3（US1）**: Phase 2 の後
- **Phase 4（US2）**: Phase 2 の後。ただし `main.py`・`route.ts`・`login/page.tsx` を US1 と共有するため、**US1 の完了後に着手する**
- **Phase 5（Polish）**: US1・US2 の完了後

### User Story Dependencies

- **US1**: Phase 2 の T004（`sync_user` と同じファイル）、T005（Lambda の環境変数）に依存
- **US2**: T003（`isAllowedGoogleAccount`）、T004（`is_allowed_email_domain`）と、US1 の T008・T010・T012（同じファイルへの追記）に依存

### Within Each User Story

- テスト（T006・T014）を先に書き、失敗を確認してから実装する
- Lambda（サービス → エンドポイント）→ フロントエンド（API 呼び出し → NextAuth → 画面）の順

### Parallel Opportunities

- Phase 1: T002 は T001 と並行可
- Phase 2: T003・T004・T005 はすべて別ファイルで並行可
- Phase 3: T009（`auth-service.ts`）・T011（`next-auth.d.ts`）は Lambda 側の T006〜T008 と並行可

---

## Parallel Example: Phase 2 / User Story 1

```bash
# Phase 2: 3 つとも別ファイル
Task: "T003 frontend/src/lib/email-domain.ts にドメイン判定関数を作成"
Task: "T004 backend/lambda/src/services/auth_service.py に is_allowed_email_domain を追加"
Task: "T005 infrastructure/stacks/lambda_stack.py の AzureAdSecrets を削除し ALLOWED_EMAIL_DOMAIN を追加"

# User Story 1: Lambda 側とフロントエンドの型・API 呼び出しを並行
Task: "T006→T007→T008 Lambda の sync-user（テスト → サービス → エンドポイント）"
Task: "T009 frontend/src/lib/auth-service.ts に syncUser を追加"
Task: "T011 frontend/src/types/next-auth.d.ts から accessToken を削除"
```

---

## Implementation Strategy

### MVP（US1 + US2）

US1 だけでは `@genuine-pt.jp` 以外を確実に拒否できない（Google の `hd` による絞り込みのみ）ため、**本番に出す最小単位は US1 + US2** とする。

1. Phase 1・2 を完了する
2. Phase 3（US1）を完了し、`@genuine-pt.jp` でログインと登録ができることをローカルで確認する
3. Phase 4（US2）を完了し、Gmail などが拒否されることをローカルで確認する
4. Phase 5 で最終確認と本番切り替えを行う

### 外部の準備（実装と並行）

- Google Workspace 管理者に OAuth クライアントの作成を依頼する（environment-setup.md「1」）。クライアント ID とシークレットがないと T013・T021 以降を実施できない

---

## Notes

- [P] = 別ファイルで依存なし
- 範囲外（research.md R-11）: CORS 設定、`Bearer <userId>` の簡易認可、`/api/auth/me`・`/api/auth/validate`
- タスクまたは論理的なまとまりごとにコミットする
- 各 Checkpoint で動作を確認してから次に進む
