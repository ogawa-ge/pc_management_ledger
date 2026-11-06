import json
from unittest.mock import Mock

from src.services.internal_request_verifier import InternalRequestVerifier

from test_internal_request_verifier import _signed_headers


def _next_signed_headers():
    import hashlib
    import hmac

    from src.services.internal_request_verifier import build_canonical_request

    body_hash = hashlib.sha256(b"body").hexdigest()
    canonical = build_canonical_request(
        "POST",
        "/api/pcs?a=1",
        body_hash,
        "idem-1",
        "request-1",
        "1000",
        "generation-2",
    )
    headers = _signed_headers(key_id="generation-2")
    headers["X-Internal-Signature"] = hmac.new(
        b"next-secret", canonical.encode(), hashlib.sha256
    ).hexdigest()
    return headers


def test_current_and_next_are_accepted_during_rotation_and_old_is_rejected_after_removal():
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "current": {"keyId": "generation-1", "secret": "test-secret"},
                "next": {"keyId": "generation-2", "secret": "next-secret"},
            }
        )
    }
    verifier = InternalRequestVerifier(
        secret_arn="test-secret-arn", secrets_client=client, clock=lambda: 1000
    )
    assert verifier.verify(
        "POST", "/api/pcs?a=1", b"body", _signed_headers()
    ).valid
    assert verifier.verify(
        "POST", "/api/pcs?a=1", b"body", _next_signed_headers()
    ).valid

    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"current": {"keyId": "generation-2", "secret": "next-secret"}}
        )
    }
    assert not verifier.verify(
        "POST", "/api/pcs?a=1", b"body", _signed_headers()
    ).valid


def test_unregistered_third_generation_is_rejected():
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "current": {"keyId": "generation-1", "secret": "test-secret"},
                "next": {"keyId": "generation-2", "secret": "next-secret"},
                "third": {"keyId": "generation-3", "secret": "third-secret"},
            }
        )
    }
    verifier = InternalRequestVerifier(
        secret_arn="test-secret-arn", secrets_client=client, clock=lambda: 1000
    )
    assert not verifier.verify(
        "POST",
        "/api/pcs?a=1",
        b"body",
        _signed_headers(),
    ).valid