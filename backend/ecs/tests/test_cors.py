import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.mark.parametrize("origin", [
    "http://localhost:3000",
    "https://001-pc-management.d2vdxg5wq5iczb.amplifyapp.com",
    "https://main.dtlqgaeqnt7wq.amplifyapp.com",
])
def test_allowed_origin_receives_cors_headers(origin):
    with TestClient(app) as client:
        response = client.get("/", headers={"Origin": origin})
        preflight = client.options("/api/pcs", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
        })

    for result in (response, preflight):
        assert result.status_code == 200
        assert result.headers["access-control-allow-origin"] == origin
        assert result.headers["access-control-allow-credentials"] == "true"
        assert "Origin" in result.headers["vary"]


@pytest.mark.parametrize("origin", [
    "https://untrusted.example.com",
    "https://main.dtlqgaeqnt7wq.amplifyapp.com.evil.example.com",
    "http://main.dtlqgaeqnt7wq.amplifyapp.com",
])
def test_unapproved_origin_does_not_receive_allow_origin(origin):
    with TestClient(app) as client:
        response = client.get("/", headers={"Origin": origin})
        preflight = client.options("/api/pcs", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        })

    assert preflight.status_code == 400
    for result in (response, preflight):
        assert "access-control-allow-origin" not in result.headers