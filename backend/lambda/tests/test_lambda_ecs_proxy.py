import sys
from types import ModuleType
from unittest.mock import Mock

from fastapi.testclient import TestClient

jose_module = ModuleType("jose")
jose_module.JWTError = Exception
jose_module.jwt = Mock()
sys.modules.setdefault("jose", jose_module)

import src.main as main


def test_non_api_path_returns_404_without_starting_ecs(monkeypatch):
    manager = Mock()
    monkeypatch.setattr(main, "get_ecs_manager", lambda: manager)
    client = TestClient(main.app)

    for non_api_path in ["/robots.txt", "/favicon.ico", "/sitemap.xml", "/.env", "/wp-login.php"]:
        response = client.get(non_api_path)
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}

    manager.record_request_accepted.assert_not_called()
    manager.ensure_ecs_running.assert_not_called()
    manager.get_ecs_public_ip.assert_not_called()


def test_stopped_ecs_returns_machine_readable_starting_response(monkeypatch):
    manager = Mock()
    manager.get_ecs_public_ip.return_value = None
    monkeypatch.setattr(main, "get_ecs_manager", lambda: manager)

    response = TestClient(main.app).get("/api/pcs")

    assert response.status_code == 503
    assert response.json()["status"] == "starting"
    assert response.headers["Retry-After"] == "15"
    assert response.headers["Cache-Control"] == "no-store"
    manager.record_request_accepted.assert_called_once()
    manager.ensure_ecs_running.assert_called_once_with(
        request_id=manager.record_request_accepted.call_args.args[0]
    )


def test_running_ecs_proxies_request_with_api_prefix(monkeypatch):
    manager = Mock()
    manager.get_ecs_public_ip.return_value = "203.0.113.10"
    monkeypatch.setattr(main, "get_ecs_manager", lambda: manager)

    captured_sign = {}

    def fake_sign(self, **kwargs):
        captured_sign.update(kwargs)
        return {"X-Internal-Signature": "sig"}

    monkeypatch.setattr(main.InternalRequestSigner, "sign", fake_sign)
    http = Mock()
    http.request.return_value = Mock(status=200, data=b'{"items":[]}', headers={"Content-Type": "application/json"})
    monkeypatch.setattr(main.urllib3, "PoolManager", lambda: http)

    response = TestClient(main.app).get("/api/pcs?sort=asset_number")

    assert response.status_code == 200
    assert http.request.call_args.kwargs["url"] == "http://203.0.113.10:80/api/pcs?sort=asset_number"
    assert captured_sign["path_with_query"] == "/api/pcs?sort=asset_number"
    manager.begin_in_flight.assert_called_once_with()
    manager.finish_in_flight.assert_called_once_with(succeeded=True)