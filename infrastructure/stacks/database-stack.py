from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
)
from constructs import Construct

class DatabaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDBテーブルの作成
        users_table = dynamodb.Table(
            self, "Users",
            table_name="Users",
            partition_key=dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        pcs_table = dynamodb.Table(
            self, "PCs",
            table_name="PCs",
            partition_key=dynamodb.Attribute(
                name="pcId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        return_records_table = dynamodb.Table(
            self, "ReturnRecords",
            table_name="ReturnRecords",
            partition_key=dynamodb.Attribute(
                name="recordId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        pc_usage_histories_table = dynamodb.Table(
            self, "PCUsageHistories",
            table_name="PCUsageHistories",
            partition_key=dynamodb.Attribute(
                name="historyId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        # テーブルARNを出力
        # これにより、lambda-stack.pyで使用できるようになります