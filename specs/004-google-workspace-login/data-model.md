# Phase 1: Data Model — ログイン方式のGoogle Workspaceへの変更

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

本機能で変更するのは **User** エンティティのみ。PC・Return Record・PC Usage History の定義は [specs/001-pc-management/data-model.md](../001-pc-management/data-model.md) から変更しない（全アイテムを削除して空から始める点のみ異なる。research.md R-9）。

## User（DynamoDB Table: `Users`）

本ファイルの定義が、001 の data-model.md の User 定義に優先する。テーブル名・パーティションキーは変更しない。

| Field | Type | 必須 | Description | 変更点 |
|---|---|---|---|---|
| `userId` | String (PK) | ○ | Google アカウントの `sub`（不変の一意 ID） | 値の意味を変更（旧: Azure AD の `oid`） |
| `email` | String | ○ | Google Workspace のメールアドレス（`@genuine-pt.jp`）。保存時は小文字化する | 001 では未定義だったものを明記 |
| `name` | String | – | Google アカウントの表示名。取得できない場合は保存しない | 変更なし |
| `role` | String | ○ | `Admin` または `User`。新規作成時は `User` | 変更なし |
| `createdAt` | String | ○ | 初回ログイン日時（ISO 8601、UTC） | 変更なし |
| `updatedAt` | String | ○ | 最終ログイン時の更新日時（ISO 8601、UTC） | 変更なし |
| `lastActivityAt` | String | – | ECS の自動停止判定用（既存の `ecs_manager` が更新） | 変更なし（本機能では触らない） |

### バリデーションルール

| ルール | 由来 |
|---|---|
| `email` のドメイン部分（最後の `@` より後ろ）を小文字化した値が、`ALLOWED_EMAIL_DOMAIN` と完全一致すること | FR-002、research.md R-3・R-5 |
| `userId` は空文字不可 | — |
| 登録済みユーザーへの更新では `role`・`createdAt` を上書きしない | FR-007（権限はシステム内で手動管理） |

### ライフサイクル

```text
（未登録）
   │ 初回ログイン（ドメイン判定に通過）
   ▼
User（role = User） ── 管理者が DB を直接操作 ──▶ User（role = Admin）
   │ 2 回目以降のログイン
   ▼
name / email / updatedAt のみ更新（role は保持）
```

- ドメイン判定で拒否されたアカウントは、Users に一切書き込まない（spec US2 シナリオ 3）。
- 最初の管理者は、本人の初回ログイン後に DynamoDB の該当アイテムの `role` を `Admin` に手動で変更する（spec Assumptions）。手順は [quickstart.md](./quickstart.md) を参照。

## 許可ドメイン（設定値）

データとしては保持しない。環境変数で設定する。

| 変数名 | 設定先 | 値 |
|---|---|---|
| `ALLOWED_EMAIL_DOMAIN` | Amplify（フロントエンド）、Lambda（CDK デプロイ時に設定） | `genuine-pt.jp` |

## 切り替え時のデータ削除

| テーブル | 対応 |
|---|---|
| `Users` | 全アイテム削除 |
| `PCs` | 全アイテム削除 |
| `ReturnRecords` | 全アイテム削除 |
| `PCUsageHistories` | 全アイテム削除 |
| `SystemActivity` | 対象外（ユーザーデータではない） |
