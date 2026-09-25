import sys
from types import ModuleType
from unittest.mock import Mock

from fastapi.testclient import TestClient

jose_module = ModuleType("jose")
jose_module.JWTError = Exception
jose_module.jwt = Mock()
sys.modules.setdefault("jose", jose_module)

import src.main as main


def test_stopped_ecs_returns_machine_readable_starting_response(monkeypatch):
    manager = Mock()
    manager.get_ecs_public_ip.return_value = None
    monkeypatch.setattr(main, "get_ecs_manager", lambda: manager)

    response = TestClient(main.app).get("/api/pcs")

    assert response.status_code == 503
    assert response.json()["status"] == "starting"
    assert response.headers["Retry-After"] == "15"
    assert response.headers["Cache-Control"] == "no-store"
    manager.ensure_ecs_running.assert_called_once()