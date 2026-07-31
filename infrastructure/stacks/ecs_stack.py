import os
from aws_cdk import (
    Stack,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_secretsmanager as secretsmanager,
    Duration,
)
from constructs import Construct

class EcsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, 
                 pcs_table=None, pc_usage_histories_table=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPCの作成
        vpc = ec2.Vpc(
            self, "PCManagementVPC",
            cidr="10.0.0.0/16",
            max_azs=2,
            nat_gateways=1,
        )

        # Gemini API キーのシークレット参照
        # 事前に AWS Secrets Manager に 'GeminiApiKey' という名前で登録されている想定
        gemini_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "GeminiApiKeySecret", "GeminiApiKey"
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

        # コンテナ定義の追加
        # プロジェクトルートからのパスを解決
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ecs_src_dir = os.path.join(base_dir, "backend", "ecs")

        container = task_definition.add_container(
            "PCManagementContainer",
            image=ecs.ContainerImage.from_asset(ecs_src_dir),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="PCManagement"),
            environment={
                "PCS_TABLE_NAME": pcs_table.table_name if pcs_table else "PCs",
                "USAGE_HISTORY_TABLE_NAME": pc_usage_histories_table.table_name if pc_usage_histories_table else "PCUsageHistories",
            },
            secrets={
                "GEMINI_API_KEY": ecs.Secret.from_secrets_manager(gemini_secret, "GeminiApiKey")
            }
        )

        container.add_port_mappings(
            ecs.PortMapping(container_port=80, host_port=80)
        )

        # ECSサービスの作成
        service = ecs.FargateService(
            self, "PCManagementService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            service_name="PCManagementService",
            assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )

        # HTTPポート(80)へのアクセスを許可
        service.connections.allow_from_any_ipv4(
            ec2.Port.tcp(80),
            "Allow HTTP access from anywhere for Lambda Proxy forwarding"
        )

        # Lambda関数用のIAMロールを作成
        ecs_role = iam.Role(
            self, "ECSExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for ECS tasks in PC Management Ledger",
        )

        # DynamoDBへのアクセス権限を追加
        if pcs_table:
            pcs_table.grant_read_write_data(task_definition.task_role)
        if pc_usage_histories_table:
            pc_usage_histories_table.grant_read_write_data(task_definition.task_role)

