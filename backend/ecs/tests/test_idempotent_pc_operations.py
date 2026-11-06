import copy
import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src.main import app, get_idempotency_service
from src.models.user import User
from src.services.idempotency_service import IdempotencyDecision, IdempotencyService


KEY = "22222222-2222-4222-8222-222222222222"
PAYLOAD = {"ownerId": "user-001", "specsText": "specs", "pcType": "N"}


class MemoryIdempotencyTable:
    def __init__(self):
        self.items = {}

    def get_item(self, Key):
        item = self.items.get(Key["entityId"])
        return {"Item": copy.deepcopy(item)} if item else {}

    def put_item(self, Item, ConditionExpression=None):
        entity_id = Item["entityId"]
        if ConditionExpression == "attribute_not_exists(entityId)" and entity_id in self.items:
            raise AssertionError("unexpected duplicate initial claim")
        self.items[entity_id] = copy.deepcopy(Item)


def _complete_success(table, key, response):
    item = table.items[f"request#{key}"]
    item.update(
        {
            "status": "SUCCEEDED",
            "completedAt": "2026-09-25T00:00:00+00:00",
            "responseStatus": 200,
            "responseBody": json.dumps(response, ensure_ascii=False),
            "expiresAt": int(datetime(2026, 10, 2, 0, 0, 1, tzinfo=timezone.utc).timestamp()),
        }
    )


@pytest.fixture
def real_idempotency_service():
    table = MemoryIdempotencyTable()
    service = IdempotencyService(
        table=table,
        clock=lambda: datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc),
    )
    app.dependency_overrides[get_idempotency_service] = lambda: service
    return service, table


@pytest.fixture
def existing_owner(user_repository_mock):
    user_repository_mock.get_user_by_id.return_value = User(
        user_id="user-001", name="Alice", email="alice@example.com", role="User"
    )


def test_create_replays_saved_success_without_business_write(api_client, existing_owner, pc_create_mock):
    service = Mock()
    service.claim.return_value = IdempotencyDecision(
        "REPLAY", response_status=200, response_body={"pcId": "N-001", "status": "success"}
    )
    app.dependency_overrides[get_idempotency_service] = lambda: service

    response = api_client.post("/api/pcs", json=PAYLOAD, headers={"Idempotency-Key": KEY})

    assert response.status_code == 200
    assert response.headers["Idempotency-Replayed"] == "true"
    assert response.json() == {"pcId": "N-001", "status": "success"}
    pc_create_mock.assert_not_called()


def test_create_conflict_returns_409_without_business_write(api_client, existing_owner, pc_create_mock):
    service = Mock()
    service.claim.return_value = IdempotencyDecision("CONFLICT")
    app.dependency_overrides[get_idempotency_service] = lambda: service

    response = api_client.post("/api/pcs", json=PAYLOAD, headers={"Idempotency-Key": KEY})

    assert response.status_code == 409
    assert response.json()["status"] == "idempotency_conflict"
    pc_create_mock.assert_not_called()


def test_create_processing_returns_retry_after_without_business_write(api_client, existing_owner, pc_create_mock):
    service = Mock()
    service.claim.return_value = IdempotencyDecision("PROCESSING")
    app.dependency_overrides[get_idempotency_service] = lambda: service

    response = api_client.post("/api/pcs", json=PAYLOAD, headers={"Idempotency-Key": KEY})

    assert response.status_code == 409
    assert response.headers["Retry-After"] == "3"
    assert response.json()["status"] == "processing"
    pc_create_mock.assert_not_called()


def test_state_change_requires_uuid_idempotency_key(api_client, existing_owner, pc_create_mock):
    missing = api_client.post("/api/pcs", json=PAYLOAD)
    invalid = api_client.post("/api/pcs", json=PAYLOAD, headers={"Idempotency-Key": "not-a-uuid"})

    assert missing.status_code == 400
    assert invalid.status_code == 400
    pc_create_mock.assert_not_called()


def test_return_replays_saved_success_without_business_write(api_client, monkeypatch):
    service = Mock()
    service.claim.return_value = IdempotencyDecision(
        "REPLAY",
        response_status=200,
        response_body={"status": "success", "message": "returned", "recordId": "record-1"},
    )
    app.dependency_overrides[get_idempotency_service] = lambda: service
    business_write = Mock()
    monkeypatch.setattr("src.main.return_pc_transaction", business_write)

    response = api_client.post(
        "/api/pcs/N-001/return",
        json={"userId": "admin-001", "returnReason": "move", "pcStatusAtReturn": "good"},
        headers={"Idempotency-Key": KEY},
    )

    assert response.status_code == 200
    assert response.headers["Idempotency-Replayed"] == "true"
    assert response.json()["recordId"] == "record-1"
    business_write.assert_not_called()


def test_status_update_replays_saved_success_without_business_write(api_client, ecs_aws_clients, monkeypatch):
    ecs_aws_clients["tables"]["PCs"].get_item.return_value = {}
    service = Mock()
    service.claim.return_value = IdempotencyDecision(
        "REPLAY",
        response_status=200,
        response_body={
            "status": "success",
            "pcId": "N-001",
            "previousStatus": "Unused",
            "newStatus": "Disposed",
            "updatedAt": "2026-09-25T00:00:00+00:00",
        },
    )
    app.dependency_overrides[get_idempotency_service] = lambda: service
    business_write = Mock()
    monkeypatch.setattr("src.main.update_pc_status_transaction", business_write)

    response = api_client.patch(
        "/api/pcs/N-001/status",
        json={"newStatus": "Disposed", "reason": "approved"},
        headers={"Idempotency-Key": KEY},
    )

    assert response.status_code == 200
    assert response.headers["Idempotency-Replayed"] == "true"
    assert response.json()["newStatus"] == "Disposed"
    ecs_aws_clients["tables"]["PCs"].get_item.assert_not_called()
    business_write.assert_not_called()


def test_create_same_key_executes_once_replays_and_rejects_changed_body(
    api_client, existing_owner, real_idempotency_service, monkeypatch
):
    _, table = real_idempotency_service
    business_write = Mock()

    def create_once(_owner_id, _specs_text, _pc_type, idempotency_key, _owner_request_id, _started_at):
        response = {"pcId": "N-001", "status": "success"}
        _complete_success(table, idempotency_key, response)
        return response

    business_write.side_effect = create_once
    monkeypatch.setattr("src.main.create_pc_transaction", business_write)

    first = api_client.post("/api/pcs", json=PAYLOAD, headers={"Idempotency-Key": KEY})
    replay = api_client.post("/api/pcs", json=PAYLOAD, headers={"Idempotency-Key": KEY})
    conflict = api_client.post(
        "/api/pcs",
        json={**PAYLOAD, "specsText": "different specs"},
        headers={"Idempotency-Key": KEY},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["status"] == "idempotency_conflict"
    business_write.assert_called_once()


def test_return_same_key_executes_once_replays_and_rejects_changed_body(
    api_client, real_idempotency_service, monkeypatch
):
    _, table = real_idempotency_service
    business_write = Mock()

    def return_once(**kwargs):
        response = {"status": "success", "message": "returned", "recordId": "record-1"}
        _complete_success(table, kwargs["idempotency_key"], response)
        return response

    business_write.side_effect = return_once
    monkeypatch.setattr("src.main.return_pc_transaction", business_write)
    payload = {"userId": "admin-001", "returnReason": "move", "pcStatusAtReturn": "good"}

    first = api_client.post(
        "/api/pcs/N-001/return", json=payload, headers={"Idempotency-Key": KEY}
    )
    replay = api_client.post(
        "/api/pcs/N-001/return", json=payload, headers={"Idempotency-Key": KEY}
    )
    conflict = api_client.post(
        "/api/pcs/N-001/return",
        json={**payload, "returnReason": "disposed"},
        headers={"Idempotency-Key": KEY},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["status"] == "idempotency_conflict"
    business_write.assert_called_once()


def test_status_same_key_executes_once_replays_and_rejects_changed_body(
    api_client, ecs_aws_clients, real_idempotency_service, monkeypatch
):
    _, table = real_idempotency_service
    pcs_table = ecs_aws_clients["tables"]["PCs"]
    pcs_table.get_item.return_value = {"Item": {"pcId": "N-001", "status": "Unused"}}
    business_write = Mock()

    def update_once(**kwargs):
        response = {
            "status": "success",
            "pcId": "N-001",
            "previousStatus": "Unused",
            "newStatus": "Disposed",
            "updatedAt": "2026-09-25T00:00:00+00:00",
        }
        _complete_success(table, kwargs["idempotency_key"], response)
        return response

    business_write.side_effect = update_once
    monkeypatch.setattr("src.main.update_pc_status_transaction", business_write)
    payload = {"newStatus": "Disposed", "reason": "approved"}

    first = api_client.patch(
        "/api/pcs/N-001/status", json=payload, headers={"Idempotency-Key": KEY}
    )
    replay = api_client.patch(
        "/api/pcs/N-001/status", json=payload, headers={"Idempotency-Key": KEY}
    )
    conflict = api_client.patch(
        "/api/pcs/N-001/status",
        json={**payload, "reason": "different approval"},
        headers={"Idempotency-Key": KEY},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["status"] == "idempotency_conflict"
    business_write.assert_called_once()
    assert pcs_table.get_item.call_count == 1