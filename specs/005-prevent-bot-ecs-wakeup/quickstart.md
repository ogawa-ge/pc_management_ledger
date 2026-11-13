# Quickstart & Validation Guide: ボットアクセスによる不要起動防止と自動停止の確実化

**Feature**: `005-prevent-bot-ecs-wakeup`  
**Status**: Completed  
**Last Updated**: 2026-11-13  

---

## 1. 検証シナリオ概要

本ガイドは、GitHub Issue #27 で定義された以下の3つのコアシナリオを迅速かつ確実に検証するための手順を定めます。

1. **シナリオ1: 非業務パスアクセス時の不要起動遮断 (User Story 1)**
   - `/robots.txt`, `/favicon.ico` 等へアクセスした際、ECS起動処理を一切呼び出さず 404 が即座に返ること。
2. **シナリオ2: 単発起動・早期離脱時の自動停止確実化 (User Story 2)**
   - 初回要求で起動待機（503）となった後、後続通信が0件のまま2時間経過した状態で監視パトロールを実行した際、タスク数0へ自動停止すること。
3. **シナリオ3: 正規業務API利用時の既存オンデマンド起動と自動停止の維持 (User Story 3)**
   - `/api/pcs` 等の正規APIアクセスにおいて、初回503起動、稼働中200返却、利用後の自動スリープが既存同等に動作すること。

---

## 2. ユニットテストによる検証手順

### 2.1 テスト実行コマンド

```bash
# Lambda 側のテストスイートを実行
pytest backend/lambda/tests/test_lambda_ecs_proxy.py backend/lambda/tests/test_lambda_activity_tracking.py backend/lambda/tests/test_ecs_manager.py
```

### 2.2 検証対象テストケース

#### シナリオ1の検証 (`test_lambda_ecs_proxy.py`)
- `test_non_api_path_returns_404_without_starting_ecs`:
  - `GET /robots.txt`, `GET /favicon.ico`, `GET /sitemap.xml` に対し、FastAPI TestClient が 404 を返却すること。
  - `ecs_manager.ensure_ecs_running` および `ecs_manager.record_request_accepted` が一度も呼ばれていない（`assert_not_called()`）ことを検証。

#### シナリオ2の検証 (`test_lambda_activity_tracking.py`, `test_ecs_manager.py`)
- `test_start_ecs_initializes_last_activity_at`:
  - 起動要求受付（`record_request_accepted` / `_claim_start`）時に、DynamoDB 上の `lastActivityAt` が現在時刻で初期化されることを検証。
- `test_auto_sleep_stops_abandoned_task_in_starting_state`:
  - `runtimeState="STARTING"` かつ後続リクエスト 0 件（`inFlightCount=0`）の状態で、2時間経過を模擬して `check_and_auto_sleep` を実行した際、ECS停止（`desiredCount=0`）が実行され、`auto_slept` が返ることを検証。
- `test_auto_sleep_falls_back_when_last_activity_missing`:
  - 万が一既存データ等で `lastActivityAt` が存在しない場合でも、`startRequestedAt` または `lastAcceptedAt` から2時間経過していれば安全に停止できることを検証。

#### シナリオ3の検証 (`test_lambda_ecs_proxy.py`)
- `test_stopped_ecs_returns_machine_readable_starting_response`:
  - 正規API `/api/pcs` に対し、停止時は 503 と `Retry-After: 15` が返り、起動処理が呼び出されることを検証。
- `test_running_ecs_proxies_request_with_api_prefix`:
  - ECS 稼働時、`/api/pcs` へのリクエストが正しく ECS の `http://{public_ip}:80/api/pcs` へプロキシされることを検証。

---

## 3. 手動・結合検証手順（参考）

Lambda またはローカルサーバーを起動して確認する場合:

```bash
# 1. 未定義パスの遮断確認 (404 が返り、コンテナ起動ログが出ないこと)
curl -i http://localhost:8000/robots.txt
# => HTTP/1.1 404 Not Found

curl -i http://localhost:8000/favicon.ico
# => HTTP/1.1 404 Not Found

# 2. 正規APIの起動確認 (503 が返り、コンテナ起動処理がトリガーされること)
curl -i http://localhost:8000/api/pcs
# => HTTP/1.1 503 Service Unavailable
# => Retry-After: 15
```

---

## 4. 本番環境（AWS）へのデプロイ反映と実機検証記録（2026-11-13）

### 4.1 事象の再発確認と原因特定
- 2026-11-13 06:12 JST に外部クローラーによる `GET /robots.txt` アクセスが発生し、ECS タスクが起動（`generation: 11`）して `runtimeState = "STARTING"` のまま停止スキップされる事象を確認。
- 原因は、`main` ブランチへのマージ時点では Amplify（フロントエンド）のみ自動デプロイされ、バックエンドの `ApiLambda` および `TimeoutCheckLambda` が 2026-11-06 時点の旧コードのまま稼働していたためと特定。

### 4.2 本番 Lambda へのデプロイと実機検証結果
1. **Lambda 関数の更新（2026-11-13 14:33 JST）**:
   - 本番環境の `ApiLambda` および `TimeoutCheckLambda` に Issue #27 の修正済みコード（`src/main.py`、`src/services/ecs_manager.py`）をデプロイ反映。
2. **自動スリープ動作の実機検証**:
   - `SystemActivity` テーブル（`entityId="global"`）の活動時刻をアイドル閾値（2時間）超過状態に設定し、本番 `TimeoutCheckLambda` を実行。
   - `{"status": "auto_slept", "action_result": {"status": "stopped", "desired_count": 0}}` が返却され、ECS サービスが `desiredCount = 0`（`runtimeState = "STOPPED"`）へ正常に遷移することを確認。
3. **スリープ状態での非業務パス遮断検証**:
   - ECS が停止（`desiredCount = 0`）している状態で、本番 API Gateway エンドポイント（`https://<api-id>.execute-api.ap-northeast-1.amazonaws.com`）に対し `GET /robots.txt` および `GET /favicon.ico` を実行。
   - 両リクエストとも即座に `HTTP 404: {"detail":"Not Found"}` が返却され、アクセス後も `ECS desiredCount = 0` および `SystemActivity.runtimeState = "STOPPED"` が維持される（不要な ECS 起動が一切発生しない）ことを実機で確認完了。
