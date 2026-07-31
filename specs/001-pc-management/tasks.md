# 実装タスク：PC 管理台帳

## 依存関係

```mermaid
graph TD
    Setup[フェーズ 1: セットアップ] --> Foundation[フェーズ 2: 基盤構築]
    Foundation --> US1[US1: Microsoft アカウントログイン]
    Foundation --> US3_5[US3.5: 権限管理]
    US1 --> US2[US2: ユーザーによる PC 登録]
    US1 --> US4[US4: PC およびユーザー一覧の確認]
    US3_5 --> US3[US3: 管理者による PC 代理登録]
    US2 --> US5[US5: PC 返却プロセス]
    US4 --> US6[US6: 未使用 PC 一覧の確認]
    US5 --> Polish[最終フェーズ：仕上げ]
    US6 --> Polish
    US3 --> Polish
```

## フェーズ 1: セットアップ

**目標**: プロジェクト構造とコアとなる依存関係を初期化する。

- [x] T001 `frontend/` に Next.js プロジェクトを初期化する
- [x] T002 [P] `backend/lambda/` に Python 環境と FastAPI をセットアップする
- [x] T003 [P] `backend/ecs/` に Python 環境と FastAPI をセットアップする
- [x] T004 [P] `infrastructure/` に AWS CDK プロジェクトを初期化する
- [x] T005 [P] `docs/session-notes.md`、`docs/backlog.md`、`docs/troubleshooting.md`、`docs/ubiquitous-language.md` を作成し、初期化する

## フェーズ 2: 基盤構築

**目標**: 共有インフラストラクチャと基盤となるコンポーネントをセットアップする。

- [x] T006b `infrastructure/stacks/database-stack.py` で DynamoDB テーブル (Users, PCs, ReturnRecords, PCUsageHistories) を定義する
- [x] T006 `infrastructure/stacks/lambda-stack.py` で Lambda 関数のインフラを実装する
- [x] T007 `infrastructure/stacks/ecs-stack.py` で ECS クラスターとタスク定義を実装する
- [x] T008 [P] `backend/lambda/src/db.py` で共有の DynamoDB クライアントを実装する
- [x] T009 [P] `backend/ecs/src/db.py` で共有の DynamoDB クライアントを実装する

## フェーズ 3: Microsoft アカウントログイン [US1]

**目標**: ユーザーは Microsoft アカウントを使用してシステムにログインし、適切な権限でアクセスできる。
**独立テスト**: Microsoft アカウントでのログインが成功し、ユーザーの権限に応じた画面が表示されることを確認する。

- [x] T010 [US1] `frontend/src/app/api/auth/[...nextauth]/route.ts` で Azure AD プロバイダーを使用した next-auth を設定する
- [x] T011 [US1] `frontend/src/app/login/page.tsx` でログインページの UI を実装する
- [x] T012 [US1] `frontend/src/middleware.ts` で保護されたルート用の認証ミドルウェアを実装する
- [x] T013 [US1] `backend/lambda/src/main.py` で認証 API エンドポイントを作成する
- [x] T014 [US1] `backend/lambda/src/services/auth-service.py` でユーザー権限の検証ロジックを実装する

## フェーズ 4: 権限管理 [US3.5]

**目標**: システム内で管理者と一般ユーザーの権限を管理する。
**独立テスト**: テーブルの権限値を手動で変更し、その権限に応じたアクセス制御が機能することを確認する。

- [x] T015 [US3.5] `backend/lambda/src/models/user.py` で User モデルとリポジトリを作成する
- [x] T016 [US3.5] `frontend/src/lib/rbac.ts` でロールベースのアクセス制御 (RBAC) ユーティリティを実装する
- [x] T017 [US3.5] `frontend/src/app/api/auth/[...nextauth]/route.ts` で認証セッションにユーザー権限を含めるよう更新する

## フェーズ 5: ユーザーによる PC 登録 [US2]

**目標**: 一般ユーザーは自分の PC をシステムに登録し、スペック情報を簡単に入力できる。
**独立テスト**: ユーザーがターミナルを起動した際にスペック取得コマンドが実行され、その結果がフォームに反映された後、Gemini API によって整形されたデータが正しく登録され、適切な管理番号が付与されることを確認する。

- [x] T018 [US2] `backend/ecs/src/models/pc.py` で PC モデルとリポジトリを実装する
- [x] T019 [US2] `backend/ecs/src/services/gemini-service.py` で Gemini API 連携サービスを作成する
- [x] T020 [US2] `backend/ecs/src/main.py` でスペック解析エンドポイント `/api/pcs/parse-specs` を実装する
- [x] T021 [US2] `backend/ecs/src/main.py` で PC 登録エンドポイント `/api/pcs` を実装する
- [x] T022 [US2] `backend/ecs/src/services/pc-service.py` で自動採番ロジック (N-XXX, D-XXX) を実装する
- [x] T023 [US2] `frontend/src/app/pcs/register/page.tsx` で PC 登録フォームの UI を作成する
- [x] T024 [US2] `frontend/src/components/terminal-command.tsx` でターミナルコマンドの生成とクリップボードへのコピー機能を実装する
- [x] T025 [US2] `frontend/src/services/pc-api.ts` でフロントエンドのフォームと parse-specs および登録 API を統合する

## フェーズ 6: 管理者による PC 代理登録 [US3]

**目標**: 管理者は特定のユーザーを指定して、そのユーザーの代理として PC を登録できる。
**独立テスト**: 管理者がユーザーを選択し、PC 情報を登録した結果が、選択したユーザーの PC として正しく紐づき、管理番号が付与されることを確認する。

- [x] T026 [US3] `backend/ecs/src/main.py` で管理者ドロップダウン用のユーザー一覧エンドポイントを実装する
- [x] T027 [US3] `backend/ecs/src/main.py` で管理者が ownerId を指定できるように PC 登録エンドポイントを更新する
- [x] T028 [US3] `frontend/src/app/pcs/register/page.tsx` で管理者向けの PC 登録フォームにユーザー選択ドロップダウンを追加する

## フェーズ 7: PC およびユーザー一覧の確認 [US4]

**目標**: 管理者はシステムに登録されているすべての PC 一覧とユーザー一覧を確認できる。
**独立テスト**: 管理者権限でアクセスした際に、全 PC と全ユーザーのリストが正しく表示されることを確認する。

- [x] T029 [US4] `backend/ecs/src/main.py` で PC 一覧エンドポイント `/api/pcs` を実装する
- [x] T030 [US4] `frontend/src/app/pcs/page.tsx` で PC 一覧ページの UI を作成する
- [x] T031 [US4] `frontend/src/app/pcs/page.tsx` で CSV ダウンロード機能を実装する
- [x] T032 [US4] `frontend/src/app/globals.css` で PC 向けのレイアウトに対応したレスポンシブデザインを確保する

## フェーズ 8: PC 返却プロセス [US5]

**目標**: ユーザーは不要になった PC を返却するためのフォームを送信できる。
**独立テスト**: ユーザーが返却日、返却理由、PC の状態を入力して送信し、PC のステータスが更新されることを確認する。

- [x] T033 [US5] `backend/ecs/src/models/return-record.py` で ReturnRecord モデルとリポジトリを実装する
- [x] T034 [US5] `backend/ecs/src/main.py` で PC 返却エンドポイント `/api/pcs/{pcId}/return` を実装する
- [x] T035 [US5] `frontend/src/app/pcs/[pcId]/return/page.tsx` で PC 返却フォームの UI を作成する
- [x] T036 [US5] `backend/ecs/src/services/pc-service.py` で PC のステータス遷移ロジックを更新する

## フェーズ 9: 未使用 PC 一覧の確認 [US6]

**目標**: ユーザー（および管理者）は、現在誰にも割り当てられていない未使用の PC 一覧を確認できる。
**独立テスト**: 未使用 PC 一覧画面にアクセスし、ステータスが「未使用」の PC のみが表示されることを確認する。

- [x] T037 [US6] `backend/ecs/src/main.py` でステータスによるフィルタリングをサポートするように PC 一覧エンドポイントを更新する
- [x] T038 [US6] `frontend/src/app/pcs/unused/page.tsx` で未使用 PC 一覧のビュー/タブを作成する

## 最終フェーズ：仕上げ

**目標**: 横断的な関心事、最終テスト、デプロイの準備。

- [x] T039 `backend/lambda/src/services/ecs-manager.py` で Lambda 経由の ECS 自動スリープおよび起動ロジックを実装する
  - [x] T039-1 ECS タスク起動関数 `start_ecs_task()` の実装
  - [x] T039-2 ECS タスク停止関数 `stop_ecs_task()` の実装
  - [x] T039-3 アイドルタイムアウト判定関数 `check_idle_timeout()` の実装（2 時間ルール）
  - [x] T039-4 CloudWatch Events トリガー対応（1 時間ごとのチェック）
  - [x] T039-5 関連 DynamoDB フィールド `lastActivityAt` の記録・更新ロジック
  - [x] T039-6 CloudWatch Logs への監査ログ出力
- [x] T040 `frontend/src/components/ecs-loading-state.tsx` で ECS コールドスタート時にフロントエンドに「loading...」UI を追加する
- [x] T041 `scripts/migrate-excel-data.py` で既存の Excel データ用のデータ移行スクリプトを作成する
- [x] T042 最終的なエンドツーエンドテストとバグ修正
  - [x] T042-1 Gemini 精度テストスイート実装
    - [x] T042-1-1 標準フォーマットのターミナル出力テストケース 50+ 件の作成
    - [x] T042-1-2 エッジケース（手書きログ、非標準フォーマット等）テストケース 50+ 件の作成
    - [x] T042-1-3 精度計算スクリプト（6 項目中 5 項目正確性判定）の実装（`backend/ecs/tests/test-gemini-accuracy.py`）
  - [x] T042-2 Excel 移行検証
    - [x] T042-2-1 D-001～D-007、N-001～N-034 の欠損なし確認
    - [x] T042-2-2 採番の正確性（D-008 以降、N-035 以降から自動採番開始）の確認
    - [x] T042-2-3 ステータス初期値の妥当性（「利用中」または「未使用」）の確認
  - [x] T042-3 ECS 自動スリープ検証（2 時間タイムアウト、CloudWatch Events トリガーの動作確認）
  - [x] T042-4 完全なエンドツーエンドフロー検証（Microsoft SSO → PC 登録 → Gemini 抽出 → 一覧表示 → PC 返却）
