import aws_cdk as cdk
from aws_cdk import assertions

from stacks.lambda_stack import LambdaStack


def test_api_and_timeout_check_use_python_3_12():
    app = cdk.App()
    stack = LambdaStack(app, "LambdaStack")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::Lambda::Function", 2)
    for handler in (
        "src.main.lambda_handler",
        "src.services.ecs_manager.lambda_handler_cloudwatch_timeout_check",
    ):
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {"Handler": handler, "Runtime": "python3.12"},
        )