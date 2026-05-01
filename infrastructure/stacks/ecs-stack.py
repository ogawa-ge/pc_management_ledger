from aws_cdk import (
    Stack,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    Duration,
)
from constructs import Construct

class EcsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPCの作成
        vpc = ec2.Vpc(
            self, "PCManagementVPC",
            cidr="10.0.0.0/16",
            max_azs=2,
            nat_gateways=1,
        )

        # ECSクラスターの作成
        cluster = ecs.Cluster(
            self, "PCManagementCluster",
            cluster_name="PCManagementCluster",
            vpc=vpc,
        )

        # ECSタスク定義の作成
        task_definition = ecs.FargateTaskDefinition(
            self, "PCManagementTaskDefinition",
            memory_limit_mib=512,
            cpu=256,
        )

        # ECSサービスの作成
        service = ecs.FargateService(
            self, "PCManagementService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
        )

        # Lambda関数用のIAMロールを作成
        ecs_role = iam.Role(
            self, "ECSExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for ECS tasks in PC Management Ledger",
        )

        # DynamoDBへのアクセス権限を追加
        ecs_role.add_to_policy(
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

        # タスク定義にロールを追加
        task_definition.add_execution_role(ecs_role)
        task_definition.add_task_role(ecs_role)