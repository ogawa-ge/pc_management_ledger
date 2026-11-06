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