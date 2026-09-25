# Ubiquitous Language (ユビキタス言語)

本ドキュメントは、PC Management Ledger プロジェクトにおける共通言語（ユビキタス言語）を定義します。
開発者、AIアシスタント、およびステークホルダー間の認識のズレを防ぐため、コード内の命名（変数名、カラム名、ファイル名など）やドキュメントでは、必ず以下の定義に従ってください。

## 1. ユーザー・権限関連 (User & Role)

| 用語 (English) | 日本語訳 | 定義・説明 | 備考・関連データ |
| :--- | :--- | :--- | :--- |
| **User** | ユーザー | システムを利用する人物。Microsoftアカウントでログインする。 | `Users` テーブル |
| **Admin** | 管理者 | システムの全機能（全PCの閲覧、代理登録、廃棄済みへのステータス変更など）を利用できる権限。 | `role` カラムの値 |
| **General User** | 一般ユーザー | 自身のPCの登録・返却、およびPC一覧の閲覧ができる権限。 | `role` カラムの値 (`User`) |
| **Owner** | オーナー | PCの所有者として紐付けられるUser。管理者による代理登録では、オーナー候補から明示的に選択する。 | `PC.ownerId` が参照するUser |
| **Owner ID** | オーナーID | PCとOwnerを紐付けるUserの一意な識別子。画面表示名ではなく、この値を登録APIへ送信する。 | `ownerId` / `User.userId` |
| **Owner Candidate** | オーナー候補 | 管理者がPCの代理登録時に選択できる、Usersに登録済みのUser。 | `GET /api/users` の返却対象 |
| **Available User** | 利用可能なユーザー | PC登録時の再確認においてUsersに存在するOwner Candidate。未定義の有効・無効属性は推測せず、削除済みまたは存在しないUserは含めない。 | Owner検証時のUser存在確認 |

## 2. PC・デバイス関連 (PC & Device)

| 用語 (English) | 日本語訳 | 定義・説明 | 備考・関連データ |
| :--- | :--- | :--- | :--- |
| **PC** | PC | 管理対象となるパーソナルコンピュータ。 | `PCs` テーブル |
| **Management Number** | 管理番号 | PCを一意に識別するための番号。自動採番される。 | `pcId` カラム。例: `N-001`, `D-001` |
| **Notebook** | ノートパソコン | 持ち運び可能なPC。管理番号は `N-` から始まる。 | `type` カラムの値 |
| **Desktop** | デスクトップパソコン | 据え置き型のPC。管理番号は `D-` から始まる。 | `type` カラムの値 |
| **Specs** | スペック情報 | PCのハードウェアおよびソフトウェアの構成情報。 | CPU, Memory, Storage, OS, Manufacturer, Model |

## 3. ステータス関連 (Status)

PCの現在の状態を表します。（`status` カラムの値）

| 用語 (English) | 日本語訳 | 定義・説明 |
| :--- | :--- | :--- |
| **InUse** | 利用中 | ユーザーに割り当てられており、現在使用されている状態。 |
| **Unused** | 未使用 | 誰にも割り当てられておらず、利用可能な状態。 |
| **PendingDisposal** | 廃棄待ち | 故障等により使用できず、社内で廃棄を待っている状態。 |
| **Disposed** | 廃棄済み | すでに処分され、社内からなくなった状態（管理台帳には履歴として残る）。 |

## 4. 履歴・記録関連 (History & Record)

| 用語 (English) | 日本語訳 | 定義・説明 | 備考・関連データ |
| :--- | :--- | :--- | :--- |
| **Return Record** | 返却記録 | ユーザーがPCを返却した際の記録。 | `ReturnRecords` テーブル |
| **Condition** | PCの状態 | 返却時のPCの物理的・ソフトウェア的な状態（例: 初期化済み、故障など）。 | `condition` カラム |
| **Reason** | 返却理由 | PCを返却する理由。 | `reason` カラム |
| **PC Usage History** | PC利用履歴 | 1台のPCが過去にいつ、誰に、どのようなステータスで利用されていたかの履歴。 | `PCUsageHistories` テーブル |

## 5. システム・外部連携関連 (System & Integration)

| 用語 (English) | 日本語訳 | 定義・説明 |
| :--- | :--- | :--- |
| **Gemini API** | Gemini API | ターミナルから取得した非構造化テキストデータから、必要なスペック情報のみを抽出・整形するために利用するAIサービス。 |
| **Terminal** | ターミナル | ユーザーがPCのスペック情報を取得するためのコマンドを実行するインターフェース。 |
| **Proxy Registration** | 代理登録 | 管理者が特定のユーザーを指定して、そのユーザーの代わりにPCを登録すること。 |

## 6. ECSランタイム制御・安全性関連 (Runtime Control & Safety)

| 用語 (English) | 日本語訳 | 定義・説明 | コード表記 |
| :--- | :--- | :--- | :--- |
| **Backend Runtime State** | バックエンド稼働状態 | ECSバックエンドの停止中、起動中、稼働中、停止処理中、起動失敗を区別する状態。DynamoDB上の状態だけでなくECSの実状態と照合して扱う。 | `runtimeState`: `STOPPED`, `STARTING`, `RUNNING`, `STOPPING`, `START_FAILED` |
| **Start Lock** | 起動ロック | 同時に到着した起動要求のうち、1要求だけへECSの稼働数更新権を与える期限付きの排他情報。取得できない要求は起動失敗ではなく進行中の状態を共有する。 | `startOwnerRequestId`, `startLockExpiresAt`, `startRequestedAt` |
| **Idempotency Key** | 冪等キー | 利用者の1回の状態変更操作を再送間で識別し、同じ内容を一度だけ成立させるUUID形式の値。異なる内容での再利用は競合として拒否する。 | HTTP `Idempotency-Key`, `request#{idempotencyKey}` |
| **In-flight Operation** | 処理中操作 | LambdaがECSへ転送を開始し、成功・失敗・例外のいずれでも終了していない操作。1件以上存在する間は自動停止しない。 | `inFlightCount` |
| **Runtime Generation** | 稼働世代 | 起動・停止と新規操作の競合を検出する単調増加番号。停止処理後に世代が変化していれば、新しい操作を優先して再起動する。 | `generation` |
| **Internal Request Signature** | 内部要求署名 | Lambdaから公開IPのECSへ転送する要求について、メソッド、正規化URL、本文、要求ID、冪等キー、送信時刻、秘密世代をHMAC-SHA256で保護する署名。利用者認証・認可を代替しない。 | `X-Internal-Signature` および関連する `X-Internal-*` ヘッダー |
| **Secret Generation** | 秘密世代 | 内部要求署名用共有秘密のローテーション単位。Lambdaは現行1世代で署名し、ECSは移行中だけ現行・次期の最大2世代を検証する。 | `keyId`, `current`, `next` |

---
※ 新しい用語や概念が登場した場合は、実装前に必ずこのドキュメントを更新し、チーム全体（AI含む）で認識を同期させてください。
