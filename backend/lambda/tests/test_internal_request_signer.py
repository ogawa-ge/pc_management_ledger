import hashlib
import hmac
import json
from unittest.mock import Mock

from src.services.internal_request_signer import (
    InternalRequestSigner,
    build_canonical_request,
    strip_internal_headers,
)


def test_signer_covers_canonical_request_fields_and_strips_external_headers():
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"current": {"keyId": "generation-1", "secret": "test-secret"}}
        )
    }
    signer = InternalRequestSigner(
        secret_arn="test-secret-arn",
        key_id="current",
        secrets_client=client,
        clock=lambda: 1000,
    )
    body = b'{"name":"pc"}'
    headers = signer.sign(
        "post", "/api/pcs?z=2&a=1", body, "idem-1", "request-1"
    )

    canonical = build_canonical_request(
        "POST",
        "/api/pcs?a=1&z=2",
        hashlib.sha256(body).hexdigest(),
        "idem-1",
        "request-1",
        "1000",
        "generation-1",
    )
    expected = hmac.new(
        b"test-secret", canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert headers["X-Internal-Signature"] == expected
    assert headers["X-Internal-Key-Id"] == "generation-1"
    assert strip_internal_headers(
        {"Authorization": "Bearer user", "X-Internal-Signature": "attacker"}
    ) == {"Authorization": "Bearer user"}