import aws_cdk as cdk
from aws_cdk import assertions

from stacks.database_stack import DatabaseStack
from stacks.ecs_stack import EcsStack
from stacks.lambda_stack import LambdaStack


def _templates():
    app = cdk.App()
    database = DatabaseStack(app, "DatabaseStack")
    lambda_stack = LambdaStack(
        app,
        "LambdaStack",
        users_table=database.users_table,
        pcs_table=database.pcs_table,
        return_records_table=database.return_records_table,
        pc_usage_histories_table=database.pc_usage_histories_table,
        system_activity_table=database.system_activity_table,
    )
    ecs_stack = EcsStack(
        app,
        "EcsStack",
        pcs_table=database.pcs_table,
        return_records_table=database.return_records_table,
        pc_usage_histories_table=database.pc_usage_histories_table,
        system_activity_table=database.system_activity_table,
    )
    return (
        assertions.Template.from_stack(lambda_stack),
        assertions.Template.from_stack(ecs_stack),
    )


def test_lambda_and_ecs_reference_the_same_internal_proxy_secret_without_plaintext():
    lambda_template, ecs_template = _templates()
    lambda_json = lambda_template.to_json()
    ecs_json = ecs_template.to_json()

    assert "InternalProxySigningSecret" in str(lambda_json)
    assert "InternalProxySigningSecret" in str(ecs_json)
    assert "INTERNAL_PROXY_SECRET_ARN" in str(lambda_json)
    assert "INTERNAL_PROXY_SECRET_ARN" in str(ecs_json)
    assert "INTERNAL_PROXY_SECRET_VALUE" not in str(lambda_json)
    assert "INTERNAL_PROXY_SECRET_VALUE" not in str(ecs_json)


def test_execution_roles_only_receive_get_secret_value_for_internal_secret():
    lambda_template, ecs_template = _templates()
    combined = f"{lambda_template.to_json()} {ecs_template.to_json()}"

    assert "secretsmanager:GetSecretValue" in combined
    assert "secretsmanager:PutSecretValue" not in combined
    assert "secretsmanager:UpdateSecret" not in combined