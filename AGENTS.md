# pc_management_ledger Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-11-20

## Active Technologies

- TypeScript (Next.js), Python (FastAPI, AWS CDK) + Next.js, FastAPI, AWS CDK, AWS SDK (boto3), Gemini API (001-pc-management)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

TypeScript (Next.js), Python (FastAPI, AWS CDK): Follow standard conventions

## Recent Changes

- 001-pc-management: Added TypeScript (Next.js), Python (FastAPI, AWS CDK) + Next.js, FastAPI, AWS CDK, AWS SDK (boto3), Gemini API

<!-- MANUAL ADDITIONS START -->

## Project Core Rules (from `.specify/memory/constitution.md`)

すべての AI ツール・チャットセッションにおいて、以下のプロジェクト原則を厳守すること（詳細なガバナンス規定は `.specify/memory/constitution.md` を正本として優先参照）。

### 1. 基本原則
- **日本語出力**: すべてのドキュメント、設計、コード解説、プラン作成、タスク出力は **日本語** で行うこと。
- **スキーマ推測の禁止（No Hallucination）**: DB テーブル名、カラム名、API エンドポイント仕様を推測しないこと。必ず該当機能の `specs/<feature>/data-model.md` および `contracts/` を一次ソースとして参照し、未定義のものは「未定義」として扱うこと。
- **Security First**: 認証ロジックや機密データに実データや本物のキー情報は一切含めず、常に環境変数やダミーデータを用いること。

### 2. アーキテクチャ・コスト・AI 方針
- **Hybrid Responsibility**: ログインや軽量処理は **AWS Lambda**、重いバッチや管理者機能は **Amazon ECS** で実行する役割分担を厳守すること。
- **Cost-Awareness**: 月額数百円〜数千円に抑えるため、ECS の自動停止（2 時間未使用でスリープ）や ALB を回避する設計を最優先すること。
- **AI Logic**: Gemini API による PC スペック抽出は、正規表現や固定パースに頼りすぎず、LLM の柔軟性を活かした非構造化データからの抽出を設計すること。

### 3. コーディング・命名規約
- **Clean Code**: 命名だけで意図が伝わる自己記述的なコードを記述し、過度なコメントに頼らないこと。
- **Naming Convention**:
  - ディレクトリ名および一般ファイル名は `kebab-case`（例: `pc-list-container.tsx`）。
  - Python モジュールおよび Python テストファイルは PEP 8 と既存 import 規約に従い `snake_case` を許可する。
  - `page.tsx`、`conftest.py`、`package.json` などフレームワーク／ツールの予約ファイル名は規約を優先する。
- **Ubiquitous Language**: 変数名・カラム名・ファイル名は `docs/ubiquitous-language.md` の定義を正守し、新しい用語が登場した際は実装前に同ドキュメントを更新すること。

### 4. 複数人開発・運用ルール
- **Issue 単位のブランチ＆ドキュメント管理**: 開発は必ず Issue ごとにブランチを切り、`specs/issue-<issue番号>-<feature-name>/` 内で `spec.md` / `plan.md` / `tasks.md` を閉じて管理すること。コンフリクト防止のため、`docs/session-notes.md` や `docs/backlog.md` の日常的なタスク管理への使用は控えること。
- **Spec Kit（`/speckit-specify`）実行時のブランチ・ディレクトリ命名ルール**:
  - デフォルトの連番（`00x-...`）での自動採番は使わず、必ず GitHub Issue 番号を用いること（依頼に Issue 番号が含まれていない場合は、実行前に必ずユーザーへ確認すること）。
  - ブランチ作成フック（`speckit.git.feature`）実行時は、環境変数 `GIT_BRANCH_NAME` に `issue-<issue番号>-<feature-name>`（例: `issue-34-update-spec-kit`）を設定して実行すること。
  - 仕様ディレクトリは `SPECIFY_FEATURE_DIRECTORY` として `specs/issue-<issue番号>-<feature-name>`（例: `specs/issue-34-update-spec-kit`）を明示指定すること。
- **厳格なスコープ制限（変更の最小化）**: **担当する Issue の目的から外れたファイル・コードの変更、他画面の修正、無関係なリファクタリングは厳禁**。変更箇所は必要最小限に留め、他ブランチとのマージコンフリクトを防ぐこと。
- **ナレッジ共有**: 全体に影響する重要なアーキテクチャ決定や、他メンバーにも共有すべき重大なバグ・解決策のみ、例外的に `docs/troubleshooting.md` や `docs/ubiquitous-language.md` へ追記すること。

<!-- MANUAL ADDITIONS END -->

