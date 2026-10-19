from decimal import Decimal

from botocore.exceptions import ClientError


def conditional_failure():
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "condition"}},
        "UpdateItem",
    )


def test_new_generation_before_stop_ownership_cancels_stop(
    ecs_manager, lambda_aws_clients, fixed_now
):
    ecs_manager.clock = lambda: fixed_now
    ecs_manager.get_ecs_status = lambda: {"status": "active", "running_count": 1}
    table = lambda_aws_clients["system_activity_table"]
    table.get_item.return_value = {
        "Item": {
            "runtimeState": "RUNNING",
            "generation": Decimal(3),
            "inFlightCount": Decimal(0),
            "lastActivityAt": "2026-09-24T00:00:00+00:00",
        }
    }
    table.update_item.side_effect = conditional_failure()

    result = ecs_manager.check_and_auto_sleep(check_id="race-before-stop")

    assert result == {"status": "active", "reason": "stop_gate_changed"}
    lambda_aws_clients["ecs"].update_service.assert_not_called()


def test_new_generation_after_desired_zero_reapplies_desired_one(
    ecs_manager, lambda_aws_clients
):
    ecs = lambda_aws_clients["ecs"]
    table = lambda_aws_clients["system_activity_table"]
    ecs.update_service.side_effect = [
        {"service": {"serviceArn": "service/test"}},
        {"service": {"serviceArn": "service/test"}},
    ]
    table.get_item.return_value = {
        "Item": {"runtimeState": "STARTING", "generation": Decimal(8)}
    }

    result = ecs_manager.stop_ecs(reason="idle_timeout", expected_generation=7)

    assert result["status"] == "restart_requested"
    assert [call.kwargs["desiredCount"] for call in ecs.update_service.call_args_list] == [0, 1]