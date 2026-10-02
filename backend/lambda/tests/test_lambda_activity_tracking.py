import sys
from decimal import Decimal
from types import ModuleType
from unittest.mock import Mock

from fastapi.testclient import TestClient
from botocore.exceptions import ClientError


jose_module = ModuleType("jose")
jose_module.JWTError = Exception
jose_module.jwt = Mock()
sys.modules.setdefault("jose", jose_module)

import src.main as main


def conditional_failure():
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "condition"}},
        "UpdateItem",
    )


def configure_proxy(monkeypatch, status=200, raises=None):
    manager = Mock()
    manager.get_ecs_public_ip.return_value = "203.0.113.10"
    monkeypatch.setattr(main, "get_ecs_manager", lambda: manager)
    monkeypatch.setattr(main.InternalRequestSigner, "sign", lambda self, **kwargs: {})
    response = Mock(status=status, data=b"{}", headers={})
    http = Mock()
    if raises:
        http.request.side_effect = raises
    else:
        http.request.return_value = response
    monkeypatch.setattr(main.urllib3, "PoolManager", lambda: http)
    return manager


def test_successful_proxy_tracks_accept_in_flight_and_completion(monkeypatch):
    manager = configure_proxy(monkeypatch, status=200)

    response = TestClient(main.app).get("/api/pcs")

    assert response.status_code == 200
    manager.record_request_accepted.assert_called_once()
    manager.ensure_ecs_running.assert_called_once_with(
        request_id=manager.record_request_accepted.call_args.args[0]
    )
    manager.begin_in_flight.assert_called_once_with()
    manager.finish_in_flight.assert_called_once_with(succeeded=True)


def test_non_success_proxy_decrements_without_success_activity(monkeypatch):
    manager = configure_proxy(monkeypatch, status=409)

    response = TestClient(main.app).get("/api/pcs")

    assert response.status_code == 409
    manager.finish_in_flight.assert_called_once_with(succeeded=False)


def test_proxy_exception_still_decrements_in_flight(monkeypatch):
    manager = configure_proxy(monkeypatch, raises=RuntimeError("network unavailable"))

    response = TestClient(main.app).get("/api/pcs")

    assert response.status_code == 502
    manager.finish_in_flight.assert_called_once_with(succeeded=False)


def test_acceptance_updates_last_accepted_and_initializes_runtime(
    ecs_manager, lambda_aws_clients, fixed_now
):
    ecs_manager.clock = lambda: fixed_now
    table = lambda_aws_clients["system_activity_table"]
    table.update_item.side_effect = [{}, conditional_failure()]

    result = ecs_manager.record_request_accepted("request-1")

    assert result == {"stop_cancelled": False}
    initialization = table.update_item.call_args_list[0].kwargs
    assert "lastAcceptedAt=:now" in initialization["UpdateExpression"]
    assert "inFlightCount=if_not_exists(inFlightCount,:zero)" in initialization["UpdateExpression"]
    assert initialization["ExpressionAttributeValues"][":zero"] == Decimal(0)


def test_begin_in_flight_atomically_increments_counter(ecs_manager, lambda_aws_clients):
    table = lambda_aws_clients["system_activity_table"]

    ecs_manager.begin_in_flight()

    call = table.update_item.call_args.kwargs
    assert "inFlightCount=if_not_exists(inFlightCount,:zero)+:one" in call["UpdateExpression"]
    assert call["ExpressionAttributeValues"][":one"] == Decimal(1)


def test_finish_in_flight_updates_activity_only_for_success(
    ecs_manager, lambda_aws_clients, fixed_now
):
    ecs_manager.clock = lambda: fixed_now
    table = lambda_aws_clients["system_activity_table"]

    ecs_manager.finish_in_flight(succeeded=True)
    success_call = table.update_item.call_args.kwargs
    assert "inFlightCount=inFlightCount-:one" in success_call["UpdateExpression"]
    assert "lastActivityAt=:now" in success_call["UpdateExpression"]
    assert success_call["ConditionExpression"] == "inFlightCount > :zero"

    table.reset_mock()
    ecs_manager.finish_in_flight(succeeded=False)
    failure_call = table.update_item.call_args.kwargs
    assert "inFlightCount=inFlightCount-:one" in failure_call["UpdateExpression"]
    assert "lastActivityAt" not in failure_call["UpdateExpression"]