import hashlib
import hmac
import json
import os
import time
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit

import boto3


INTERNAL_HEADER_PREFIX = "x-internal-"


def normalize_path_with_query(path_with_query: str) -> str:
    parsed = urlsplit(path_with_query)
    path = parsed.path or "/"
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return f"{path}?{query}" if query else path


def hash_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


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


def strip_internal_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if not key.lower().startswith(INTERNAL_HEADER_PREFIX)
    }


class InternalRequestSigner:
    def __init__(
        self,
        secret_arn: Optional[str] = None,
        key_id: Optional[str] = None,
        secrets_client=None,
        clock=time.time,
    ) -> None:
        self.secret_arn = secret_arn or os.environ.get("INTERNAL_PROXY_SECRET_ARN", "")
        self.key_id = key_id or os.environ.get("INTERNAL_PROXY_KEY_ID", "current")
        self.secrets_client = secrets_client or boto3.client("secretsmanager")
        self.clock = clock

    def _load_secret(self) -> Tuple[str, str]:
        if not self.secret_arn:
            raise RuntimeError("INTERNAL_PROXY_SECRET_ARN is required")
        response = self.secrets_client.get_secret_value(SecretId=self.secret_arn)
        payload = json.loads(response["SecretString"])
        generation = payload.get(self.key_id)
        if isinstance(generation, dict):
            resolved_key_id = generation.get("keyId", self.key_id)
            secret = generation.get("secret") or generation.get("value")
        else:
            resolved_key_id = self.key_id
            secret = generation
        if not isinstance(secret, str) or not secret:
            raise RuntimeError("configured internal signing generation was not found")
        return resolved_key_id, secret

    def sign(
        self,
        method: str,
        path_with_query: str,
        body: bytes,
        idempotency_key: str,
        request_id: str,
        timestamp: Optional[int] = None,
    ) -> Dict[str, str]:
        key_id, secret = self._load_secret()
        sent_at = str(int(self.clock() if timestamp is None else timestamp))
        body_sha256 = hash_body(body)
        canonical = build_canonical_request(
            method,
            path_with_query,
            body_sha256,
            idempotency_key,
            request_id,
            sent_at,
            key_id,
        )
        signature = hmac.new(
            secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return {
            "X-Internal-Request-Id": request_id,
            "X-Internal-Timestamp": sent_at,
            "X-Internal-Body-SHA256": body_sha256,
            "X-Internal-Key-Id": key_id,
            "X-Internal-Signature": signature,
        }