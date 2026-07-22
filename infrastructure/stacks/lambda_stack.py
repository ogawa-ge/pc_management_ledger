import os
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    Duration,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    CfnOutput,
)
import aws_cdk.aws_lambda_python_alpha as lambda_python
from constructs import Construct

class LambdaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, 
                 users_table=None, pcs_table=None, return_records_table=None, 
                 pc_usage_histories_table=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Azure AD シークレットの参照
        # 事前に AWS Secrets Manager に 'AzureAdSecrets' という名前で登録されている想定
        azure_ad_secrets = secretsmanager.Secret.from_secret_name_v2(
            self, "AzureAdSecrets", "AzureAdSecrets"
        )

        # Lambda関数を作成
        # プロジェクトルートからのパスを解決
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        lambda_src_dir = os.path.join(base_dir, "backend", "lambda")

        api_lambda = lambda_python.PythonFunction(
            self, "ApiLambda",
            entry=lambda_src_dir,  # lambda フォルダを指定。直下に requirements.txt がある
            index="src/main.py",   # エントリポイントのファイル
            handler="lambda_handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(30),
            environment={
                "USERS_TABLE_NAME": users_table.table_name if users_table else "Users",
                "PCS_TABLE_NAME": pcs_table.table_name if pcs_table else "PCs",
                "AZURE_AD_SECRET_NAME": "AzureAdSecrets",
            }
        )

        # シークレットへの読み取り権限を追加
        azure_ad_secrets.grant_read(api_lambda)

        # DynamoDBへのアクセス権限を追加
        if users_table:
            users_table.grant_read_write_data(api_lambda)
        if pcs_table:
            pcs_table.grant_read_write_data(api_lambda)
        if return_records_table:
            return_records_table.grant_read_write_data(api_lambda)
        if pc_usage_histories_table:
            pc_usage_histories_table.grant_read_write_data(api_lambda)

        # ECS 起動・停止および ENI 情報取得のための IAM 権限を追加
        api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:ListTasks",
                    "ecs:DescribeTasks",
                    "ecs:DescribeServices",
                    "ecs:UpdateService",
                ],
                resources=["*"]
            )
        )

        api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:DescribeNetworkInterfaces",
                ],
                resources=["*"]
            )
        )

        api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:DescribeLogGroups",
                ],
                resources=["*"]
            )
        )

        # API Gateway (HTTP API) の作成
        http_api = apigwv2.HttpApi(
            self, "HttpApi",
            api_name="PCManagementHttpApi",
            description="HTTP API Gateway for Lambda FastAPI Integration"
        )

        # Lambda 統合の定義
        lambda_integration = apigwv2_integrations.HttpLambdaIntegration(
            "LambdaIntegration",
            handler=api_lambda
        )

        # デフォルトルート（すべてのパスとメソッド）を Lambda 統合へ向ける
        http_api.add_routes(
            path="/{proxy+}",
            methods=[apigwv2.HttpMethod.ANY],
            integration=lambda_integration
        )

        # API のベースパス（/）も Lambda 統合へ向ける（ヘルスチェックやルート用）
        http_api.add_routes(
            path="/",
            methods=[apigwv2.HttpMethod.ANY],
            integration=lambda_integration
        )

        # デプロイ後にAPIのパブリックURLを出力する
        CfnOutput(
            self, "ApiUrl",
            value=http_api.api_endpoint,
            description="The URL of the API Gateway",
            export_name="PCManagementApiUrl"
        )

