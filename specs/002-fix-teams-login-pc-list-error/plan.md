# Implementation Plan: Fix Teams Login PC List Fetch Error

**Branch**: `002-fix-teams-login-pc-list-error` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-fix-teams-login-pc-list-error/spec.md`

## Summary

Teams（Azure AD）認証ログイン直後に、バックエンドのECSサーバーが起動待機（Cold Start）状態であるために発生する HTTP 503 エラーを起因とした「`Failed to fetch PC list`」の画面クラッシュを解消します。
フロントエンド（Next.js）の `frontend/src/app/pcs/page.tsx` において、503エラー時には自動リトライ（ポーリング）を行うロジックと、その他のエラー発生時に手動で再取得ができる「再試行」ボタンを実装します。

※ **Issue #11 に関連する未登録ユーザーの自動登録処理等は一切含みません（スコープ外）**。

## Technical Context

**Language/Version**: TypeScript, React (Next.js)
**Target File**: `frontend/src/app/pcs/page.tsx`
**Dependencies**: SWR (データフェッチング - 既存利用の場合) または標準の `fetch` API
**Constraints**: 
- 他ブランチ（Issue #11等）とのコンフリクトを回避するため、`page.tsx` のみ最小限の変更に留める。
- バックエンド（Lambda/ECS/DynamoDB）のコードは一切変更しない。

## Implementation Details

### 1. 503 Error Handling & Polling (FR-001)
- `frontend/src/app/pcs/page.tsx` 内のデータフェッチ処理に、ステータスコードを判定するロジックを追加。
- HTTP 503 の場合、`throw new Error` せずに「再試行待機状態」へ遷移させる。
- 5秒間隔で最大3回の `setTimeout` による自動リトライを実行する。
- 待機中は、UI上に Tailwind CSS のアニメーションを利用したスピナー（`animate-spin`）と、「サーバー起動中...」のメッセージを表示する。

### 2. Manual Retry Button & Error Messaging (FR-002, FR-003)
- 500, 502, 401, 403 などのエラー、または自動リトライの上限（15秒経過）に達した場合は、エラーメッセージステートを更新する。
- 画面に「PC一覧の取得に失敗しました。サーバーに一時的に接続できません。」等の日本語メッセージを表示する。
- その下に `onClick` イベントで再度フェッチ関数を単発で呼び出す「再試行」ボタン（`button` タグ、Tailwindスタイル適用）を配置する。

## Constitution Check

*GATE: Must pass before execution.*

- [x] **Layer 1 (Global Directives)**: 日本語出力、スキーマ推測なし（既存のAPI仕様に準拠）。
- [x] **Layer 2 (Project Mission)**: ユーザーのUX向上（朝イチのエラー画面回避）。
- [x] **Layer 3 (Engineering Policies)**: `kebab-case` の維持、クリーンなコード。
- [x] **Layer 4 (Documentation Workflow)**: Issue単位（`002-fix-teams-login-pc-list-error`）でのドキュメント管理を徹底。他Issue（#11）のスコープ外コードには触れない（Strict Scope Boundaries）。
