# Research & Technical Decisions: ボットアクセスによる不要起動防止と自動停止の確実化

**Feature**: `005-prevent-bot-ecs-wakeup`  
**Status**: Completed  
**Last Updated**: 2026-11-06  

---

## 1. 課題の整理と技術調査

### 1.1 課題1: 非業務パスアクセスによるECS不要起動
- **現象**:
  インターネット上の検索クローラーや脆弱性スキャナーが `/robots.txt`、`/favicon.ico`、`/sitemap.xml` などの非業務パスにアクセスした際、FastAPI のリバースプロキシ設定により ECS の自動起動（`ecs_manager.ensure_ecs_running()`）が呼び出され、コンテナが起動してしまう。
- **原因**:
  `backend/lambda/src/main.py` の ECS リバースプロキシがワイルドカード `@app.api_route("/{path:path}", ...)` で定義されており、Lambda 側で直接処理するルート（`/`, `/api/auth/*`）以外のすべてのパスがプロキシ対象となっていた。
- **方針検討**:
  - **案A**: プロキシのルートを `@app.api_route("/api/{path:path}", ...)` に限定する。
    - メリット: フロントエンド（Next.js）からの正規 API リクエストはすべて `/api/` プレフィックスが付与されている（例: `/api/pcs`, `/api/users`）。非業務パスは未定義ルートとなり、FastAPI のデフォルト挙動により 404 Not Found が即座に返却され、`proxy_to_ecs` 関数（および `ensure_ecs_running`）は一切実行されない。
    - デメリット: なし。
  - **案B**: `proxy_to_ecs` 内で `path` をブラックリスト/ホワイトリスト判定する。
    - メリット: ルート定義自体は変更不要。
    - デメリット: プロキシハンドラが実行され、受付ログやオーバーヘッドが発生する。ブラックリスト漏れのリスクがある。
  - **決定**: **案A を採用**。FastAPI のルーティング階層で `/api/{path:path}` に制限し、非業務パスはハンドラ到達前に 404 で遮断する。

### 1.2 課題2: 単発起動・早期離脱時の `lastActivityAt` 未設定による自動停止スキップ
- **現象**:
  ボットアクセスやユーザーの早期離脱（起動待機 503 受信後にブラウザを閉じる等）により、初回起動要求後に後続の業務要求（2xx 完了）が 1 件も来なかった場合、定期監視パトロール（`check_and_auto_sleep`）が実行されてもコンテナが停止されず、永久に稼働し続けて課金が発生する。
- **原因**:
  1. `SystemActivity/global` における `lastActivityAt` は、リクエストがプロキシ転送され 2xx 成功で完了した時（`ecs_manager.finish_in_flight(succeeded=True)`）にのみ更新される。起動受付時や起動処理時には設定されない。
  2. `check_and_auto_sleep` では、`lastActivityAt` が存在しない場合、`invalid_runtime_activity: lastActivityAt is missing` と判定してフェイルオープン（安全装置）により停止処理をスキップする。
  3. 初回リクエストで ECS タスクが起動しても、後続リクエストが来ないため `get_ecs_public_ip()` や `start_ecs()` による `_mark_runtime_running()` が呼ばれず、DynamoDB 上の `runtimeState` が `"STARTING"` のまま残る。`check_and_auto_sleep` の停止条件は `runtimeState=:running` であるため、状態不一致で停止できない。
- **方針検討**:
  - **対策1（初期活動時刻の設定）**:
    - `ecs_manager.record_request_accepted` および `_claim_start` において、`lastActivityAt` の初期値として現在時刻を設定する（`if_not_exists(lastActivityAt, :now)` または起動世代更新時に現在時刻を設定）。
    - これにより、後続リクエストが一切来なくても、起動要求時刻が `lastActivityAt` として記録される。
  - **対策2（`check_and_auto_sleep` のフォールバックと孤立タスク救済）**:
    - 万が一 `lastActivityAt` が未設定または不正な場合でも、`lastAcceptedAt` や `startRequestedAt` が存在すればそれをフォールバックとして採用する。
    - `runtimeState` が `"STARTING"` のまま放置され、かつ起動ロック期限（`startLockExpiresAt`）が経過し、アイドル判定時間（2時間）を経過している場合、ECS 実タスクが稼働中であれば安全に停止処理（`STOPPING` -> `STOPPED`）へ移行できる条件式（`ConditionExpression`）に拡張する。
  - **決定**: **対策1 と 対策2 の両方を実装**。根本原因である `lastActivityAt` の初期化を行うと同時に、定期パトロール側の安全装置を多重防護（Defense in Depth）として強化する。

---

## 2. 制約事項と技術選定

- **使用技術**:
  - Python 3.11 / 3.12
  - FastAPI (既存バージョン)
  - boto3 / botocore (既存バージョン)
  - Amazon DynamoDB (既存 `SystemActivity` テーブル、スキーマ変更なし)
  - Amazon ECS / Fargate (既存設定、変更なし)
- **新規ライブラリ**: 一切追加しない（ユーザー指示および Constitution 厳守）。
- **影響範囲**:
  - `backend/lambda/src/main.py`: ルーティングデコレータおよび転送パスの微修正。
  - `backend/lambda/src/services/ecs_manager.py`: `lastActivityAt` 初期化と `check_and_auto_sleep` の判定ロジック拡張。
  - `backend/lambda/tests/`: 該当ユースケースのユニットテスト追加。
  - フロントエンド、認証、ECSコンテナ内コード、AWS CDK インフラ定義への影響: なし。

---

## 3. 未解決事項（NEEDS CLARIFICATION）の確認と解決

- **Q1: `/api/{path:path}` に変更した場合、プロキシ転送先 URL はどうなるか？**
  - **解決**: FastAPI で `@app.api_route("/api/{path:path}")` とした場合、引数 `path` には `"api/"` 以降の文字列が入る（例: `/api/pcs` の場合 `path="pcs"`）。
  - ECS 側のエンドポイントはすべて `/api/...`（例: `/api/pcs`）であるため、転送先 URL は `http://{public_ip}:80/api/{path}{query_string}`、署名対象パスは `/api/{path}{query_string}` とする。
  - `/api` 単体へのアクセスも考慮し、空パス時も正規に処理できるよう正規化を行う。
- **Q2: `check_and_auto_sleep` で `runtimeState` が `STARTING` のままのタスクを停止する際の安全性は？**
  - **解決**: `startLockExpiresAt`（デフォルト180秒）が現在時刻以前であり、かつ `inFlightCount == 0`、アイドル経過時間が 2 時間（7200秒）以上である場合に限り停止を許可する。起動直後の過渡状態を誤って停止することは絶対にない。
