import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit

import boto3


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    reason: str = ""


def normalize_path_with_query(path_with_query: str) -> str:
    parsed = urlsplit(path_with_query)
    path = parsed.path or "/"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return f"{path}?{query}" if query else path


def build_canonical_request(
    method: str,
    path_with_query: str,
    body_sha256: str,
    idempotency_key: str,
    request_id: str,
    timestamp: str,
    key_id: str,
) -> str:
    return "\n".join(
        (
            method.upper(),
            normalize_path_with_query(path_with_query),
            body_sha256,
            idempotency_key,
            request_id,
            timestamp,
            key_id,
        )
    )


class InternalRequestVerifier:
    required_headers = (
        "x-internal-request-id",
        "x-internal-timestamp",
        "x-internal-body-sha256",
        "x-internal-key-id",
        "x-internal-signature",
    )

    def __init__(
        self,
        secret_arn: Optional[str] = None,
        secrets_client=None,
        clock=time.time,
        allowed_clock_skew_seconds: int = 60,
    ) -> None:
        self.secret_arn = secret_arn or os.environ.get("INTERNAL_PROXY_SECRET_ARN", "")
        self.secrets_client = secrets_client or boto3.client("secretsmanager")
        self.clock = clock
        self.allowed_clock_skew_seconds = allowed_clock_skew_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.secret_arn)

    def _load_generations(self) -> Dict[str, str]:
        response = self.secrets_client.get_secret_value(SecretId=self.secret_arn)
        payload = json.loads(response["SecretString"])
        generation_entries = [
            value
            for value in payload.values()
            if isinstance(value, dict) and ("secret" in value or "value" in value)
        ]
        if len(generation_entries) > 2:
            raise RuntimeError("at most two internal signing generations are allowed")
        generations: Dict[str, str] = {}
        for configured_id, value in payload.items():
            if configured_id not in {"current", "next"}:
                continue
            if isinstance(value, dict):
                key_id = value.get("keyId", configured_id)
                secret = value.get("secret") or value.get("value")
            else:
                key_id = configured_id
                secret = value
            if isinstance(key_id, str) and isinstance(secret, str) and secret:
                generations[key_id] = secret
        return generations

    def verify(
        self,
        method: str,
        path_with_query: str,
        body: bytes,
        headers: Dict[str, str],
    ) -> VerificationResult:
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        if any(not normalized_headers.get(name) for name in self.required_headers):
            return VerificationResult(False, "missing_internal_signature")

        try:
            sent_at = int(normalized_headers["x-internal-timestamp"])
        except (TypeError, ValueError):
            return VerificationResult(False, "invalid_internal_timestamp")
        if abs(int(self.clock()) - sent_at) > self.allowed_clock_skew_seconds:
            return VerificationResult(False, "expired_internal_signature")

        actual_body_hash = hashlib.sha256(body).hexdigest()
        supplied_body_hash = normalized_headers["x-internal-body-sha256"]
        if not hmac.compare_digest(actual_body_hash, supplied_body_hash):
            return VerificationResult(False, "invalid_internal_body_hash")

        key_id = normalized_headers["x-internal-key-id"]
        try:
            secret = self._load_generations().get(key_id)
        except (KeyError, ValueError, TypeError, json.JSONDecodeError, RuntimeError):
            return VerificationResult(False, "invalid_internal_secret_configuration")
        if not secret:
            return VerificationResult(False, "unknown_internal_key_id")

        canonical = build_canonical_request(
            method,
            path_with_query,
            supplied_body_hash,
            normalized_headers.get("idempotency-key", ""),
            normalized_headers["x-internal-request-id"],
            normalized_headers["x-internal-timestamp"],
            key_id,
        )
        expected = hmac.new(
            secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, normalized_headers["x-internal-signature"]):
            return VerificationResult(False, "invalid_internal_signature")
        return VerificationResult(True)