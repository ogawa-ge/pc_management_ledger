import aws_cdk as cdk
from aws_cdk import assertions

from stacks.database_stack import DatabaseStack


def test_system_activity_is_the_only_table_with_expires_at_ttl():
    app = cdk.App()
    stack = DatabaseStack(app, "DatabaseStack")
    template = assertions.Template.from_stack(stack)

    tables = template.find_resources("AWS::DynamoDB::Table")
    ttl_tables = [
        resource
        for resource in tables.values()
        if resource["Properties"].get("TimeToLiveSpecification")
    ]

    assert len(ttl_tables) == 1
    assert ttl_tables[0]["Properties"]["TableName"] == "SystemActivity"
    assert ttl_tables[0]["Properties"]["TimeToLiveSpecification"] == {
        "AttributeName": "expiresAt",
        "Enabled": True,
    }


def test_business_tables_do_not_gain_idempotency_attributes():
    app = cdk.App()
    stack = DatabaseStack(app, "DatabaseStack")
    template = assertions.Template.from_stack(stack)

    for resource in template.find_resources("AWS::DynamoDB::Table").values():
        attributes = resource["Properties"]["AttributeDefinitions"]
        assert all(
            attribute["AttributeName"] not in {"idempotencyKey", "expiresAt"}
            for attribute in attributes
        )
