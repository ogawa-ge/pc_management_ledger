import aws_cdk as cdk
from aws_cdk import assertions

from stacks.database_stack import DatabaseStack
from stacks.lambda_stack import LambdaStack


def test_timeout_check_runs_every_fifteen_minutes_with_runtime_configuration():
    app = cdk.App()
    database = DatabaseStack(app, "DatabaseStack")
    stack = LambdaStack(
        app,
        "LambdaStack",
        users_table=database.users_table,
        pcs_table=database.pcs_table,
        return_records_table=database.return_records_table,
        pc_usage_histories_table=database.pc_usage_histories_table,
        system_activity_table=database.system_activity_table,
    )
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::Events::Rule",
        {"ScheduleExpression": "rate(15 minutes)", "State": "ENABLED"},
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "src.services.ecs_manager.lambda_handler_cloudwatch_timeout_check",
            "Environment": {
                "Variables": {
                    "ECS_CLUSTER_NAME": "PCManagementCluster",
                    "ECS_SERVICE_NAME": "PCManagementService",
                    "IDLE_TIMEOUT_SECONDS": "7200",
                }
            },
        },
    )