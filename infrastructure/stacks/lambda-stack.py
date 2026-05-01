from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    Duration,
    aws_dynamodb as dynamodb,
)
from constructs import Construct

class LambdaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDBテーブルのARNを取得
        # 例: テーブル名を指定してARNを取得
        # ここでは、DatabaseStackで作成されたテーブルを参照
        # 実際には、DatabaseStackからARNを出力し、LambdaStackでそれを使用する必要がある

        # Lambda関数用のIAMロールを作成
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Lambda functions in PC Management Ledger",
        )

        # DynamoDBへのアクセス権限を追加
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                ],
                resources=[
                    # DynamoDBテーブルのARNを指定
                    # 例: "arn:aws:dynamodb:region:account:table/TableName"
                ]
            )
        )

        # Lambda関数を作成
        # 例: API Gatewayと連携するLambda関数
        api_lambda = _lambda.Function(
            self, "ApiLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="main.lambda_handler",
            code=_lambda.Code.from_asset("backend/lambda/src"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                # 環境変数を設定
                "DYNAMODB_TABLE_NAME": "PCs",  # 例
            }
        )