#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infrastructure.infrastructure_stack import InfrastructureStack
from stacks.database_stack import DatabaseStack
from stacks.lambda_stack import LambdaStack
from stacks.ecs_stack import EcsStack


app = cdk.App()

# 1. データベーススタック
database_stack = DatabaseStack(app, "DatabaseStack")

# 2. Lambdaスタック (認証・管理用)
lambda_stack = LambdaStack(
    app, "LambdaStack",
    users_table=database_stack.users_table,
    pcs_table=database_stack.pcs_table,
    return_records_table=database_stack.return_records_table,
    pc_usage_histories_table=database_stack.pc_usage_histories_table
)

# 3. ECSスタック (スペック抽出・バッチ用)
ecs_stack = EcsStack(
    app, "EcsStack",
    pcs_table=database_stack.pcs_table,
    pc_usage_histories_table=database_stack.pc_usage_histories_table
)

app.synth()
