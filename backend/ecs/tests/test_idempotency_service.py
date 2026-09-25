from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from src.services.idempotency_service import IdempotencyService


NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


def _service(item=None):
    table = Mock()
    table.get_item.return_value = {"Item": item} if item else {}
    return IdempotencyService(table=table, clock=lambda: NOW), table


def test_new_request_is_claimed():
    service, table = _service()
    decision = service.claim("key", "fp", "PC_REGISTER", "owner")
    assert decision.action == "EXECUTE"
    table.put_item.assert_called_once()


def test_processing_conflict_and_replay_boundaries():
    service, _ = _service({
        "requestFingerprint": "fp",
        "status": "PROCESSING",
        "ownerRequestId": "old",
        "startedAt": (NOW - timedelta(minutes=4, seconds=59)).isoformat(),
    })
    assert service.claim("key", "fp", "PC_REGISTER", "new").action == "PROCESSING"

    service, table = _service({
        "requestFingerprint": "fp",
        "status": "PROCESSING",
        "ownerRequestId": "old",
        "startedAt": (NOW - timedelta(minutes=5)).isoformat(),
    })
    assert service.claim("key", "fp", "PC_REGISTER", "new").action == "EXECUTE"
    table.update_item.assert_called_once()

    service, _ = _service({
        "requestFingerprint": "other",
        "status": "SUCCEEDED",
        "expiresAt": int((NOW + timedelta(days=1)).timestamp()),
    })
    assert service.claim("key", "fp", "PC_REGISTER", "new").action == "CONFLICT"


def test_success_is_replayed_until_seven_day_expiry_then_reclaimed():
    service, _ = _service({
        "requestFingerprint": "fp",
        "status": "SUCCEEDED",
        "expiresAt": int((NOW + timedelta(seconds=1)).timestamp()),
        "responseStatus": 201,
        "responseBody": '{"pcId":"N-001"}',
    })
    decision = service.claim("key", "fp", "PC_REGISTER", "new")
    assert decision.action == "REPLAY"
    assert decision.response_status == 201

    service, table = _service({
        "requestFingerprint": "fp",
        "status": "SUCCEEDED",
        "expiresAt": int(NOW.timestamp()),
    })
    assert service.claim("key", "fp", "PC_REGISTER", "new").action == "EXECUTE"
    table.update_item.assert_called_once()


def test_success_update_requires_current_owner_and_started_at():
    service, _ = _service()
    update = service.success_update("key", "owner", NOW.isoformat(), 200, {"ok": True})
    expression = update["Update"]["ConditionExpression"]
    assert "ownerRequestId=:owner" in expression
    assert "startedAt=:started" in expression