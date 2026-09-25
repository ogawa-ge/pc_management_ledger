import aws_cdk as cdk
from aws_cdk import assertions

from stacks.database_stack import DatabaseStack
from stacks.ecs_stack import EcsStack


def _template():
    app = cdk.App()
    database = DatabaseStack(app, "DatabaseStack")
    stack = EcsStack(
        app,
        "EcsStack",
        pcs_table=database.pcs_table,
        return_records_table=database.return_records_table,
        pc_usage_histories_table=database.pc_usage_histories_table,
        system_activity_table=database.system_activity_table,
    )
    return assertions.Template.from_stack(stack)


def test_idle_cost_resources_are_not_provisioned():
    template = _template()
    template.resource_count_is("AWS::EC2::NatGateway", 0)
    template.resource_count_is("AWS::ElasticLoadBalancingV2::LoadBalancer", 0)
    template.has_resource_properties("AWS::ECS::Service", {"DesiredCount": 0})


def test_fargate_service_keeps_public_network_egress():
    template = _template()
    template.has_resource_properties(
        "AWS::ECS::Service",
        {
            "NetworkConfiguration": {
                "AwsvpcConfiguration": {
                    "AssignPublicIp": "ENABLED",
                }
            }
        },
    )