import aws_cdk as cdk
from aws_cdk import assertions

from stacks.database_stack import DatabaseStack
from stacks.ecs_stack import EcsStack


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


def test_ecs_task_role_has_read_only_access_to_users_table():
    app = cdk.App()
    database = DatabaseStack(app, "DatabaseStack")
    ecs_stack = EcsStack(
        app,
        "EcsStack",
        users_table=database.users_table,
        pcs_table=database.pcs_table,
        return_records_table=database.return_records_table,
        pc_usage_histories_table=database.pc_usage_histories_table,
        system_activity_table=database.system_activity_table,
    )
    template_json = assertions.Template.from_stack(ecs_stack).to_json()

    users_statements = []
    for resource in template_json["Resources"].values():
        if resource.get("Type") != "AWS::IAM::Policy":
            continue
        for statement in resource["Properties"]["PolicyDocument"].get("Statement", []):
            raw_resources = statement.get("Resource", [])
            res_list = raw_resources if isinstance(raw_resources, list) else [raw_resources]
            if any("Users" in str(res) for res in res_list):
                users_statements.append(statement)

    assert len(users_statements) >= 1

    granted_actions = set()
    for statement in users_statements:
        raw_actions = statement.get("Action", [])
        act_list = raw_actions if isinstance(raw_actions, list) else [raw_actions]
        granted_actions.update(act_list)

    assert "dynamodb:GetItem" in granted_actions
    assert "dynamodb:Scan" in granted_actions
    for write_action in (
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:BatchWriteItem",
    ):
        assert write_action not in granted_actions

    for resource in template_json["Resources"].values():
        if resource.get("Type") != "AWS::ECS::TaskDefinition":
            continue
        for container in resource["Properties"].get("ContainerDefinitions", []):
            env_names = {item["Name"] for item in container.get("Environment", [])}
            assert "USERS_TABLE_NAME" not in env_names
