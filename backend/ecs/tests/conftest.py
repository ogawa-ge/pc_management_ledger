import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


ECS_ROOT = Path(__file__).resolve().parents[1]
if str(ECS_ROOT) not in sys.path:
    sys.path.insert(0, str(ECS_ROOT))

from src.main import RequestPrincipal, app, get_request_principal, get_user_repository


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
    monkeypatch.setattr("src.main.create_pc", create_mock)
    return create_mock


@pytest.fixture
def authenticated_principal():
    return RequestPrincipal(user_id="admin-001", role="Admin")


@pytest.fixture
def api_client(user_repository_mock, authenticated_principal):
    app.dependency_overrides[get_user_repository] = lambda: user_repository_mock
    app.dependency_overrides[get_request_principal] = lambda: authenticated_principal
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client(user_repository_mock):
    app.dependency_overrides[get_user_repository] = lambda: user_repository_mock
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()