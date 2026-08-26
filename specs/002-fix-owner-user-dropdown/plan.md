# Implementation Plan: PC新規登録時のオーナーユーザー選択修正

**Branch**: `002-fix-owner-user-dropdown` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-fix-owner-user-dropdown/spec.md`

## Summary

`specs/001-pc-management` と同等の Next.js + FastAPI（Lambda/ECS）+ DynamoDB 構成および PC 向け UI 方針を維持する。PC新規登録画面で、管理者が既存の `Users` テーブルのユーザーをオーナーとして選択できる既存導線を完成させる。具体的には、ユーザー一覧の取得状態（取得中・成功・0件・失敗）をUIで表現し、取得完了かつ有効なユーザー選択済みの場合だけ登録を可能にする。登録APIでは、管理者にUsersに存在する任意の `ownerId` を許可し、一般ユーザーには認証主体本人の `ownerId` だけを許可する。既存のスペック解析・管理番号採番・PC保存の挙動は変更しない。

## Technical Context

**Language/Version**: TypeScript（Next.js 16 / React 19）、Python 3.11+（FastAPI）
**Primary Dependencies**: Next.js、React、next-auth、FastAPI、boto3、Pydantic、既存の AWS Lambda/ECS 構成
**Storage**: Amazon DynamoDB（既存 `Users` / `PCs` テーブル。新規テーブルは作らない）
**Testing**: 既存 pytest、TypeScript/Next.js build、API契約確認。Frontend のテストランナーは未導入のため、今回の計画では既存 build と手動確認を基線とする
**Target Platform**: AWS Amplify/Next.js、AWS Lambda、Amazon ECS、Windows PC向けブラウザ
**Project Type**: Web Application（Frontend + Serverless/Container Hybrid Backend）
**Performance Goals**: 20〜30件のUsersを用い、ECS APIがreadyで人工的な通信遅延を設定していない受け入れ環境で、ブラウザの `GET /api/users` 開始からユーザー選択欄が操作可能になるまでを3回計測し、全回30秒以内。ECSのcold startは計測対象外とし、起動時は既存の loading 方針を維持
**Constraints**: 既存の AWS コスト最適化、ALB非利用方針、既存PC登録機能を壊さないこと。実データ・秘密鍵は成果物に含めない
**Scale/Scope**: 通常運用は20〜30名程度の既存ユーザー。DynamoDB scan が複数ページになる場合も全ページを取得し、PC新規登録画面と関連 API の限定修正とする

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] 出力・設計文書は日本語で作成する。
- [x] `001-pc-management` の `data-model.md` / `contracts/api.md` を一次ソースとし、Users/PCs の新規スキーマを推測しない。
- [x] 認証・認可は既存の Admin/User 方針に従い、ownerId の受信値だけで権限を信頼しない。
- [x] Lambda/ECS の責任分担、ECS のコスト最適化、PC向け UI 方針を維持する。
- [x] 一般のファイル名はkebab-case、PythonモジュールとPythonテストはsnake_case、フレームワーク予約名は各ツール規約に従う。
- [x] Gemini API、スペック入力、管理番号採番、返却処理は本修正の対象外として回帰させない。

**判定**: PASS（Phase 0 開始可）。Phase 1 後も新規テーブル・新規外部依存・既存責務の逸脱がないことを再確認する。

## 1) マイルストーン（フェーズ）一覧

| フェーズ | マイルストーン | 成果物 |
|---|---|---|
| M0 | 調査・契約確定 | `research.md`、既存契約との差分方針 |
| M1 | ユーザー一覧取得と認可の堅牢化 | `/api/users` の管理者制御、取得失敗のエラー契約 |
| M2 | PC登録UIの状態表現と選択制御 | 取得中/成功/0件/失敗を含む登録画面 |
| M3 | 登録直前の所有者検証と回帰確認 | owner 検証、既存登録フローの維持 |
| M4 | 受け入れ・手動検証 | pytest/build/手動チェック結果 |

## 2) 各フェーズのステップ

### M0: 調査・契約確定

#### Step 0.1: 既存実装と一次資料の照合
- **目的**: `001-pc-management` と今回の仕様、実コードの差分を確定する。
- **作業内容**: `Users` の `userId/name/email/role`、`PC.ownerId`、既存 `/api/users` と `/api/pcs` の入出力を照合。snake_case と camelCase の変換境界を確認する。
- **Done条件**: 未定義スキーマを追加せず、変更対象と対象外が `research.md` に記載されている。
- **影響ファイル案**: `specs/002-fix-owner-user-dropdown/research.md`

### M1: ユーザー一覧取得と認可の堅牢化

#### Step 1.1: Users一覧 API の契約・認可を整理
- **目的**: 管理者だけが代理登録候補を取得でき、失敗を空配列と区別する。
- **作業内容**: ECS の `GET /api/users` に既存認証/管理者判定を適用する。DynamoDB scan は `LastEvaluatedKey` がなくなるまで全ページを取得し、userIdで重複を排除する。エラー時 HTTP status/body、0件時の正常レスポンスを固定する。Lambda プロキシは既存の転送動作を維持する。
- **Done条件**: 管理者は `User[]` を取得でき、非管理者/未認証は拒否され、取得失敗は非2xxでクライアントが判別できる。
- **影響ファイル案**: `backend/ecs/src/main.py`、`backend/ecs/src/models/user.py`、`backend/tests/test_e2e.py` または `backend/ecs/tests/` のAPIテスト、`specs/002-fix-owner-user-dropdown/contracts/api.md`

#### Step 1.2: PC登録APIの owner 検証
- **目的**: UIを迂回した不正な ownerId やUsersから削除済みのユーザーへの紐付けを防ぐ。
- **作業内容**: `POST /api/pcs` の登録前に Users の存在と実行者の権限を検証する。AdminはUsersに存在する任意のオーナー候補を指定でき、一般ユーザーは認証主体本人と一致する `ownerId` だけを指定できる。「利用可能なユーザー」は登録時点でUsersに存在するオーナー候補とし、未定義の有効・無効属性は追加しない。既存のPC登録リクエスト、スペック解析、採番、保存処理は変更しない。検証失敗時は明示的な4xxとする。
- **Done条件**: Adminによる代理登録と一般ユーザー本人の登録が成功し、owner未指定・不存在・一般ユーザーによる他ユーザー指定・取得失敗ではPCが保存されない。
- **影響ファイル案**: `backend/ecs/src/main.py`、`backend/ecs/src/services/pc_service.py`、`backend/ecs/src/models/user.py`、`backend/tests/test_e2e.py`、`specs/002-fix-owner-user-dropdown/contracts/api.md`

### M2: PC登録UIの状態表現と選択制御

#### Step 2.1: User型と API クライアントの明確化
- **目的**: ユーザー表示と送信IDを型安全に扱う。
- **作業内容**: `any[]` を既存 `User` 型へ置換し、`getUsers()` の戻り値とエラー伝播を明確化。表示名欠落時は `userId` または email を代替表示に使う。レスポンス形式は既存 `/api/users` 契約に合わせる。
- **Done条件**: 各 option の value は一意な `userId`、表示は欠落時も識別可能、重複表示がない。
- **影響ファイル案**: `frontend/src/services/pc-api.ts`、`frontend/src/types/user.ts`

#### Step 2.2: 管理者向けドロップダウンの状態UI
- **目的**: 空欄表示による誤登録を防ぎ、取得状態を理解可能にする。
- **作業内容**: `page.tsx` に `loading/error/empty/ready` 状態を追加。取得中は select を無効化し「取得中」を表示、失敗はエラー文と再試行ボタンを表示して再取得できるようにし、0件は「登録済みユーザーなし」を表示する。ready 時のみ選択を許可する。`001-pc-management` と同等の PC向けフォーム構造・ラベル・既存スペック入力UIを維持する。
- **Done条件**: FR-001〜FR-007 のUI条件を満たし、owner未確認時に submit が無効または処理停止する。一般ユーザーには従来どおり自身の owner 表示のみで他ユーザー選択UIを出さない。
- **影響ファイル案**: `frontend/src/app/pcs/register/page.tsx`、必要時 `frontend/src/app/globals.css`

### M3: 登録直前の所有者検証と回帰確認

#### Step 3.1: Submitフローの整合性確保
- **目的**: 表示された選択と登録時の ownerId を一致させる。
- **作業内容**: ownerId、ユーザー取得完了状態、選択肢内の存在を submit 前に確認。登録中の二重送信を防止し、APIエラーを画面上で通知する。既存の parseSpecs → registerPC → `/pcs` 遷移を壊さない。
- **Done条件**: 選択ユーザーの ownerId が `registerPC` に渡り、エラー時に成功表示/遷移が起きず、選択肢が消えた場合は登録を停止する。
- **影響ファイル案**: `frontend/src/app/pcs/register/page.tsx`、`frontend/src/services/pc-api.ts`

#### Step 3.2: 自動検証と回帰確認
- **目的**: 既存機能を維持したまま今回の条件を検証する。
- **作業内容**: APIの成功/0件/失敗/権限不足/owner不存在/複数ページ取得、UI状態、既存PC登録・スペック解析・型チェックを確認する。20〜30件のUsersを用い、ECS APIがreadyかつ人工遅延なしの状態で、ブラウザの `GET /api/users` 開始からselectが操作可能になるまでを3回計測して全回30秒以内であることを確認する。Frontendテスト基盤は今回新設せず、既存の `npm run build`、API pytest、`quickstart.md` の手動確認を実行する。
- **Done条件**: 自動検証が成功し、対象外機能に差分がないことを確認できる。
- **影響ファイル案**: `backend/tests/test_e2e.py`、`backend/ecs/tests/`、必要時 `frontend/src/...`、`specs/002-fix-owner-user-dropdown/quickstart.md`

### M4: 受け入れ・手動検証

#### Step 4.1: 受け入れ条件に基づく実機確認
- **目的**: Issue #7 の再現条件と異常系を実際の管理者画面で確認する。
- **作業内容**: 複数ユーザー、0件、API失敗、取得中、一般ユーザー、選択後登録、無効ユーザーのシナリオを実施。
- **Done条件**: 下記チェックリストが全て合格し、結果を記録する。
- **影響ファイル案**: `specs/002-fix-owner-user-dropdown/quickstart.md`、必要時 `docs/session-notes.md`

## 3) 受け入れ条件との対応（Step → AC）

| Step | 対応するAC/要件 |
|---|---|
| Step 1.1 | AC1-1、AC2-1、AC2-2、FR-001、FR-006、FR-007、FR-008 |
| Step 1.2 | AC1-2、AC1-3、AC2-2、FR-004、FR-006、FR-007、FR-008 |
| Step 2.1 | AC1-1、FR-002、FR-009、Edge: 欠落表示・大量ユーザー |
| Step 2.2 | AC1-1、AC2-1、AC2-2、FR-001、FR-003、FR-005、FR-006、FR-007、FR-008 |
| Step 3.1 | AC1-2、AC1-3、FR-003、FR-004、FR-006、Edge: 選択後無効化 |
| Step 3.2 | SC-001〜SC-005、FR-009、既存 `001-pc-management` のPC登録回帰 |
| Step 4.1 | AC1-1〜AC1-3、AC2-1〜AC2-2、SC-001〜SC-005、全Edge Cases |

## 4) 手動の動作確認チェックリスト

- [ ] Users に2名以上ある状態で、管理者が `/pcs/register` を開くと全ユーザーが重複なく表示される。
- [ ] ユーザー名または email が欠落するデータでも、userId等の代替表示で識別できる。
- [ ] ユーザー取得中は「取得中」が表示され、select と登録操作ができない。
- [ ] ユーザー取得失敗時は明示的なエラーと再試行ボタンが表示され、空のselectだけにならず、登録できない。再試行が成功した場合は候補を選択できる。
- [ ] Users が0件の場合は「登録済みユーザーなし」が表示され、登録できない。
- [ ] 管理者が任意の1名を選ぶと、選択内容が表示され、登録ボタンが利用可能になる。
- [ ] 選択後にPC登録を完了すると、登録されたPCの `ownerId` が選択ユーザーの `userId` と一致する。
- [ ] 登録中は二重送信できず、成功時だけ既存どおりPC一覧へ遷移する。
- [ ] 登録前に選択ユーザーがUsersから削除された場合、登録は拒否されPCが作成されない。
- [ ] 一般ユーザーには他ユーザーを選ぶselectが表示されず、自身の表示だけになる。
- [ ] 20〜30件のUsers、ECS API ready、人工遅延なしの条件で、ブラウザのNetwork記録により `GET /api/users` の開始からselectが操作可能になるまでを3回計測し、全回30秒以内である。
- [ ] DynamoDB scanが複数ページになるデータで、全ユーザーがuserIdの重複なく表示される。
- [ ] Notebook/DesktopのPC種別、スペック入力、ターミナルボタンとコマンドコピー、Gemini解析、N-/D-管理番号採番、`001-pc-management` 準拠のPC保存形式、登録中の二重送信防止、成功後の `/pcs` 遷移に回帰がない。
- [ ] PC向けレイアウト・既存フォームのラベル/操作感を維持し、モバイル専用UIを追加していない。

## 5) リスク/未決事項（決めるべき順番つき）

1. **認証トークンから実行者を特定する方式**: 現在ECS側に簡易トークン処理の記述があるため、既存認証契約に沿ったAdmin判定方式を最初に確定する。
2. **Usersの利用可能性**: `001-pc-management` の一次モデルには有効/無効フィールドがないため、今回は登録時点でUsersに存在することを利用可能条件とし、新しい属性を推測して実装しない。
3. **DynamoDB scan のページング**: `LastEvaluatedKey` がなくなるまで全ページを取得し、userIdで重複を排除する。
4. **APIのJSON命名**: 既存のPydanticモデル、APIレスポンス、Frontend型で snake_case/camelCase が混在しているため、今回の境界での正規形と変換方針を固定する。
5. **Frontend自動テスト基盤（決定済み）**: 現在 `npm test` は未設定であり、Issue #7 の限定修正で新規依存を増やさないため、今回は `npm run build` + API pytest + `quickstart.md` の手動確認に限定する。Frontendテストランナーの導入は別Issueで扱う。
6. **取得失敗時の再試行UI**: エラーメッセージ、登録抑止、再試行ボタンを今回の必須範囲とする。
7. **既存検証環境の修復**: `npm run build` は既存の `.next/dev/types/validator.ts` に存在しない `src/pages/index.js` 参照があり、`pytest -q` は既存テストの import path により `No module named 'backend'` で収集失敗した。実装着手前に環境起因か既存不具合かを切り分け、修正範囲を合意する。

## Project Structure

### Documentation (this feature)

```text
specs/002-fix-owner-user-dropdown/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/api.md
└── tasks.md              # /speckit.tasks で作成
```

### Source Code (repository root)

```text
frontend/src/app/pcs/register/page.tsx
frontend/src/services/pc-api.ts
frontend/src/types/user.ts
backend/ecs/src/main.py
backend/ecs/src/models/user.py
backend/ecs/src/services/pc_service.py
backend/tests/
backend/ecs/tests/
```

**Structure Decision**: `001-pc-management` と同じ Web Application 構造を採用し、今回の修正はPC登録画面、ECS API、既存テストに限定する。Lambdaは既存プロキシを再利用し、独自のユーザー取得経路は追加しない。

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| N/A | Constitution違反なし | N/A |

## Constitution Check（Phase 1 後）

- [x] 新規データモデルは `User` と `PC.ownerId` の既存定義のみを利用する。
- [x] APIの認可・入力検証をサーバー側で行い、UIだけの制御に依存しない。
- [x] 既存のLambda/ECS境界、DynamoDB、コスト最適化方針を変更しない。
- [x] 指定されたUI方針（`001-pc-management` と同等のPC向けフォーム）を維持する。
- [x] 仕様のAC、異常系、手動確認項目が各Stepに対応している。

**最終判定**: PASS。未決事項は実装開始前に上記の順番で解消し、解消前に新規属性や認証仕様を推測しない。
