<!--
Sync Impact Report
- Version change: 1.0.0 -> 1.1.0
- Modified principles: N/A (Initial setup based on user input)
- Added sections: Layer 1 to Layer 4
- Removed sections: N/A
- Templates requiring updates: N/A
- Follow-up TODOs: docs/ubiquitous-language.md, docs/session-notes.md, docs/backlog.md, docs/troubleshooting.md の作成
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
   * **Naming Convention**: ディレクトリ名、ファイル名はすべて `kebab-case`（例: `pc-list-container.tsx`）とする。
3. **AI Logic**:
   * Gemini APIを用いたスペック抽出の際、正規表現や固定のパースロジックに頼りすぎず、LLMの柔軟性を活かした「非構造化データからの正確な抽出」を設計すること。

* **Ubiquitous Language**:
  * 命名（変数名、カラム名、ファイル名）は、必ず `docs/ubiquitous-language.md` の定義を正守すること。
  * 新しい用語が登場した際は、実装前に必ず同ドキュメントを更新し、AIと人間の認識を同期させること。

## Layer 4: Documentation Workflow (運用ルール)
プロジェクトの継続的な品質維持とAIのコンテキスト把握のため、以下のドキュメント運用を徹底すること。

1. **`docs/session-notes.md` (セッションノート)**:
   * 直近の開発セッションにおける作業メモや一時的な記録を残すために使用する。
   * 今後のタスクは `docs/backlog.md` に、過去のトラブルシューティングは `docs/troubleshooting.md` に記載すること。
   * このファイルが長くなった場合は、`docs/archive/` フォルダに定期的にアーカイブすること。
2. **`docs/backlog.md` (プロジェクト・バックログ)**:
   * 今後の開発セッションで取り組むべき「次期開発アクション」や「未完了タスク」を記載する。
   * AIは開発開始時に必ずこのファイルを参照し、次に何をすべきかを把握すること。
3. **`docs/troubleshooting.md` (トラブルシューティング・ナレッジベース)**:
   * 過去の開発で発生した主要なエラー、バグ、およびその解決策を辞書的に記録する。
   * 同様の問題が発生した際の参照用として活用し、再発防止に努めること。
