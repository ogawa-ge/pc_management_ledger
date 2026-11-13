# Feature Specification: Google Search Console 所有権確認対応（セーフブラウジング誤検知対策）

**Feature Branch**: `006-google-site-verification`

**Created**: 2026-11-12

**Status**: Completed

**Input**: User description: "Googleセーフブラウジング誤検知（赤画面）対策としてSearch Console所有権確認用HTML追加と認証リダイレクト除外設定"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Google Search Console によるサイト所有権確認 (Priority: P1)

システム管理者が Google セーフ ブラウジングの誤検知（赤画面警告）解除申請を行うため、Google Search Console の確認クローラーが未ログイン状態でも所有権確認用 HTML ファイルを取得し、所有権確認を完了できるようにする。

**Why this priority**: サイト所有権確認が完了しないと Google セーフ ブラウジングの審査リクエストを送信できず、社員がログインする際に赤画面警告が表示され続けるため。

**Independent Test**: 未ログイン（シークレットウィンドウ等）の状態で `/google6f17d6e6785211dc.html` にアクセスし、ログイン画面へリダイレクトされずに確認用文字列が表示されることで検証可能。

**Acceptance Scenarios**:

1. **Given** 未ログイン状態（認証セッションなし）、**When** `/google6f17d6e6785211dc.html` にアクセスする、**Then** `/login` へリダイレクトされず `google-site-verification: google6f17d6e6785211dc.html` が返却される。
2. **Given** 未ログイン状態（認証セッションなし）、**When** 通常の業務画面（`/pcs` 等）にアクセスする、**Then** 従来通り `/login` へリダイレクトされる。

---

### Edge Cases

- 未ログイン状態で `/robots.txt` や他の `google*.html` 確認ファイルパスにアクセスした場合も、認証リダイレクトの対象外として直接応答されること。
- 業務画面（`/pcs` 等）の未認証保護には一切影響を与えないこと。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: システムは、ルートパス直下（`/google6f17d6e6785211dc.html`）にて所有権確認用コンテンツ（`google-site-verification: google6f17d6e6785211dc.html`）を配信しなければならない。
- **FR-002**: システムは、未認証状態での所有権確認用ファイル（`/google*.html`）および `/robots.txt` へのアクセスをログイン画面へのリダイレクト対象から除外しなければならない。
- **FR-003**: システムは、除外対象パス以外の保護対象画面への未認証アクセスを引き続きログイン画面（`/login`）へリダイレクトしなければならない。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 未認証状態で `/google6f17d6e6785211dc.html` へアクセスした際、100% の確率でリダイレクトなし（HTTP 200）で確認用コンテンツが返却される。
- **SC-002**: Google Search Console の「所有権の確認（HTML ファイル）」を実行し、1回の試行で所有権確認が成功する。

## Assumptions

- Google Search Console の URL プレフィックスプロパティ向けに発行された確認ファイル名は `google6f17d6e6785211dc.html` である。
- 所有権確認完了後の「審査をリクエスト」送信操作自体は Google Search Console 管理画面上で実施する。
