---

description: "PC新規登録時のオーナーユーザー選択修正の実装タスク"
---

# Tasks: PC新規登録時のオーナーユーザー選択修正

**Input**: `specs/002-fix-owner-user-dropdown/` の設計文書
**Prerequisites**: `plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/api.md`、`quickstart.md`

**Tests**: 仕様と計画で API の pytest 追加が明示されているため、Backend の契約・統合テストを含める。Frontend はテストランナー未導入のため、新規依存を追加せず `npm run build` と `quickstart.md` の手動確認を基線とする。

**Organization**: 各ユーザーストーリーを独立して検証可能な増分として実装する。既存の Lambda/ECS 境界、Gemini 解析、管理番号採番、PC 保存形式は変更しない。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 未完了タスクに依存せず、別ファイルで並行実行できるタスク
- **[Story]**: 対応するユーザーストーリー（US1、US2）
- すべてのタスクに具体的なファイルパスを記載する

## Phase 1: Setup（調査と検証基線）

**Purpose**: 実装前に既知の検証環境問題と、推測禁止の認証・ユーザー利用可能性契約を解消する。

- [ ] T001 `npm run build` と `pytest -q` の既知の失敗を再現し、実行ディレクトリ、失敗原因、機能実装前の基線を `specs/002-fix-owner-user-dropdown/quickstart.md` に記録する
- [ ] T002 NextAuth から Lambda プロキシを経由して ECS へ届く既存の認証主体・Authorization ヘッダーを追跡し、Admin/User 判定方式を `specs/002-fix-owner-user-dropdown/research.md` と `specs/002-fix-owner-user-dropdown/contracts/api.md` に確定する
- [ ] T003 Users の既存削除運用を一次資料とコードから確認し、新規属性を追加せず「利用可能なユーザー」を登録時点でUsersに存在するオーナー候補として `specs/002-fix-owner-user-dropdown/research.md`、`specs/002-fix-owner-user-dropdown/data-model.md`、`specs/002-fix-owner-user-dropdown/contracts/api.md`、`specs/002-fix-owner-user-dropdown/spec.md` に整合させ、Owner関連用語が `docs/ubiquitous-language.md` に定義済みであることを確認する

---

## Phase 2: Foundational（全ストーリーの共通前提）

**Purpose**: ユーザー取得、サーバー認可、型安全な API 呼び出し、API テストの共通基盤を整える。

**⚠️ CRITICAL**: このフェーズが完了するまで、ユーザーストーリーの実装を開始しない。

- [ ] T004 T002 で確定した認証契約に従ってリクエスト主体を解決し Admin/User を判定する共通依存関数を `backend/ecs/src/main.py` に実装する
- [ ] T005 [P] DynamoDB scanの `LastEvaluatedKey` がなくなるまで全ページを取得して `userId` の重複を排除し、一覧取得と存在確認をDynamoDB例外と「0件」を区別して提供するメソッドを `backend/ecs/src/models/user.py` に実装する
- [ ] T006 [P] DynamoDB、認証主体、PC 保存を実データなしで差し替えられる FastAPI TestClient 共通フィクスチャを `backend/ecs/tests/conftest.py` に実装する
- [ ] T007 [P] `User[]` の型を返し非2xxを例外として保持する `getUsers` API クライアントを `frontend/src/services/pc-api.ts` に実装し、`frontend/src/types/user.ts` の既存 User 型を利用する

**Checkpoint**: Users データアクセス、認可、API テスト、Frontend 型境界が準備でき、US1 の実装を開始できる。

---

## Phase 3: User Story 1 - 代理登録対象ユーザーの選択（Priority: P1）🎯 MVP

**Goal**: 管理者が登録済みユーザーを重複なく識別して明示選択し、選択した `userId` を所有者として PC を登録できるようにする。

**Independent Test**: Users に表示情報が揃ったユーザーと欠落したユーザーを含む2件以上を用意し、Admin で `/pcs/register` を開く。全候補が一意な代替表示を含めて表示され、選択したユーザーで登録した PC の `ownerId` が選択値と一致することを確認する。未認証・一般ユーザーによる候補一覧取得と一般ユーザーによる他ユーザー指定は拒否され、一般ユーザー本人の既存PC登録は成功することも確認する。

### Tests for User Story 1

> **NOTE: 実装前に作成し、対象ケースが失敗することを確認する。**

- [ ] T008 [P] [US1] Admin の `GET /api/users` が全ユーザーを camelCase で返し、未認証と一般ユーザーを拒否する契約テストを `backend/ecs/tests/test_owner_selection_api.py` に実装する
- [ ] T009 [P] [US1] Admin の `POST /api/pcs` が有効な `ownerId` を保存し、一般ユーザー本人の既存PC登録も成功する一方、未指定・不存在・一般ユーザーによる他ユーザー指定では保存処理を呼ばない契約テストを `backend/ecs/tests/test_owner_registration_api.py` に実装する

### Implementation for User Story 1

- [ ] T010 [US1] 共通認可と UserRepository を使用して Admin のみに候補を返し、重複した `userId` を返さない `GET /api/users` を `backend/ecs/src/main.py` に実装する
- [ ] T011 [US1] スペック解析・採番より前に実行者権限と `ownerId` の存在を再検証し、Adminには任意の存在するOwner、一般ユーザーには認証主体本人だけを許可して、検証失敗時に PC を保存しない `POST /api/pcs` 処理を `backend/ecs/src/main.py` と `backend/ecs/src/services/pc_service.py` に実装する
- [ ] T012 [US1] Admin には自動選択なしの候補 select と `name (email)`・欠落時の `userId` 代替表示を提供し、一般ユーザーには自身の表示のみを維持する画面を `frontend/src/app/pcs/register/page.tsx` に実装する
- [ ] T013 [US1] 有効な候補の明示選択時だけ送信を許可し、選択した `userId` を `registerPC` へ渡し、登録中の二重送信と成功後 `/pcs` 遷移を維持する処理を `frontend/src/app/pcs/register/page.tsx` に実装する

**Checkpoint**: US1 単独で Issue #7 の再現条件が解消され、管理者の代理登録とサーバー側 owner 検証が完結する。

---

## Phase 4: User Story 2 - ユーザー一覧取得失敗時の案内（Priority: P2）

**Goal**: ユーザー取得中、0件、取得失敗を明確に区別し、所有者を確認できない状態で PC が登録されないようにする。

**Independent Test**: `GET /api/users` を遅延、空配列、DynamoDB 例外の各状態に切り替えて `/pcs/register` を開き、それぞれ「取得中」「登録済みユーザーなし」「取得失敗」が表示されること、および select と登録操作が無効で PC 保存が行われないことを確認する。

### Tests for User Story 2

> **NOTE: 実装前に作成し、対象ケースが失敗することを確認する。**

- [ ] T014 [P] [US2] `GET /api/users` の0件は200の空配列、複数ページは全件をuserIdの重複なく返し、DynamoDB取得失敗は非2xxとなり、`POST /api/pcs` のowner再確認失敗では保存しない契約テストを `backend/ecs/tests/test_owner_list_errors_api.py` に実装する

### Implementation for User Story 2

- [ ] T015 [US2] Users 0件を正常な空配列として返し、DynamoDB 取得例外を空配列へ変換せず既存エラー形式の非2xxで返す処理を `backend/ecs/src/main.py` に実装する
- [ ] T016 [US2] ユーザー一覧の取得中・成功・0件・失敗を別状態で管理し、対応する日本語案内を表示してselectと登録ボタンを無効化し、失敗時は再試行ボタンから再取得できる処理を `frontend/src/app/pcs/register/page.tsx` に実装する
- [ ] T017 [US2] 一覧取得後に選択ユーザーが削除される競合を登録 API の4xxとして表示し、フォーム内容を保持したまま再登録を抑止する処理を `frontend/src/app/pcs/register/page.tsx` に実装する

**Checkpoint**: US2 単独の異常系確認で、取得失敗と0件を区別でき、所有者未確認のPCが作成されない。

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: 全ストーリーの回帰、ビルド、受け入れシナリオを検証して結果を残す。

- [ ] T018 [P] owner 候補 API と登録 API の追加テストを含む `pytest -q` を `backend/ecs/tests/` と `backend/tests/` に対して実行し、失敗があれば機能変更に起因するものを修正する
- [ ] T019 [P] `npm run build` を `frontend/package.json` の既存スクリプトで実行し、User 型、登録画面、API クライアントの型・コンパイルエラーを修正する
- [ ] T020 `specs/002-fix-owner-user-dropdown/quickstart.md` の複数ユーザー、複数ページ、欠落表示、取得中、0件、失敗後の再試行、一般ユーザー本人の登録と他ユーザー指定拒否、選択後削除、Notebook/Desktop、スペック入力、ターミナルボタンとコマンドコピー、Gemini解析、N-/D-採番、PC保存形式、二重送信防止、成功後遷移の全シナリオを実行する。さらに20〜30件のUsers、ECS API ready、人工遅延なしの条件で、ブラウザのNetwork記録による `GET /api/users` 開始からselect操作可能までを3回計測し、全回30秒以内である結果を同ファイルへ記録する
- [ ] T021 実装済みの status/body/camelCase を照合し、差異を解消して最終契約を `specs/002-fix-owner-user-dropdown/contracts/api.md` に反映する

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup（Phase 1）**: 依存なし。T001 は単独実行可能。T002 と T003 は調査対象が重なるため順番に確定する。
- **Foundational（Phase 2）**: Setup 完了後。全ユーザーストーリーをブロックする。
- **US1（Phase 3）**: Foundational 完了後。MVP として最初に実装する。
- **US2（Phase 4）**: Foundational と US1 の成功経路完了後。同じ API・画面へ異常状態を追加する。
- **Polish（Phase 5）**: 提供対象の US1・US2 完了後。

### User Story Dependency Graph

```text
Setup → Foundational → US1 (P1 / MVP) → US2 (P2) → Polish
```

### Within Each User Story

- API 契約テストを先に作成し、対象ケースが失敗することを確認してから実装する。
- Repository と共通認可を Endpoint より先に完成させる。
- Endpoint 契約を確定してから Frontend の状態・送信制御を実装する。
- 各ストーリーの Independent Test を通過してから次のストーリーへ進む。

### Parallel Opportunities

- Foundational 完了後、US1 の T008 と T009 は別テストファイルで並行実行できる。
- Phase 2 の T005、T006、T007 は相互に異なるファイルで、T004 と並行実行できる。
- US2 の T014 は US1 完了後、Backend 実装着手前に独立して作成できる。
- Polish の T018（Backend）と T019（Frontend）は並行実行できる。

---

## Parallel Example: User Story 1

```text
Task T008: `backend/ecs/tests/test_owner_selection_api.py` に Users 一覧・認可契約テストを作成
Task T009: `backend/ecs/tests/test_owner_registration_api.py` に owner 登録・保存抑止契約テストを作成
```

## Parallel Example: User Story 2

```text
Task T014: `backend/ecs/tests/test_owner_list_errors_api.py` に0件・取得失敗・競合テストを作成
```

---

## Implementation Strategy

### MVP First（User Story 1 Only）

1. Phase 1 で既知の検証基線、認証主体、利用可能ユーザーの定義を確定する。
2. Phase 2 の共通 Repository・認可・テスト・型境界を完成させる。
3. Phase 3 の API テストを失敗させてから US1 を実装する。
4. US1 の Independent Test で候補表示、明示選択、owner 紐付け、権限制御を検証する。
5. ここで停止すれば Issue #7 の主経路を解消した MVP としてデモできる。

### Incremental Delivery

1. **Foundation**: Setup + Foundational → 推測のない認証・データ契約とテスト基盤
2. **MVP**: US1 → 管理者が正しい所有者を選び、安全に代理登録可能
3. **Safety Increment**: US2 → 取得中・0件・失敗・競合時の誤登録防止
4. **Release Candidate**: Polish → pytest、build、全手動シナリオを検証済み

### Scope Guardrails

- 新規 DynamoDB テーブルや `isActive` 等の未定義属性を追加しない。
- 新規 Frontend テストライブラリや UI ライブラリを追加しない。
- Lambda/ECS の責任分担、ALB 非利用、ECS 自動停止方針を変更しない。
- Gemini 解析、PC 種別、管理番号採番、返却処理の既存契約を変更しない。

---

## Notes

- `[P]` は異なるファイルを変更し、未完了タスクに依存しない作業だけに付与する。
- `[US1]` と `[US2]` は `spec.md` のユーザーストーリーへ直接対応する。
- 実データ、実 API キー、実トークンをテスト・ドキュメントへ記録しない。
- 各タスクまたは論理的なまとまりごとにコミットし、各 Checkpoint で独立検証する。