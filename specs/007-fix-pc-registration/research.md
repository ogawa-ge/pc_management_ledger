# Research: PC新規登録時の登録失敗・画面固まり解消 & 技術スタック脆弱性調査

## Decision 1: ECS への `Users` テーブル読み取り権限付与（最小権限）
- **Decision**: `infrastructure/app.py` から `EcsStack` へ `users_table=database_stack.users_table` を渡し、`infrastructure/stacks/ecs_stack.py` で `users_table.grant_read_data(task_definition.task_role)` を追加する。
- **環境変数は追加しない**: ECS の Python コード（`backend/ecs/src/models/user.py` / `backend/ecs/src/main.py`）はテーブル名 `'Users'` を直書きしており、`USERS_TABLE_NAME` を読むコードは存在しない。IAM の許可はテーブル ARN 単位で付与されるため環境変数は不要であり、未使用の設定を増やさない（`backend/ecs/` 側も変更しない）。
- **Rationale**: ECS 側の `POST /api/pcs`、`GET /api/users`、`POST /api/pcs/{pc_id}/return` は認証ユーザーの本人確認・ロール判定・オーナー（利用可能なユーザー）の実在確認のために `Users` テーブルを参照するが、書き込みは Lambda 側（`/api/auth/sync-user`）が担当するため、読み取り専用権限（`grant_read_data`）のみを付与するのが最小権限の原則に合致する。
- **Alternatives considered**: `grant_read_write_data`（書き込み不要のため却下）、全テーブル `*` 権限（セキュリティ原則違反のため却下）、`USERS_TABLE_NAME` 追加（未使用のため却下）。

## Decision 2: 管理者向けオーナー候補一覧取得（`getUsers`）のコールドスタート対応・ECS起動待機表示の解除・日本語エラー表示
- **Decision**:
  1. `frontend/src/services/pc-api.ts` の `getUsers` を `requestWithRetry` 経由に変更し、コールドスタート時の HTTP 503 (`status: "starting"`) に対して自動待機・リトライできるようにする。
  2. `frontend/src/app/pcs/register/page.tsx` の `fetchUsers` および `handleSubmit` の `catch` ブロックで `ecsLoading.setIsLoading(false)` を明示的に呼び出し、3分タイムアウト（`status: 'timeout'`）や通信例外時に ECS起動待機表示（`ECSLoadingState`）が閉じずに残存する不具合を防ぐ（`frontend/src/app/pcs/page.tsx` と同様の安全処理）。
  3. `registrationError` を「PCを登録」ボタンの直上にも表示する。現行の `frontend/package.json` には Tailwind CSS が未導入で `text-red-600` が反映されないため、インラインスタイル（例: `style={{ color: '#dc2626', fontWeight: 600 }}`）を併用して視認性を確実に担保する。
  4. 登録失敗時のメッセージは `error.message`（`Failed to resolve authenticated user` や `HTTP error! status: 503` などの英語の生メッセージ）をそのまま表示せず、`frontend/src/app/pcs/page.tsx`（Issue #10）と同方針でステータス別の日本語メッセージに変換する。
     - `401` / `403`: 「アクセス権限がありません。ログイン状態を確認してください。」
     - `start_timeout`: `ApiError` が持つタイムアウト用メッセージ（「バックエンドの起動が3分以内に完了しませんでした。操作は完了していません。」）
     - `500` 以上: 「サーバーでエラーが発生しました。しばらく経ってから再試行してください。」
     - その他 / 通信断: 「PCの登録に失敗しました。サーバーに一時的に接続できません。」
     - 既存の `404`（オーナーが利用不可）の専用処理は維持する。
- **Rationale**: 既存の `requestWithRetry`、`ECSLoadingState`、`ApiError` ハンドリングと Issue #10 のメッセージ方針を再利用することで、新規ライブラリや複雑な状態管理を増やさずに最小差分で解決できる。

## Decision 3: 主原因の実証（実装前の読み取り専用確認 / T000）
- **Decision**: 実装前に、AWS 上で次の3点を読み取り専用で確認し、主原因が `Users` テーブルの権限不足であることを実証する（`Force_MFA` ポリシーのため MFA セッションが必要）。手順は `quickstart.md` §0 に記載する。
  1. ECS タスクロールのポリシーに `Users` テーブルが含まれていないこと。
  2. ECS のロググループに、`Users` テーブルを参照するエンドポイントでの HTTP 503 エラーが記録されていること。
  3. 画面上「PCを登録」ボタンを押しても無反応になる挙動とログが一致すること。
- **Rationale**: 原因はソース解析からの推定であり、権限不足でなかった場合に CDK デプロイが無駄になるため。確認できない場合は実装を止めて再分析する（Constitution Layer 1: No Hallucination）。
- **実環境での実証結果（2026-11-19 実施・機密情報マスク済み）**:
  1. **ECS タスクロールの IAM ポリシー確認**:
     - 現行タスク定義（`EcsStackPCManagementTaskDefinition...:2`）のタスクロールに付与されたインラインポリシー（`PCManagementTaskDefinitionTaskRoleDefaultPolicy...`）を確認した結果、DynamoDB の許可リソースは以下の 4 テーブルのみであり、**`table/Users` が一切含まれていないことを実証**：
       - `arn:aws:dynamodb:ap-northeast-1:<account-id>:table/PCUsageHistories`
       - `arn:aws:dynamodb:ap-northeast-1:<account-id>:table/PCs`
       - `arn:aws:dynamodb:ap-northeast-1:<account-id>:table/ReturnRecords`
       - `arn:aws:dynamodb:ap-northeast-1:<account-id>:table/SystemActivity`
  2. **ECS コンテナログ（CloudWatch Logs）での 503 発生実証**:
     - ECS コンテナのロググループ（`EcsStack-PCManagementTaskDefinitionPCManagementContainerLogGroup...`）にて、以下のログを確認：
       ```text
       [2026-11-18 17:26:59 JST] INFO: <ip>:<port> - "GET /api/pcs HTTP/1.1" 200 OK
       [2026-11-18 17:35:19 JST] INFO: <ip>:<port> - "GET /api/pcs?status=Unused HTTP/1.1" 200 OK
       [2026-11-18 17:35:27 JST] INFO: <ip>:<port> - "GET /api/pcs HTTP/1.1" 200 OK
       [2026-11-18 17:35:30 JST] INFO: <ip>:<port> - "GET /api/users HTTP/1.1" 503 Service Unavailable
       ```
     - `PCs` テーブルのみを参照する `GET /api/pcs` は `200 OK` で成功している一方、`/pcs/register` 画面遷移直後（`17:35:30 JST`）に `Users` テーブルを参照する `GET /api/users`（`get_request_principal` → `dynamodb.Table('Users').get_item`）が IAM 権限不足により例外となり、ECS から **`503 Service Unavailable`** が返却されていることを実証。
     - さらに、この `503` によりフロントエンド（`register/page.tsx`）の `userListStatus` が `'error'` となり、「PCを登録」ボタンが `disabled` でロックされて押せなくなっていた（そのため `POST /api/pcs` 自体が送信されず画面が固まったように見えていた）ことも完全に裏付けられた。

---

## Decision 4: 技術スタックの脆弱性調査結果（2026-11-18 時点）

### 4-1. フロントエンド（`frontend/package.json` / `npm audit` 実測結果）
`npm --prefix frontend audit` を実行した結果、**計 14 件の脆弱性（Critical: 3, High: 7, Moderate: 4）** が検出された。すべて `fixAvailable: true` となっている。

| パッケージ | 現在のバージョン | 深刻度 | 主な内容 | 対応方針案 |
|---|---|---|---|---|
| `next` | `^16.2.4` | **Critical** | ルーティング / ミドルウェア / prefetch 関連の認証バイパス等（`CVE-2026-45109` 等） | `16.2.6` 以上のパッチ版へアップデート推奨（`npm audit fix` で対応可能か確認） |
| `next-auth` | `^4.24.14` | **Critical** | OAuth アカウントリンク認証バイパス・メール正規化不備（`CVE-2026-73419`, `CVE-2026-73420` 等） | **`4.24.15` 以上**へのパッチアップデート推奨 |
| `@types/next-auth` | `^3.13.0` | **High** | 推移的依存（`typeorm` / `jose` 等）に起因する脆弱性 | `next-auth` v4 には型定義が同梱されているため、互換性確認の上で更新または整理を検討 |
| その他推移的依存 | — | High / Moderate | `brace-expansion`, `js-yaml`, `nanoid`, `postcss`, `sharp`, `source-map-js`, `uuid` 等 | `npm audit fix` により破壊的変更なしで解消可能か検証 |

### 4-2. インフラ（`infrastructure/requirements.txt`）
- `aws-cdk-lib`（`2.276.0`）：過去の主要脆弱性（`CVE-2026-107608`, `CVE-2026-13760`）の修正済みバージョン以降であり、現時点で既知の重大脆弱性はなし。アップデート不要。

### 4-3. バックエンド（`backend/ecs/requirements.txt`, `backend/lambda/requirements.txt`）
- `fastapi==0.104.1`：旧バージョンのため、依存する Starlette 等の ReDoS 系脆弱性指摘の対象になりやすい。
- `python-jose[cryptography]==3.3.0`（Lambda のみ）：`CVE-2025-61152`（`alg=none` バイパス）、`CVE-2024-33663`（Algorithm Confusion）、`CVE-2024-33664`（JWE DoS）等の既知脆弱性が存在（メンテナンス停滞のため `PyJWT` への移行や明示的なアルゴリズム固定が推奨される）。

### 4-4. スコープ判断
- Constitution Layer 4（厳格なスコープ制限）に従い、フロントエンド（`next` / `next-auth` 等）およびバックエンド（`fastapi` / `python-jose` 等）の脆弱性アップデートはいずれも本 Issue #30 には含めず、**別 Issue（Issue #32: セキュリティアップデート）として切り出して対応**する。本 Issue では PC 新規登録の不具合修正のみに集中する。

## Decision 5: スコープ外の所見（認証・認可まわり）
- 分析中に、依存パッケージ更新と併せて検討すべき認証・認可まわりの強化項目（トークン検証用の鍵の扱い、ECS 側の利用者認証方式、一部エンドポイントの認証有無）を確認した。公開リポジトリのため詳細はここに記載せず、**Issue #32 に追記して対応方針を管理**する。本 Issue #30 では変更しない。
