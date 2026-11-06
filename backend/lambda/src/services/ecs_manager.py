"""ECS の起動集約、活動追跡、安全な自動停止を管理する。"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger()
logger.setLevel(logging.INFO)
logs_client = boto3.client("logs")


class ECSManager:
    """既存 ECS Service と SystemActivity/global の状態を調停する。"""

    def __init__(self, cluster_name: Optional[str] = None, clock=None):
        self.ecs_client = boto3.client("ecs")
        self.dynamodb = boto3.resource("dynamodb")
        self.cluster_name = cluster_name or os.getenv("ECS_CLUSTER_NAME", "PCManagementCluster")
        self.service_name = os.getenv("ECS_SERVICE_NAME", "PCManagementService")
        self.system_activity_table_name = os.getenv(
            "SYSTEM_ACTIVITY_TABLE_NAME", "SystemActivity"
        )
        self.system_activity_table = self.dynamodb.Table(self.system_activity_table_name)
        self.sleep_task_count = 0
        self.active_task_count = 1
        self.idle_timeout_seconds = int(os.getenv("IDLE_TIMEOUT_SECONDS", "7200"))
        self.start_lock_seconds = int(os.getenv("START_LOCK_SECONDS", "180"))
        self.log_group_name = "/aws/lambda/pc-management-ecs"
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._ensure_log_group()

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    def _now_iso(self) -> str:
        return self._now().isoformat()

    @staticmethod
    def _is_conditional_failure(error: ClientError) -> bool:
        return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"

    def _ensure_log_group(self) -> None:
        try:
            logs_client.describe_log_groups(logGroupNamePrefix=self.log_group_name)
        except Exception:
            logger.debug("log group preflight skipped", exc_info=True)

    def _log_audit(
        self, action: str, status: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        entry = {
            "timestamp": self._now_iso(),
            "action": action,
            "status": status,
            "cluster": self.cluster_name,
            **(details or {}),
        }
        logger.info(json.dumps(entry, ensure_ascii=False, default=str))

    def _runtime_item(self) -> Dict[str, Any]:
        return self.system_activity_table.get_item(
            Key={"entityId": "global"}, ConsistentRead=True
        ).get("Item", {})

    def _service(self) -> Dict[str, Any]:
        response = self.ecs_client.describe_services(
            cluster=self.cluster_name, services=[self.service_name]
        )
        services = response.get("services", [])
        if not services:
            raise RuntimeError("ECS service was not found")
        return services[0]

    def get_ecs_public_ip(self) -> Optional[str]:
        try:
            tasks_response = self.ecs_client.list_tasks(
                cluster=self.cluster_name,
                serviceName=self.service_name,
                desiredStatus="RUNNING",
            )
            task_arns = tasks_response.get("taskArns", [])
            if not task_arns:
                return None
            tasks = self.ecs_client.describe_tasks(
                cluster=self.cluster_name, tasks=[task_arns[0]]
            ).get("tasks", [])
            if not tasks or tasks[0].get("lastStatus") != "RUNNING":
                return None
            eni_id = None
            for attachment in tasks[0].get("attachments", []):
                if attachment.get("type") != "ElasticNetworkInterface":
                    continue
                for detail in attachment.get("details", []):
                    if detail.get("name") == "networkInterfaceId":
                        eni_id = detail.get("value")
                        break
            if not eni_id:
                return None
            ec2_client = boto3.client("ec2")
            interfaces = ec2_client.describe_network_interfaces(
                NetworkInterfaceIds=[eni_id]
            ).get("NetworkInterfaces", [])
            if not interfaces:
                return None
            public_ip = interfaces[0].get("Association", {}).get("PublicIp")
            if public_ip:
                self._mark_runtime_running()
            return public_ip
        except Exception as error:
            logger.error("Failed to get ECS public IP: %s", error)
            return None

    def record_request_accepted(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        """受付時刻を更新し、停止中なら新しい起動世代へ進める。"""
        now_value = self._now()
        now = now_value.isoformat()
        owner = request_id or str(uuid.uuid4())
        self.system_activity_table.update_item(
            Key={"entityId": "global"},
            UpdateExpression=(
                "SET lastAcceptedAt=:now, "
                "runtimeState=if_not_exists(runtimeState,:stopped), "
                "generation=if_not_exists(generation,:zero), "
                "inFlightCount=if_not_exists(inFlightCount,:zero), "
                "lastStateChangedAt=if_not_exists(lastStateChangedAt,:now)"
            ),
            ExpressionAttributeValues={
                ":now": now,
                ":stopped": "STOPPED",
                ":zero": Decimal(0),
            },
        )
        try:
            response = self.system_activity_table.update_item(
                Key={"entityId": "global"},
                UpdateExpression=(
                    "SET runtimeState=:starting, generation=generation+:one, "
                    "startRequestedAt=:now, lastStateChangedAt=:now, "
                    "startOwnerRequestId=:owner, startLockExpiresAt=:expiry"
                ),
                ConditionExpression="runtimeState=:stopping",
                ExpressionAttributeValues={
                    ":starting": "STARTING",
                    ":stopping": "STOPPING",
                    ":one": Decimal(1),
                    ":now": now,
                    ":owner": owner,
                    ":expiry": Decimal(int(now_value.timestamp()) + self.start_lock_seconds),
                },
                ReturnValues="ALL_NEW",
            )
            return {"stop_cancelled": True, **response.get("Attributes", {})}
        except ClientError as error:
            if not self._is_conditional_failure(error):
                raise
        return {"stop_cancelled": False}

    def begin_in_flight(self) -> None:
        self.system_activity_table.update_item(
            Key={"entityId": "global"},
            UpdateExpression=(
                "SET inFlightCount=if_not_exists(inFlightCount,:zero)+:one, "
                "lastStateChangedAt=if_not_exists(lastStateChangedAt,:now)"
            ),
            ExpressionAttributeValues={
                ":zero": Decimal(0),
                ":one": Decimal(1),
                ":now": self._now_iso(),
            },
        )

    def finish_in_flight(self, succeeded: bool) -> None:
        values = {":zero": Decimal(0), ":one": Decimal(1)}
        expression = "SET inFlightCount=inFlightCount-:one"
        if succeeded:
            expression += ", lastActivityAt=:now"
            values[":now"] = self._now_iso()
        try:
            self.system_activity_table.update_item(
                Key={"entityId": "global"},
                UpdateExpression=expression,
                ConditionExpression="inFlightCount > :zero",
                ExpressionAttributeValues=values,
            )
        except ClientError as error:
            if not self._is_conditional_failure(error):
                raise
            self._log_audit(
                "finish_in_flight", "invalid_runtime_activity", {"reason": "non_positive_in_flight"}
            )

    def _claim_start(self, owner: str) -> Optional[int]:
        runtime = self._runtime_item()
        if (
            runtime.get("runtimeState") == "STARTING"
            and runtime.get("startOwnerRequestId") == owner
            and isinstance(runtime.get("generation"), (int, Decimal))
        ):
            return int(runtime["generation"])
        now = self._now()
        now_iso = now.isoformat()
        now_epoch = Decimal(int(now.timestamp()))
        lock_expiry = Decimal(int(now.timestamp()) + self.start_lock_seconds)
        try:
            response = self.system_activity_table.update_item(
                Key={"entityId": "global"},
                UpdateExpression=(
                    "SET runtimeState=:starting, "
                    "generation=if_not_exists(generation,:zero)+:one, "
                    "inFlightCount=if_not_exists(inFlightCount,:zero), "
                    "startOwnerRequestId=:owner, startRequestedAt=:now, "
                    "startLockExpiresAt=:expiry, lastStateChangedAt=:now"
                ),
                ConditionExpression=(
                    "attribute_not_exists(runtimeState) OR "
                    "runtimeState IN (:stopped,:failed,:running) OR "
                    "(runtimeState=:starting AND startLockExpiresAt <= :nowEpoch)"
                ),
                ExpressionAttributeValues={
                    ":starting": "STARTING",
                    ":stopped": "STOPPED",
                    ":failed": "START_FAILED",
                    ":running": "RUNNING",
                    ":zero": Decimal(0),
                    ":one": Decimal(1),
                    ":owner": owner,
                    ":now": now_iso,
                    ":expiry": lock_expiry,
                    ":nowEpoch": now_epoch,
                },
                ReturnValues="ALL_NEW",
            )
            return int(response.get("Attributes", {}).get("generation", 1))
        except ClientError as error:
            if self._is_conditional_failure(error):
                return None
            raise

    def _mark_start_outcome(
        self, owner: str, generation: int, state: str, error_code: Optional[str] = None
    ) -> bool:
        expression = "SET runtimeState=:state, lastStateChangedAt=:now"
        values: Dict[str, Any] = {
            ":state": state,
            ":now": self._now_iso(),
            ":owner": owner,
            ":generation": Decimal(generation),
            ":starting": "STARTING",
        }
        if error_code:
            expression += ", lastErrorCode=:error, lastErrorAt=:now"
            values[":error"] = error_code
        try:
            self.system_activity_table.update_item(
                Key={"entityId": "global"},
                UpdateExpression=expression,
                ConditionExpression=(
                    "startOwnerRequestId=:owner AND generation=:generation "
                    "AND runtimeState=:starting"
                ),
                ExpressionAttributeValues=values,
            )
            return True
        except ClientError as error:
            if self._is_conditional_failure(error):
                return False
            raise

    def _mark_runtime_running(self) -> None:
        runtime = self._runtime_item()
        if runtime.get("runtimeState") == "RUNNING":
            return
        owner = runtime.get("startOwnerRequestId")
        generation = runtime.get("generation")
        if not owner or not isinstance(generation, (int, Decimal)):
            self._log_audit(
                "mark_runtime_running",
                "invalid_runtime_activity",
                {"reason": "start owner or generation is missing"},
            )
            return
        self._mark_start_outcome(owner, int(generation), "RUNNING")

    def start_ecs(
        self, user_id: Optional[str] = None, request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        owner = request_id or str(uuid.uuid4())
        status = self.get_ecs_status()
        if status.get("status") == "error":
            return status
        if status.get("running_count", 0) > 0 and status.get("desired_count", 0) > 0:
            self._mark_runtime_running()
            return {
                "status": "already_running",
                "message": "ECS is already running",
                "running_count": status.get("running_count", 0),
            }

        generation = self._claim_start(owner)
        if generation is None:
            shared = self.get_ecs_status()
            return {
                "status": "already_running"
                if shared.get("running_count", 0) > 0
                else "starting",
                "message": "ECS start is already in progress",
                "desired_count": shared.get("desired_count", 0),
                "running_count": shared.get("running_count", 0),
            }

        try:
            update_response = self.ecs_client.update_service(
                cluster=self.cluster_name,
                service=self.service_name,
                desiredCount=self.active_task_count,
            )
            service = update_response.get("service", {})
            self._log_audit(
                "start_ecs",
                "success",
                {"generation": generation, "user_id": user_id, "owner_request_id": owner},
            )
            return {
                "status": "started",
                "message": "ECS service started",
                "service_arn": service.get("serviceArn"),
                "desired_count": self.active_task_count,
                "generation": generation,
                "timestamp": self._now_iso(),
            }
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "ECS_START_FAILED")
            self._mark_start_outcome(owner, generation, "START_FAILED", code)
            self._log_audit("start_ecs", "failure", {"error_code": code})
            return {"status": "error", "message": "Failed to start ECS", "error_code": code}

    def stop_ecs(
        self, reason: str = "idle_timeout", expected_generation: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            update_response = self.ecs_client.update_service(
                cluster=self.cluster_name,
                service=self.service_name,
                desiredCount=self.sleep_task_count,
            )
            runtime = self._runtime_item()
            generation_changed = (
                expected_generation is not None
                and int(runtime.get("generation", -1)) != expected_generation
            )
            restart_required = generation_changed or runtime.get("runtimeState") == "STARTING"
            if restart_required:
                self.ecs_client.update_service(
                    cluster=self.cluster_name,
                    service=self.service_name,
                    desiredCount=self.active_task_count,
                )
                return {
                    "status": "restart_requested",
                    "message": "A newer operation requested ECS restart",
                    "desired_count": self.active_task_count,
                }
            if expected_generation is not None:
                try:
                    self.system_activity_table.update_item(
                        Key={"entityId": "global"},
                        UpdateExpression="SET runtimeState=:stopped, lastStateChangedAt=:now",
                        ConditionExpression="runtimeState=:stopping AND generation=:generation",
                        ExpressionAttributeValues={
                            ":stopped": "STOPPED",
                            ":stopping": "STOPPING",
                            ":generation": Decimal(expected_generation),
                            ":now": self._now_iso(),
                        },
                    )
                except ClientError as error:
                    if not self._is_conditional_failure(error):
                        raise
                    self.ecs_client.update_service(
                        cluster=self.cluster_name,
                        service=self.service_name,
                        desiredCount=self.active_task_count,
                    )
                    return {"status": "restart_requested", "desired_count": 1}
            service = update_response.get("service", {})
            self._log_audit("stop_ecs", "success", {"reason": reason})
            return {
                "status": "stopped",
                "message": "ECS service stopped (sleeping)",
                "service_arn": service.get("serviceArn"),
                "desired_count": self.sleep_task_count,
                "timestamp": self._now_iso(),
            }
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "ECS_STOP_FAILED")
            return {"status": "error", "message": "Failed to stop ECS", "error_code": code}

    def get_ecs_status(self) -> Dict[str, Any]:
        try:
            service = self._service()
            desired_count = service.get("desiredCount", 0)
            running_count = service.get("runningCount", 0)
            return {
                "status": "active" if running_count > 0 else "sleeping",
                "desired_count": desired_count,
                "running_count": running_count,
                "deployment_status": service.get("status", "UNKNOWN"),
                "timestamp": self._now_iso(),
            }
        except (ClientError, RuntimeError) as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code", "ECS_STATUS_FAILED")
            return {"status": "error", "message": "Failed to get ECS status", "error_code": code}

    @staticmethod
    def _parse_activity_timestamp(value: Any) -> datetime:
        if not isinstance(value, str) or not value:
            raise ValueError("lastActivityAt is missing")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _invalid_activity(self, check_id: str, reason: str) -> Dict[str, Any]:
        self._log_audit(
            "check_idle_timeout",
            "invalid_runtime_activity",
            {"check_id": check_id, "reason": reason},
        )
        return {"status": "skip", "reason": "invalid_runtime_activity", "message": reason}

    def check_and_auto_sleep(
        self, last_activity_timestamp: Optional[str] = None, check_id: str = "system"
    ) -> Dict[str, Any]:
        current_status = self.get_ecs_status()
        if current_status.get("status") == "error":
            return current_status
        if current_status.get("running_count", 0) == 0:
            return {"status": "already_sleeping", "message": "ECS is already in sleep state"}

        runtime = self._runtime_item()
        activity_value = last_activity_timestamp or runtime.get("lastActivityAt")
        in_flight = runtime.get("inFlightCount")
        generation = runtime.get("generation")
        if not isinstance(in_flight, (int, Decimal)) or in_flight < 0:
            return self._invalid_activity(check_id, "inFlightCount is missing or invalid")
        if int(in_flight) > 0:
            return {"status": "active", "reason": "in_flight", "in_flight_count": int(in_flight)}
        if not isinstance(generation, (int, Decimal)) or generation < 0:
            return self._invalid_activity(check_id, "generation is missing or invalid")
        try:
            last_activity = self._parse_activity_timestamp(activity_value)
        except (TypeError, ValueError) as error:
            return self._invalid_activity(check_id, str(error))
        now = self._now()
        if last_activity > now:
            return self._invalid_activity(check_id, "lastActivityAt is in the future")
        idle_time = (now - last_activity).total_seconds()
        if idle_time < self.idle_timeout_seconds:
            return {
                "status": "active",
                "idle_time_seconds": idle_time,
                "remaining_until_auto_sleep": self.idle_timeout_seconds - idle_time,
            }

        generation_int = int(generation)
        try:
            self.system_activity_table.update_item(
                Key={"entityId": "global"},
                UpdateExpression="SET runtimeState=:stopping, stopRequestedAt=:now, lastStateChangedAt=:now",
                ConditionExpression=(
                    "runtimeState=:running AND generation=:generation AND "
                    "inFlightCount=:zero AND lastActivityAt <= :boundary"
                ),
                ExpressionAttributeValues={
                    ":stopping": "STOPPING",
                    ":running": "RUNNING",
                    ":generation": Decimal(generation_int),
                    ":zero": Decimal(0),
                    ":boundary": datetime.fromtimestamp(
                        now.timestamp() - self.idle_timeout_seconds, timezone.utc
                    ).isoformat(),
                    ":now": now.isoformat(),
                },
            )
        except ClientError as error:
            if self._is_conditional_failure(error):
                return {"status": "active", "reason": "stop_gate_changed"}
            raise
        result = self.stop_ecs(reason="idle_timeout", expected_generation=generation_int)
        return {
            "status": "auto_slept" if result.get("status") == "stopped" else result.get("status"),
            "idle_time_seconds": idle_time,
            "action_result": result,
        }

    def ensure_ecs_running(
        self, user_id: Optional[str] = None, request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return self.start_ecs(user_id=user_id, request_id=request_id)


_ecs_manager: Optional[ECSManager] = None


def get_ecs_manager() -> ECSManager:
    global _ecs_manager
    if _ecs_manager is None:
        _ecs_manager = ECSManager()
    return _ecs_manager


def lambda_handler_ecs_start(event, context):
    user_id = event.get("user_id") or event.get("userId") if isinstance(event, dict) else None
    result = get_ecs_manager().start_ecs(user_id=user_id)
    return {
        "statusCode": 200 if result.get("status") != "error" else 500,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }


def lambda_handler_ecs_stop(event, context):
    reason = event.get("reason", "manual_stop") if isinstance(event, dict) else "manual_stop"
    result = get_ecs_manager().stop_ecs(reason=reason)
    return {
        "statusCode": 200 if result.get("status") != "error" else 500,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }


def lambda_handler_ecs_status(event, context):
    result = get_ecs_manager().get_ecs_status()
    return {
        "statusCode": 200 if result.get("status") != "error" else 500,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }


def lambda_handler_cloudwatch_timeout_check(event, context):
    manager = get_ecs_manager()
    try:
        result = manager.check_and_auto_sleep(check_id=getattr(context, "request_id", "system"))
        return {
            "statusCode": 200,
            "body": json.dumps(result),
            "headers": {"Content-Type": "application/json"},
        }
    except Exception as error:
        logger.exception("Error in timeout check")
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(error)}),
            "headers": {"Content-Type": "application/json"},
        }