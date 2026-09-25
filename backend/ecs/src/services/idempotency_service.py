import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class IdempotencyDecision:
    action: str
    owner_request_id: Optional[str] = None
    started_at: Optional[str] = None
    response_status: Optional[int] = None
    response_body: Optional[Dict[str, Any]] = None


def request_fingerprint(method: str, path: str, body: bytes) -> str:
    value = "\n".join((method.upper(), path, hashlib.sha256(body).hexdigest()))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class IdempotencyService:
    retention_seconds = 7 * 24 * 60 * 60
    stale_seconds = 5 * 60

    def __init__(self, table=None, clock=None) -> None:
        table_name = os.getenv("SYSTEM_ACTIVITY_TABLE_NAME", "SystemActivity")
        self.table = table or boto3.resource("dynamodb").Table(table_name)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def claim(
        self,
        key: str,
        fingerprint: str,
        operation: str,
        owner_request_id: str,
    ) -> IdempotencyDecision:
        now = self.clock()
        now_iso = now.isoformat()
        entity_id = f"request#{key}"
        item = self.table.get_item(Key={"entityId": entity_id}).get("Item")

        if not item:
            try:
                self.table.put_item(
                    Item={
                        "entityId": entity_id,
                        "requestFingerprint": fingerprint,
                        "operation": operation,
                        "status": "PROCESSING",
                        "ownerRequestId": owner_request_id,
                        "startedAt": now_iso,
                    },
                    ConditionExpression="attribute_not_exists(entityId)",
                )
                return IdempotencyDecision("EXECUTE", owner_request_id, now_iso)
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    raise
                return IdempotencyDecision("PROCESSING")

        if item.get("requestFingerprint") != fingerprint:
            return IdempotencyDecision("CONFLICT")

        if item.get("status") == "SUCCEEDED":
            expires_at = int(item.get("expiresAt", 0))
            if expires_at > int(now.timestamp()):
                return IdempotencyDecision(
                    "REPLAY",
                    response_status=int(item.get("responseStatus", 200)),
                    response_body=json.loads(item.get("responseBody", "{}")),
                )
            return self._replace_owner(
                entity_id, fingerprint, owner_request_id, now_iso, "SUCCEEDED"
            )

        started_at = datetime.fromisoformat(item["startedAt"])
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if item.get("status") == "PROCESSING" and now - started_at < timedelta(seconds=self.stale_seconds):
            return IdempotencyDecision("PROCESSING")
        return self._replace_owner(
            entity_id,
            fingerprint,
            owner_request_id,
            now_iso,
            item.get("status", "PROCESSING"),
            item.get("ownerRequestId"),
            item.get("startedAt"),
        )

    def _replace_owner(
        self,
        entity_id: str,
        fingerprint: str,
        owner_request_id: str,
        now_iso: str,
        old_status: str,
        old_owner: Optional[str] = None,
        old_started_at: Optional[str] = None,
    ) -> IdempotencyDecision:
        values = {
            ":processing": "PROCESSING",
            ":fingerprint": fingerprint,
            ":owner": owner_request_id,
            ":started": now_iso,
            ":oldStatus": old_status,
        }
        condition = "requestFingerprint = :fingerprint AND #status = :oldStatus"
        if old_owner is not None:
            condition += " AND ownerRequestId = :oldOwner AND startedAt = :oldStarted"
            values.update({":oldOwner": old_owner, ":oldStarted": old_started_at})
        try:
            self.table.update_item(
                Key={"entityId": entity_id},
                UpdateExpression=(
                    "SET #status=:processing, ownerRequestId=:owner, startedAt=:started "
                    "REMOVE completedAt, responseStatus, responseBody, expiresAt"
                ),
                ConditionExpression=condition,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=values,
            )
            return IdempotencyDecision("EXECUTE", owner_request_id, now_iso)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return IdempotencyDecision("PROCESSING")
            raise

    def success_update(
        self,
        key: str,
        owner_request_id: str,
        started_at: str,
        response_status: int,
        response_body: Dict[str, Any],
    ) -> Dict[str, Any]:
        completed = self.clock()
        return {
            "Update": {
                "TableName": os.getenv("SYSTEM_ACTIVITY_TABLE_NAME", "SystemActivity"),
                "Key": {"entityId": {"S": f"request#{key}"}},
                "UpdateExpression": (
                    "SET #status=:s, completedAt=:completed, responseStatus=:code, "
                    "responseBody=:body, expiresAt=:expires"
                ),
                "ConditionExpression": (
                    "#status=:p AND ownerRequestId=:owner AND startedAt=:started"
                ),
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {
                    ":s": {"S": "SUCCEEDED"},
                    ":p": {"S": "PROCESSING"},
                    ":completed": {"S": completed.isoformat()},
                    ":code": {"N": str(response_status)},
                    ":body": {"S": json.dumps(response_body, ensure_ascii=False)},
                    ":expires": {
                        "N": str(int(completed.timestamp()) + self.retention_seconds)
                    },
                    ":owner": {"S": owner_request_id},
                    ":started": {"S": started_at},
                },
            }
        }