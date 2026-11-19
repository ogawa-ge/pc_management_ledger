import json
from unittest.mock import Mock

import pytest

from src.services.internal_request_verifier import InternalRequestVerifier


def _signed_headers(timestamp=1000, body=b"body", key_id="generation-1"):
    import hashlib
    import hmac

    from src.services.internal_request_verifier import build_canonical_request

    body_hash = hashlib.sha256(body).hexdigest()
    canonical = build_canonical_request(
        "POST", "/api/pcs?a=1", body_hash, "idem-1", "request-1", str(timestamp), key_id
    )
    return {
        "Idempotency-Key": "idem-1",
        "X-Internal-Request-Id": "request-1",
        "X-Internal-Timestamp": str(timestamp),
        "X-Internal-Body-SHA256": body_hash,
        "X-Internal-Key-Id": key_id,
        "X-Internal-Signature": hmac.new(
            b"test-secret", canonical.encode(), hashlib.sha256
        ).hexdigest(),
    }


@pytest.mark.parametrize(
    ("offset", "expected"), [(-61, False), (-60, True), (60, True), (61, False)]
)
def test_timestamp_window_boundaries(offset, expected):
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"current": {"keyId": "generation-1", "secret": "test-secret"}}
        )
    }
    verifier = InternalRequestVerifier(
        secret_arn="test-secret-arn", secrets_client=client, clock=lambda: 1000
    )
    result = verifier.verify(
        "POST", "/api/pcs?a=1", b"body", _signed_headers(1000 + offset)
    )
    assert result.valid is expected


def test_missing_tampered_and_unknown_signatures_are_rejected():
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"current": {"keyId": "generation-1", "secret": "test-secret"}}
        )
    }
    verifier = InternalRequestVerifier(
        secret_arn="test-secret-arn", secrets_client=client, clock=lambda: 1000
    )
    assert not verifier.verify("POST", "/api/pcs", b"body", {}).valid
    assert not verifier.verify(
        "POST", "/api/pcs?a=1", b"tampered", _signed_headers()
    ).valid
    assert not verifier.verify(
        "POST", "/api/pcs?a=1", b"body", _signed_headers(key_id="unknown")
    ).valid


@pytest.mark.parametrize(
    ("method", "path", "header_name", "header_value"),
    [
        ("PATCH", "/api/pcs?a=1", None, None),
        ("POST", "/api/pcs?a=2", None, None),
        ("POST", "/api/pcs?a=1", "X-Internal-Request-Id", "request-2"),
        ("POST", "/api/pcs?a=1", "Idempotency-Key", "idem-2"),
        ("POST", "/api/pcs?a=1", "X-Internal-Signature", "0" * 64),
    ],
)
def test_canonical_field_tampering_is_rejected(method, path, header_name, header_value):
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"current": {"keyId": "generation-1", "secret": "test-secret"}}
        )
    }
    verifier = InternalRequestVerifier(
        secret_arn="test-secret-arn", secrets_client=client, clock=lambda: 1000
    )
    headers = _signed_headers()
    if header_name:
        headers[header_name] = header_value
    assert not verifier.verify(method, path, b"body", headers).valid


def test_post_request_with_verification_enabled_replays_body_without_deadlock(monkeypatch):
    import hashlib
    import hmac
    import time
    from fastapi.testclient import TestClient

    from src.main import app as ecs_app
    from src.services.internal_request_verifier import (
        InternalRequestVerifier as VerifierClass,
        build_canonical_request,
    )

    secret_client = Mock()
    secret_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"current": {"keyId": "generation-1", "secret": "test-secret"}}
        )
    }

    now_ts = int(time.time())
    monkeypatch.setattr(
        "src.main.InternalRequestVerifier",
        lambda: VerifierClass(
            secret_arn="test-secret-arn",
            secrets_client=secret_client,
            clock=lambda: now_ts,
        ),
    )

    body = json.dumps({"ownerId": "user-1", "pcType": "N", "pcName": "PC-1"}).encode("utf-8")
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = build_canonical_request(
        "POST", "/api/pcs", body_hash, "idem-replay-1", "req-replay-1", str(now_ts), "generation-1"
    )
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": "idem-replay-1",
        "X-Internal-Request-Id": "req-replay-1",
        "X-Internal-Timestamp": str(now_ts),
        "X-Internal-Body-SHA256": body_hash,
        "X-Internal-Key-Id": "generation-1",
        "X-Internal-Signature": hmac.new(
            b"test-secret", canonical.encode(), hashlib.sha256
        ).hexdigest(),
    }

    with TestClient(ecs_app) as client:
        # 認証ヘッダーなしのため、ミドルウェアを正常通過して下流ハンドラの 401 に到達すること（デッドロックしないこと）
        response = client.post("/api/pcs", content=body, headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Authorization header required"