# Data Model: AI抽出モデルの軽量モデルへの切り替え

**Feature**: [spec.md](./spec.md) | **Date**: 2026-11-25

本機能では、データモデルを変更しない。

- **PC エンティティ**: [001-pc-management/data-model.md](../001-pc-management/data-model.md) と [002-ai-pc-info-extraction/data-model.md](../002-ai-pc-info-extraction/data-model.md) の定義をそのまま使う。項目の追加・削除・型の変更はない。
- **AI抽出結果**（`POST /api/pcs/parse-specs` のレスポンス）: 項目（`cpu`, `memory`, `storage`, `os`, `manufacturer`, `model`, `gpu`, `pcName`）は変わらない。`memory` と `storage` は GB 単位・小数点第1位までの数値であり、1000単位・1024単位のどちらで換算されるかは AI に任せる（[research.md](./research.md) Decision 3）。
