<!--
Sync Impact Report
- Version change: 1.1.0 -> 1.1.1
- Modified principles: Layer 3 / Code Standard / Naming Convention
- Added sections: Governance
- Removed sections: N/A
- Templates requiring updates: N/A（実行時に本Constitutionを参照するため変更不要）
- Follow-up TODOs: N/A
-->

# Project Constitution: PC Management Ledger

## Layer 1: Global Directives (共通原則)
AIアシスタントは、本プロジェクトの全工程において以下の挙動を基本原則とすること。

1. **Output Language**:
   * すべてのドキュメント、設計、コード解説、プラン作成、およびタスクの出力は **日本語** で行うこと。
2. **No Hallucination (スキーマ推測の禁止)**:
   * データベースのテーブル名、カラム名、APIエンドポイントの仕様を一般的な知識で推測しないこと。必ず `specs/` ディレクトリ内の該当する機能フォルダにある `data-model.md` および `contracts/` を一次ソースとして参照し、定義されていないものは「未定義」として扱うこと。
3. **Security First**:
   * 認証ロジックや機密データの取り扱いにおいて、顧客の実データやリアルなキー情報は一切含めない。常に環境変数やダミーデータを用いた実装を提案すること。

## Layer 2: Project Mission (プロジェクトの魂)
* **Mission**: 「徹底したAWSコスト最適化と、Gemini APIによるPCスペック登録の完全自動化を両立する資産管理システム」
* **Core Value**: ユーザーが手入力でスペックを調べる苦痛を取り除き、かつ会社側のインフラコストを最小（月額数百円〜数千円）に抑えること。
* ※機能の具体的な詳細は、`specs/` ディレクトリ内の該当する機能フォルダにある `spec.md` を優先参照すること。

## Layer 3: Engineering Policies (開発の掟)
1. **Architecture Integrity**:
   * **Hybrid Responsibility**: ログインや軽量処理は Lambda、重いバッチや管理者機能は ECS で実行するという `plan.md` の役割分担を厳守すること。
   * **Cost-Awareness**: ECSの自動停止（2時間未使用でスリープ）や、ALBを回避する設計を最優先すること。
2. **Code Standard**:
   * **Clean Code**: 命名だけで意図が伝わる自己記述的なコードを記述し、過度なコメントに頼らないこと。
   * **Naming Convention**: ディレクトリ名および一般のファイル名は `kebab-case`（例: `pc-list-container.tsx`）とする。PythonモジュールおよびPythonテストファイルは、PEP 8と既存のimport規約に従うため `snake_case` を許可する。Next.jsの `page.tsx`、pytestの `conftest.py`、npmの `package.json` など、フレームワークまたはツールが要求する予約ファイル名は、その規約を優先する。
3. **AI Logic**:
   * Gemini APIを用いたスペック抽出の際、正規表現や固定のパースロジックに頼りすぎず、LLMの柔軟性を活かした「非構造化データからの正確な抽出」を設計すること。

* **Ubiquitous Language**:
  * 命名（変数名、カラム名、ファイル名）は、必ず `docs/ubiquitous-language.md` の定義を正守すること。
  * 新しい用語が登場した際は、実装前に必ず同ドキュメントを更新し、AIと人間の認識を同期させること。

## Layer 4: Documentation Workflow & Team Collaboration (複数人開発・運用ルール)
プロジェクトは複数メンバーによる並行開発へ移行したため、コンフリクトを回避し効率的に開発を進めるための以下の運用ルールを厳守すること。

1. **Feature-based Documentation (機能/Issue単位のドキュメント管理)**:
   * グローバルな docs/session-notes.md や docs/backlog.md は複数人開発ではコンフリクトの原因となるため、日常的なタスク管理としての使用は控える。
   * 開発は必ずIssueごとにブランチを切り、specs/<issue-number>-<feature-name>/ ディレクトリ内に spec.md (仕様), plan.md (実装計画),    tasks.md (進行状況) を作成し、Issue単位でドキュメントを閉じて管理すること。
2. **Strict Scope Boundaries (厳格なスコープ制限と変更の最小化)**:
   * 複数人が同時に異なる機能を開発しているため、**自身が担当するIssue（バグ修正や機能追加）の目的から外れたファイルやコードの変更、他画面の修正、無関係なリファクタリングは厳禁（ご法度）**とする。
   * 変更箇所は必要最小限に留め、他ブランチとのマージコンフリクトを極力発生させないこと。
3. **Knowledge Sharing & Troubleshooting (ナレッジ共有)**:
   * 全体に影響する重要なアーキテクチャの決定や、他メンバーにも共有すべき重大なバグ・解決策のみ、例外的に docs/troubleshooting.md や docs/ubiquitous-language.md へ追記する。追記時はコンフリクトに注意すること。

## Governance

* 本Constitutionは、仕様、計画、タスク、および実装上の慣例より優先する。各機能の計画時と実装開始前に、適合性を確認しなければならない。
* 原則の追加、削除、または意味を変更する改定は、影響範囲、移行方法、およびバージョン変更理由をSync Impact Reportに記録したうえで行う。
* バージョンはセマンティックバージョニングに従う。後方互換の明確化はPATCH、原則の追加または実質的拡張はMINOR、既存原則の削除または後方互換性のない変更はMAJORとする。
* Constitution違反は仕様分析および計画レビューでCRITICALとして扱い、実装開始前に成果物またはConstitutionを明示的に修正しなければならない。

**Version**: 1.1.1 | **Ratified**: 2026-04-14 | **Last Amended**: 2026-08-14