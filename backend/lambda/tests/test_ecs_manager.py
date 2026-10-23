import threading
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError


def conditional_failure():
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "condition"}},
        "UpdateItem",
    )


def test_ten_concurrent_start_requests_update_service_once(ecs_manager, lambda_aws_clients):
    ecs = lambda_aws_clients["ecs"]
    table = lambda_aws_clients["system_activity_table"]
    ecs.describe_services.return_value = {
        "services": [{"desiredCount": 0, "runningCount": 0, "status": "ACTIVE"}]
    }
    ecs.update_service.return_value = {"service": {"serviceArn": "service/test"}}

    lock = threading.Lock()
    claimed = False

    def update_item(**kwargs):
        nonlocal claimed
        if "startLockExpiresAt" not in kwargs.get("UpdateExpression", ""):
            return {}
        with lock:
            if claimed:
                raise conditional_failure()
            claimed = True
            return {"Attributes": {"generation": Decimal(1)}}

    table.update_item.side_effect = update_item
    results = []

    def start(index):
        results.append(ecs_manager.ensure_ecs_running(request_id=f"request-{index}"))

    threads = [threading.Thread(target=start, args=(index,)) for index in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert ecs.update_service.call_count == 1
    assert sum(result["status"] == "started" for result in results) == 1
    assert all(result["status"] in {"started", "starting", "already_running"} for result in results)


def test_expired_start_lock_can_be_reclaimed(ecs_manager, lambda_aws_clients):
    ecs = lambda_aws_clients["ecs"]
    table = lambda_aws_clients["system_activity_table"]
    ecs.describe_services.return_value = {
        "services": [{"desiredCount": 1, "runningCount": 0, "status": "ACTIVE"}]
    }
    ecs.update_service.return_value = {"service": {"serviceArn": "service/test"}}
    table.update_item.return_value = {"Attributes": {"generation": Decimal(4)}}

    result = ecs_manager.ensure_ecs_running(request_id="new-owner")

    assert result["status"] == "started"
    claim = table.update_item.call_args_list[0].kwargs
    assert "startLockExpiresAt <= :nowEpoch" in claim["ConditionExpression"]
    assert claim["ExpressionAttributeValues"][":owner"] == "new-owner"
    assert result["generation"] == 4


def test_stop_cancelling_request_uses_its_existing_start_ownership(
    ecs_manager, lambda_aws_clients
):
    ecs = lambda_aws_clients["ecs"]
    table = lambda_aws_clients["system_activity_table"]
    ecs.describe_services.return_value = {
        "services": [{"desiredCount": 0, "runningCount": 1, "status": "ACTIVE"}]
    }
    ecs.update_service.return_value = {"service": {"serviceArn": "service/test"}}
    table.get_item.return_value = {
        "Item": {
            "runtimeState": "STARTING",
            "generation": Decimal(9),
            "startOwnerRequestId": "operation-9",
        }
    }

    result = ecs_manager.ensure_ecs_running(request_id="operation-9")

    assert result["status"] == "started"
    assert result["generation"] == 9
    ecs.update_service.assert_called_once_with(
        cluster="test-cluster", service="PCManagementService", desiredCount=1
    )


def test_start_outcome_rejects_old_owner(ecs_manager, lambda_aws_clients):
    table = lambda_aws_clients["system_activity_table"]
    table.update_item.side_effect = conditional_failure()

    updated = ecs_manager._mark_start_outcome("old-owner", 1, "START_FAILED", "TEST")

    assert updated is False
    call = table.update_item.call_args.kwargs
    assert "startOwnerRequestId=:owner" in call["ConditionExpression"]
    assert "generation=:generation" in call["ConditionExpression"]


def test_ready_reconciliation_uses_current_owner_and_generation(
    ecs_manager, lambda_aws_clients
):
    table = lambda_aws_clients["system_activity_table"]
    table.get_item.return_value = {
        "Item": {
            "runtimeState": "STARTING",
            "generation": Decimal(5),
            "startOwnerRequestId": "current-owner",
        }
    }
    table.update_item.return_value = {}

    ecs_manager._mark_runtime_running()

    call = table.update_item.call_args.kwargs
    assert call["ExpressionAttributeValues"][":owner"] == "current-owner"
    assert call["ExpressionAttributeValues"][":generation"] == Decimal(5)
    assert call["ExpressionAttributeValues"][":state"] == "RUNNING"


@pytest.mark.parametrize(
    ("activity_delta", "in_flight", "expected_status"),
    [
        (timedelta(hours=1, minutes=59, seconds=59), 0, "active"),
        (timedelta(hours=2), 0, "auto_slept"),
        (timedelta(hours=3), 1, "active"),
    ],
)
def test_idle_boundary_and_in_flight_gate(
    ecs_manager, lambda_aws_clients, fixed_now, activity_delta, in_flight, expected_status
):
    ecs_manager.clock = lambda: fixed_now
    ecs_manager.get_ecs_status = Mock(return_value={"status": "active", "running_count": 1})
    ecs_manager.stop_ecs = Mock(return_value={"status": "stopped"})
    table = lambda_aws_clients["system_activity_table"]
    table.get_item.return_value = {
        "Item": {
            "runtimeState": "RUNNING",
            "generation": Decimal(2),
            "inFlightCount": Decimal(in_flight),
            "lastActivityAt": (fixed_now - activity_delta).isoformat(),
        }
    }
    table.update_item.return_value = {}

    result = ecs_manager.check_and_auto_sleep(check_id="check-1")

    assert result["status"] == expected_status
    if expected_status == "auto_slept":
        ecs_manager.stop_ecs.assert_called_once_with(reason="idle_timeout", expected_generation=2)
    else:
        ecs_manager.stop_ecs.assert_not_called()


@pytest.mark.parametrize(
    "item",
    [
        {"runtimeState": "RUNNING", "generation": Decimal(1), "lastActivityAt": "2026-09-29T00:00:00+00:00"},
        {"runtimeState": "RUNNING", "generation": Decimal(1), "inFlightCount": Decimal(-1), "lastActivityAt": "2026-09-29T00:00:00+00:00"},
        {"runtimeState": "RUNNING", "generation": Decimal(1), "inFlightCount": Decimal(0)},
        {"runtimeState": "RUNNING", "generation": Decimal(1), "inFlightCount": Decimal(0), "lastActivityAt": "invalid"},
        {"runtimeState": "RUNNING", "generation": Decimal(1), "inFlightCount": Decimal(0), "lastActivityAt": "2026-09-26T00:00:01+00:00"},
    ],
)
def test_invalid_runtime_activity_fails_open(
    ecs_manager, lambda_aws_clients, fixed_now, item, caplog
):
    ecs_manager.clock = lambda: fixed_now
    ecs_manager.get_ecs_status = Mock(return_value={"status": "active", "running_count": 1})
    lambda_aws_clients["system_activity_table"].get_item.return_value = {"Item": item}

    result = ecs_manager.check_and_auto_sleep(check_id="invalid-check")

    assert result["status"] == "skip"
    assert result["reason"] == "invalid_runtime_activity"
    assert "invalid_runtime_activity" in caplog.text