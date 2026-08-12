# Phase 1: Data Model

本機能では新規エンティティや新規テーブルを追加しない。定義は `specs/001-pc-management/data-model.md` を一次ソースとする。

## User（DynamoDB Table: `Users`）

| Field | Type | 本機能での用途 |
|---|---|---|
| `userId` | String (PK) | optionのvalue、PC.ownerIdとの紐付けに使う一意識別子 |
| `name` | String | 選択肢の表示名。欠落時は代替表示が必要 |
| `email` | String | 選択肢の補助表示。欠落時もuserId等で識別可能にする |
| `role` | String (`Admin` / `User`) | 実行者の権限確認。候補ユーザーの表示値ではない |
| `createdAt` / `updatedAt` | String | 既存データとして保持。今回のUI選択では変更しない |

## PC（DynamoDB Table: `PCs`）

| Field | Type | 本機能での用途 |
|---|---|---|
| `pcId` | String (PK) | 既存の管理番号採番を維持 |
| `ownerId` | String | 選択した User の `userId`。登録時に一致を検証 |
| `type`、スペック項目、`status`、日時 | 既存定義 | 本機能では変更しない |

## Relationships

- `PC.ownerId` は `Users.userId` を参照する論理的な所有者関係。
- PC登録時は、`ownerId` がUsersに存在することを登録前に確認する。
- 仕様にある「利用できなくなったユーザー」の具体的な属性は一次モデルに未定義。`isActive` 等を推測して追加しない。

## Validation Rules

1. 管理者の代理登録では `ownerId` 必須。
2. `ownerId` は候補一覧の一意な `userId` でなければならない。
3. Users取得中、取得失敗、0件、または登録直前の所有者検証失敗時はPCを保存しない。
4. 一般ユーザーは他ユーザーの `ownerId` を選択できない。
5. PCの `type`、スペック、管理番号、既存statusのルールは `001-pc-management` の定義をそのまま適用する。