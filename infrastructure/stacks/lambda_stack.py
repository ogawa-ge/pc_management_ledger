import os
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    Duration,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
)
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
        lambda_src_dir = os.path.join(base_dir, "backend", "lambda", "src")

        api_lambda = _lambda.Function(
            self, "ApiLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="main.lambda_handler",
            code=_lambda.Code.from_asset(lambda_src_dir),
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
