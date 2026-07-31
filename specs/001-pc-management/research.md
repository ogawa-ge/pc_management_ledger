# Phase 0: Research & Decisions

## 1. ECSへの直接接続（ALB非利用）

**Decision**: ALBを使用せず、AWS Cloud Map (Service Discovery) と API Gateway (HTTP API) などを組み合わせるか、あるいはECSタスクのパブリックIPをLambda経由で取得してフロントエンドに返す方式を採用する。よりシンプルでコストを抑えるため、LambdaからECSタスクのパブリックIPを取得し、フロントエンドが直接通信する方式を第一候補とする。

**Rationale**: ALBは固定費（月額約2000円強）がかかり、月間数百円〜数千円以内というコスト要件を満たすのが難しいため。

**Alternatives considered**:
- API Gateway (HTTP API) + VPC Link + Cloud Map: ALBよりは安価だが、VPC Linkのコストや設定の複雑さがある。
- Lambda Function URLのみで構成: メモリ/CPUを要する処理や長時間実行に不向きなため、ECSとのハイブリッド構成が要件となっている。

## 2. Gemini APIによるスペック情報の抽出

**Decision**: ユーザーのローカルPCから取得したスペック情報（テキストデータ）をGemini APIに送信し、JSON形式（CPU、メモリ容量、ストレージ容量、OSバージョン、メーカー名、モデル名）で構造化して返却させるプロンプトを実装する。

**Rationale**: ターミナルからの出力結果はOSや環境によってフォーマットが異なるため、LLMを用いて柔軟にパースし、統一されたフォーマットに変換するのが最も確実かつ実装コストが低いため。

**Alternatives considered**:
- 正規表現や専用のパーサーの実装: OSごとの出力フォーマットの違いを網羅するのが困難であり、メンテナンスコストが高い。

## 3. Microsoftアカウントでのログイン (SSO)

**Decision**: Next.jsのフロントエンドで `next-auth` (Auth.js) を利用し、Azure AD (Microsoft Entra ID) プロバイダーを設定してログインを実装する。取得したトークン（またはユーザー情報）をLambdaに送信し、DynamoDBの権限テーブルと照合してアクセス制御を行う。
認証は特定のテナント（`***AZURE_AD_TENANT_NAME_MASKED***`、テナントID: `***AZURE_AD_TENANT_ID_MASKED***`）のみを許可するように設定し、クライアントIDとして `***AZURE_AD_CLIENT_ID_MASKED***` を使用する。

**Rationale**: Next.jsエコシステムで標準的かつ実績のある `next-auth` を利用することで、セキュアかつ容易にMicrosoftアカウント連携を実装できるため。

**Alternatives considered**:
- AWS Cognitoの利用: CognitoのユーザープールとAzure ADを連携させることも可能だが、小規模かつシンプルな構成を目指すため、フロントエンドで直接認証を処理する方式を選択。
