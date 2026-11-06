# Implementation Plan: ログイン方式のGoogle Workspaceへの変更

**Branch**: `004-google-workspace-login` | **Date**: 2026-10-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-google-workspace-login/spec.md`

## Summary

ログイン方式を Microsoft（Azure AD）から Google Workspace に切り替え、`@genuine-pt.jp` のアカウントだけを許可する（Issue #19）。

技術的には、NextAuth v4 のプロバイダを `AzureADProvider` から `GoogleProvider` に置き換える。ドメイン判定は `signIn` コールバック（サーバー側）で行い、`email_verified`・メールのドメイン・`hd` クレームの 3 点をすべて確認する。

あわせて、現状は存在しない「初回ログイン時のユーザー登録」を、Lambda の新しいエンドポイント `POST /api/auth/sync-user` で実装する。このエンドポイントでもドメインを再チェックする。

ユーザー ID は Google の `sub` とする。テーブル定義は変更せず、切り替え時に既存データを全削除する。詳細は [research.md](./research.md) を参照。

## Technical Context

**Language/Version**: TypeScript 6 / Next.js 16 / React 19（フロントエンド）、Python 3.9（Lambda、CDK のランタイム指定に準拠）、Python（CDK）

**Primary Dependencies**: NextAuth v4（`next-auth@^4.24`、`GoogleProvider`）、FastAPI + Mangum（Lambda）、boto3（DynamoDB）、AWS CDK（Python）。新しく追加する依存パッケージはない。

**Storage**: Amazon DynamoDB（`Users` テーブル。定義の変更なし）

**Testing**: pytest（Lambda の `sync-user` とドメイン判定）。フロントエンドは [quickstart.md](./quickstart.md) の手動シナリオで確認する（テスト基盤なし。research.md R-11）。

**Target Platform**: AWS Amplify Hosting（Next.js SSR）、AWS Lambda + API Gateway

**Project Type**: Web アプリケーション（frontend + backend + infrastructure）

**Performance Goals**: ログイン完了まで 1 分以内（SC-001）。ログイン時の追加処理は Lambda への 1 回の呼び出し（DynamoDB の `update_item` 1 回）のみ。

**Constraints**: ログイン処理で ECS を起動しない（FR-010）。新しい AWS リソースを追加しない（Cost-Awareness）。許可ドメインや認証情報をソースコードに書かない（FR-003）。

**Scale/Scope**: 社内利用者（数十名程度）。変更するファイルは約 10 個。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原則 | 判定 | 根拠 |
|---|---|---|
| L1-1 Output Language（日本語） | ✅ | すべての成果物を日本語で作成 |
| L1-2 No Hallucination | ✅ | テーブル名・カラム名は既存の `specs/001-pc-management/data-model.md` と CDK の定義を確認したうえで使用。新しく定義するものは本機能の [data-model.md](./data-model.md) と [contracts/api.md](./contracts/api.md) に明記した |
| L1-3 Security First | ✅ | 認証情報と許可ドメインは環境変数で管理。成果物には実際の値を含めない（ドメイン名は spec で決定済みの設定値） |
| L3-1 Hybrid Responsibility | ✅ | ログイン関連の処理（ユーザー登録・権限取得）は Lambda で完結し、ECS にプロキシしない |
| L3-1 Cost-Awareness | ✅ | 新しい AWS リソースなし。ログは既存の CloudWatch Logs を利用 |
| L3-2 Naming Convention | ✅ | 新規の TypeScript ファイルは kebab-case（例: `email-domain.ts`）、Python は snake_case |
| L3 Ubiquitous Language | ✅ | 実装前に `docs/ubiquitous-language.md` の User の定義を更新する（FR-011。tasks の最初に置く） |
| L4-1 Feature-based Documentation | ✅ | 成果物はすべて `specs/004-google-workspace-login/` に作成 |
| L4-2 Strict Scope Boundaries | ✅ | CORS 設定、`Bearer <userId>` の簡易認可、`/api/auth/me` などは範囲外とした（research.md R-11） |

**Post-design re-check（Phase 1 後）**: 違反なし。Complexity Tracking は不要。

## Project Structure

### Documentation (this feature)

```text
specs/004-google-workspace-login/
├── spec.md                 # 仕様（/speckit-specify, /speckit-clarify）
├── environment-setup.md    # 事前設定一覧（Issue #19 本文にも掲載）
├── plan.md                 # 本ファイル
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   └── api.md              # Phase 1
├── checklists/
│   └── requirements.md
└── tasks.md                # Phase 2（/speckit-tasks で作成）
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/
│   │   ├── api/auth/[...nextauth]/route.ts   # 変更: GoogleProvider、signIn コールバック、pages 設定
│   │   └── login/page.tsx                    # 変更: Google ログインボタン、?error= のメッセージ表示
│   ├── lib/
│   │   ├── email-domain.ts                   # 新規: ドメイン判定の関数
│   │   └── auth-service.ts                   # 変更: sync-user 呼び出し関数を追加
│   └── types/next-auth.d.ts                  # 変更: accessToken を削除
└── .env.local                                # 各自: AZURE_AD_* を削除し GOOGLE_* などを追加（git 管理外）

backend/
├── lambda/src/
│   ├── main.py                               # 変更: POST /api/auth/sync-user を追加（キャッチオールより前）
│   └── services/auth_service.py              # 変更: sync_user、ドメイン判定の関数を追加
└── tests/
    └── test_sync_user.py                     # 新規: sync-user とドメイン判定のテスト

infrastructure/stacks/lambda_stack.py         # 変更: AzureAdSecrets 参照を削除、ALLOWED_EMAIL_DOMAIN を追加

docs/ubiquitous-language.md                   # 変更: User の定義を Google Workspace アカウントに更新
```

**Structure Decision**: 既存の Web アプリケーション構成（`frontend/`・`backend/lambda/`・`infrastructure/`）をそのまま使う。新規ファイルは、ドメイン判定の関数（`frontend/src/lib/email-domain.ts`）とテスト（`backend/tests/test_sync_user.py`）の 2 つだけ。

## 実装の流れ

```text
ブラウザ ──「Googleアカウントでログイン」──▶ Google（hd=genuine-pt.jp で絞り込み）
                                                │ 認証
                                                ▼
                         NextAuth signIn コールバック（Amplify サーバー側）
                           ├─ email_verified / メールのドメイン / hd を判定
                           │    └─ NG → 拒否ログ出力 → /login?error=DomainNotAllowed
                           └─ OK → Lambda POST /api/auth/sync-user
                                     ├─ ドメインを再チェック（NG → 403 + 拒否ログ）
                                     ├─ Users に upsert（新規は role=User）
                                     │    └─ 失敗 → /login?error=RegistrationFailed
                                     └─ 成功 → ログイン完了（token.sub = Google sub）
                                                │
                         session コールバック → 既存の /api/auth/user-permissions で role 取得
```

## 決定事項の一覧（plan で確定した論点）

| 論点 | 決定 | 詳細 |
|---|---|---|
| ユーザー ID | Google の `sub` | research.md R-2 |
| ドメイン判定の場所 | NextAuth `signIn` コールバック ＋ Lambda `sync-user` の二重チェック | R-3、R-5 |
| 環境変数名 | `ALLOWED_EMAIL_DOMAIN` で確定 | R-3、data-model.md |
| CDK の `AzureAdSecrets` 参照 | 削除する | R-10 |
| CORS（新 Amplify の URL 追加） | 本 Issue の範囲外 | R-11 |
| テーブル構成 | 変更しない（全アイテム削除のみ） | R-9 |

## Complexity Tracking

Constitution Check に違反がないため、記載なし。
