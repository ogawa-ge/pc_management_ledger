import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


ECS_ROOT = Path(__file__).resolve().parents[1]
if str(ECS_ROOT) not in sys.path:
    sys.path.insert(0, str(ECS_ROOT))

from src.main import (
    RequestPrincipal,
    app,
    get_idempotency_service,
    get_request_principal,
    get_user_repository,
)
from src.services.idempotency_service import IdempotencyDecision


@pytest.fixture
def fixed_now():
    return datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def ecs_aws_clients(monkeypatch):
    dynamodb_resource = Mock(name="dynamodb_resource")
    dynamodb_client = Mock(name="dynamodb_client")
    secrets_manager_client = Mock(name="secrets_manager_client")
    tables = {
        name: Mock(name=f"{name}_table")
        for name in (
            "PCs",
            "ReturnRecords",
            "PCUsageHistories",
            "Users",
            "SystemActivity",
        )
    }
    dynamodb_resource.Table.side_effect = lambda name: tables[name]

    import src.db as db_module

    monkeypatch.setattr(db_module, "dynamodb", dynamodb_resource)
    monkeypatch.setattr("src.main.dynamodb", dynamodb_resource)

    return {
        "dynamodb_resource": dynamodb_resource,
        "dynamodb_client": dynamodb_client,
        "secrets_manager": secrets_manager_client,
        "tables": tables,
    }


@pytest.fixture
def business_write_failure():
    failure = RuntimeError("injected business write failure")

    def raise_failure(*_args, **_kwargs):
        raise failure

    return raise_failure


@pytest.fixture
def user_repository_mock():
    repository = Mock()
    repository.get_all_users.return_value = []
    repository.get_user_by_id.return_value = None
    repository.user_exists.return_value = False
    return repository


@pytest.fixture
def pc_create_mock(monkeypatch):
    create_mock = Mock()
    monkeypatch.setattr("src.main.create_pc_transaction", create_mock)
    return create_mock


@pytest.fixture
def idempotency_service_mock():
    service = Mock()
    service.claim.return_value = IdempotencyDecision(
        "EXECUTE", "request-owner", "2026-09-25T00:00:00+00:00"
    )
    return service


@pytest.fixture
def authenticated_principal():
    return RequestPrincipal(user_id="admin-001", role="Admin")


@pytest.fixture
def api_client(user_repository_mock, authenticated_principal, idempotency_service_mock):
    app.dependency_overrides[get_user_repository] = lambda: user_repository_mock
    app.dependency_overrides[get_request_principal] = lambda: authenticated_principal
    app.dependency_overrides[get_idempotency_service] = lambda: idempotency_service_mock
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client(user_repository_mock, idempotency_service_mock):
    app.dependency_overrides[get_user_repository] = lambda: user_repository_mock
    app.dependency_overrides[get_idempotency_service] = lambda: idempotency_service_mock
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()