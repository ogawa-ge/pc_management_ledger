"""
ECS 自動スリープおよび起動ロジック

このモジュールは、AWS ECS タスクの自動スリープ/起動を管理します。
- ユーザーが資産管理機能にアクセスする際に ECS を起動
- 2 時間のアイドル時間後に自動的にスリープ状態に遷移
"""

import boto3
import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# CloudWatch Logs へのロギング設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# CloudWatch Logs クライアント
logs_client = boto3.client("logs")


class ECSManager:
    """ECS タスクの起動・停止・スリープ管理を行うクラス"""

    def __init__(self, cluster_name: str = "pc-management-cluster"):
        """
        ECSManager を初期化します

        Args:
            cluster_name (str): ECS クラスター名
        """
        self.ecs_client = boto3.client("ecs")
        self.dynamodb = boto3.resource("dynamodb")
        self.cluster_name = cluster_name
        self.task_definition = "pc-management-ecs-task"
        # ECS のスリープを実現するため、タスク数を 0 に設定する状態を「スリープ」と定義
        self.sleep_task_count = 0
        self.active_task_count = 1
        self.idle_timeout_seconds = 2 * 60 * 60  # 2 hours
        self.log_group_name = "/aws/lambda/pc-management-ecs"
        
        # ロググループの存在確認と作成
        self._ensure_log_group()

    def _ensure_log_group(self) -> None:
        """CloudWatch Logs のロググループを確認し、なければ作成します"""
        try:
            logs_client.describe_log_groups(logGroupNamePrefix=self.log_group_name)
        except logs_client.exceptions.ResourceNotFoundException:
            try:
                logs_client.create_log_group(logGroupName=self.log_group_name)
                logger.info(f"Created log group: {self.log_group_name}")
            except Exception as e:
                logger.warning(f"Failed to create log group: {str(e)}")

    def _log_audit(self, action: str, status: str, details: Dict[str, Any] = None) -> None:
        """
        監査ログを CloudWatch Logs に出力します

        Args:
            action (str): 実行したアクション（start, stop, sleep, check など）
            status (str): ステータス（success, failure など）
            details (Dict[str, Any]): その他の詳細情報
        """
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "action": action,
                "status": status,
                "cluster": self.cluster_name,
                **(details or {}),
            }
            
            # CloudWatch Logs に出力
            logger.info(json.dumps(log_entry))
            
        except Exception as e:
            logger.error(f"Failed to log audit: {str(e)}")

    def _update_last_activity(self, entity_id: Optional[str] = None, entity_type: str = "system") -> None:
        """
        DynamoDB の lastActivityAt フィールドを更新します

        Args:
            entity_id (Optional[str]): ユーザー ID または PC ID
            entity_type (str): エンティティの種類（system, user, pc）
        """
        try:
            if entity_type == "system":
                # システム全体のアクティビティ更新
                table = self.dynamodb.Table("SystemActivity")
                table.update_item(
                    Key={"entityId": "global"},
                    UpdateExpression="SET lastActivityAt = :timestamp",
                    ExpressionAttributeValues={":timestamp": datetime.utcnow().isoformat()},
                )
            elif entity_type == "user" and entity_id:
                # ユーザーのアクティビティ更新
                table = self.dynamodb.Table("Users")
                table.update_item(
                    Key={"userId": entity_id},
                    UpdateExpression="SET lastActivityAt = :timestamp",
                    ExpressionAttributeValues={":timestamp": datetime.utcnow().isoformat()},
                )
            elif entity_type == "pc" and entity_id:
                # PC のアクティビティ更新
                table = self.dynamodb.Table("PCs")
                table.update_item(
                    Key={"pcId": entity_id},
                    UpdateExpression="SET lastActivityAt = :timestamp",
                    ExpressionAttributeValues={":timestamp": datetime.utcnow().isoformat()},
                )
        except Exception as e:
            logger.warning(f"Failed to update last activity: {str(e)}")

    def start_ecs(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        ECS タスクを起動します（スリープ状態から復帰）

        Args:
            user_id (Optional[str]): リクエストを送信したユーザーID

        Returns:
            Dict[str, Any]: 起動結果とタスク情報
        """
        try:
            # 現在の ECS サービスの状態を確認
            service_response = self.ecs_client.describe_services(
                cluster=self.cluster_name, services=["pc-management-service"]
            )

            current_count = service_response["services"][0].get("desiredCount", 0)

            # 既に起動している場合はスキップ
            if current_count > 0:
                self._log_audit(
                    action="start_ecs",
                    status="already_running",
                    details={"current_task_count": current_count, "user_id": user_id},
                )
                return {
                    "status": "already_running",
                    "message": "ECS service is already running",
                    "current_task_count": current_count,
                }

            # サービスの desired count を 1 に更新（起動）
            update_response = self.ecs_client.update_service(
                cluster=self.cluster_name,
                service="pc-management-service",
                desiredCount=self.active_task_count,
            )

            # アクティビティを更新
            self._update_last_activity(entity_id=user_id, entity_type="user")
            self._update_last_activity(entity_type="system")

            result = {
                "status": "started",
                "message": "ECS service started",
                "service_arn": update_response["service"]["serviceArn"],
                "desired_count": self.active_task_count,
                "timestamp": datetime.utcnow().isoformat(),
            }

            self._log_audit(
                action="start_ecs",
                status="success",
                details={"user_id": user_id, "service_arn": update_response["service"]["serviceArn"]},
            )

            return result

        except ClientError as e:
            self._log_audit(
                action="start_ecs",
                status="failure",
                details={"user_id": user_id, "error_code": e.response["Error"]["Code"], "error_message": str(e)},
            )
            return {
                "status": "error",
                "message": f"Failed to start ECS: {str(e)}",
                "error_code": e.response["Error"]["Code"],
            }

    def stop_ecs(self, reason: str = "idle_timeout") -> Dict[str, Any]:
        """
        ECS タスクをスリープ状態にします（スケールダウン）

        Args:
            reason (str): 停止理由（idle_timeout, manual_stop など）

        Returns:
            Dict[str, Any]: スリープ状態への遷移結果
        """
        try:
            # サービスの desired count を 0 に更新（スリープ）
            update_response = self.ecs_client.update_service(
                cluster=self.cluster_name,
                service="pc-management-service",
                desiredCount=self.sleep_task_count,
            )

            result = {
                "status": "stopped",
                "message": "ECS service stopped (sleeping)",
                "service_arn": update_response["service"]["serviceArn"],
                "desired_count": self.sleep_task_count,
                "timestamp": datetime.utcnow().isoformat(),
            }

            self._log_audit(
                action="stop_ecs",
                status="success",
                details={"reason": reason, "service_arn": update_response["service"]["serviceArn"]},
            )

            return result

        except ClientError as e:
            self._log_audit(
                action="stop_ecs",
                status="failure",
                details={"reason": reason, "error_code": e.response["Error"]["Code"], "error_message": str(e)},
            )
            return {
                "status": "error",
                "message": f"Failed to stop ECS: {str(e)}",
                "error_code": e.response["Error"]["Code"],
            }

    def get_ecs_status(self) -> Dict[str, Any]:
        """
        ECS サービスの現在の状態を取得します

        Returns:
            Dict[str, Any]: ECS サービスの状態情報
        """
        try:
            service_response = self.ecs_client.describe_services(
                cluster=self.cluster_name, services=["pc-management-service"]
            )

            service = service_response["services"][0]
            desired_count = service.get("desiredCount", 0)
            running_count = service.get("runningCount", 0)

            return {
                "status": "active" if running_count > 0 else "sleeping",
                "desired_count": desired_count,
                "running_count": running_count,
                "deployment_status": service.get("status", "UNKNOWN"),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except ClientError as e:
            return {
                "status": "error",
                "message": f"Failed to get ECS status: {str(e)}",
                "error_code": e.response["Error"]["Code"],
            }

    def check_and_auto_sleep(
        self, last_activity_timestamp: Optional[str] = None, check_id: str = "system"
    ) -> Dict[str, Any]:
        """
        アイドル時間をチェックし、必要に応じて自動スリープを実行します

        Args:
            last_activity_timestamp (Optional[str]): 最後のアクティビティのタイムスタンプ（ISO8601形式）
            check_id (str): チェック ID（トレーサビリティ用）

        Returns:
            Dict[str, Any]: チェック結果とアクションの結果
        """
        try:
            current_status = self.get_ecs_status()

            if current_status.get("status") == "error":
                self._log_audit(
                    action="check_idle_timeout",
                    status="failure",
                    details={"check_id": check_id, "error": current_status.get("message")},
                )
                return current_status

            # ECS が既にスリープしている場合はスキップ
            if current_status.get("running_count", 0) == 0:
                self._log_audit(
                    action="check_idle_timeout",
                    status="already_sleeping",
                    details={"check_id": check_id},
                )
                return {
                    "status": "already_sleeping",
                    "message": "ECS is already in sleep state",
                }

            if not last_activity_timestamp:
                self._log_audit(
                    action="check_idle_timeout",
                    status="skip",
                    details={"check_id": check_id, "reason": "no_activity_timestamp"},
                )
                return {
                    "status": "skip",
                    "message": "No activity timestamp provided",
                }

            # 最後のアクティビティからの経過時間を計算
            last_activity = datetime.fromisoformat(last_activity_timestamp)
            current_time = datetime.utcnow()
            idle_time = (current_time - last_activity).total_seconds()

            if idle_time > self.idle_timeout_seconds:
                # アイドル時間が 2 時間を超えた場合、自動スリープ
                sleep_result = self.stop_ecs(reason="idle_timeout")
                self._log_audit(
                    action="check_idle_timeout",
                    status="auto_slept",
                    details={
                        "check_id": check_id,
                        "idle_time_seconds": int(idle_time),
                        "timeout_seconds": self.idle_timeout_seconds,
                    },
                )
                return {
                    "status": "auto_slept",
                    "message": f"ECS auto-slept after {int(idle_time)} seconds of inactivity",
                    "idle_time_seconds": idle_time,
                    "action_result": sleep_result,
                }
            else:
                remaining_time = self.idle_timeout_seconds - idle_time
                self._log_audit(
                    action="check_idle_timeout",
                    status="active",
                    details={
                        "check_id": check_id,
                        "idle_time_seconds": int(idle_time),
                        "remaining_seconds": int(remaining_time),
                    },
                )
                return {
                    "status": "active",
                    "message": "ECS is still active",
                    "idle_time_seconds": idle_time,
                    "remaining_until_auto_sleep": remaining_time,
                }

        except ValueError as e:
            self._log_audit(
                action="check_idle_timeout",
                status="failure",
                details={"check_id": check_id, "error": f"Invalid timestamp format: {str(e)}"},
            )
            return {
                "status": "error",
                "message": f"Invalid timestamp format: {str(e)}",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error checking auto-sleep: {str(e)}",
            }

    def ensure_ecs_running(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        ECS が実行中であることを確認し、必要に応じて起動します

        Args:
            user_id (Optional[str]): リクエストを送信したユーザーID

        Returns:
            Dict[str, Any]: 実行結果
        """
        current_status = self.get_ecs_status()

        if current_status.get("status") == "error":
            self._log_audit(
                action="ensure_ecs_running",
                status="failure",
                details={"user_id": user_id, "error": current_status.get("message")},
            )
            return current_status

        if current_status.get("running_count", 0) > 0:
            self._log_audit(
                action="ensure_ecs_running",
                status="already_running",
                details={"user_id": user_id, "running_count": current_status.get("running_count", 0)},
            )
            return {
                "status": "already_running",
                "message": "ECS is already running",
                "running_count": current_status.get("running_count", 0),
            }

        # ECS が起動していない場合、起動処理を実行
        return self.start_ecs(user_id=user_id)


# グローバルインスタンス
_ecs_manager: Optional[ECSManager] = None


def get_ecs_manager() -> ECSManager:
    """
    ECSManager のシングルトンインスタンスを取得します

    Returns:
        ECSManager: ECSManager インスタンス
    """
    global _ecs_manager
    if _ecs_manager is None:
        _ecs_manager = ECSManager()
    return _ecs_manager


def lambda_handler_ecs_start(event, context):
    """
    Lambda 関数: ECS を起動するハンドラー

    Args:
        event: Lambda イベント（user_id を含む可能性あり）
        context: Lambda コンテキスト

    Returns:
        dict: API レスポンス
    """
    manager = get_ecs_manager()
    
    # イベントからユーザー ID を抽出
    user_id = None
    if isinstance(event, dict):
        user_id = event.get("user_id") or event.get("userId")
    
    result = manager.start_ecs(user_id=user_id)

    return {
        "statusCode": 200 if result.get("status") != "error" else 500,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }


def lambda_handler_ecs_stop(event, context):
    """
    Lambda 関数: ECS をスリープ状態に移行するハンドラー

    Args:
        event: Lambda イベント（reason を含む可能性あり）
        context: Lambda コンテキスト

    Returns:
        dict: API レスポンス
    """
    manager = get_ecs_manager()
    
    # イベントから理由を抽出
    reason = "manual_stop"
    if isinstance(event, dict):
        reason = event.get("reason", reason)
    
    result = manager.stop_ecs(reason=reason)

    return {
        "statusCode": 200 if result.get("status") != "error" else 500,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }


def lambda_handler_ecs_status(event, context):
    """
    Lambda 関数: ECS ステータスを確認するハンドラー

    Args:
        event: Lambda イベント
        context: Lambda コンテキスト

    Returns:
        dict: API レスポンス
    """
    manager = get_ecs_manager()
    result = manager.get_ecs_status()

    return {
        "statusCode": 200 if result.get("status") != "error" else 500,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }


def lambda_handler_cloudwatch_timeout_check(event, context):
    """
    Lambda 関数: CloudWatch Events によるアイドルタイムアウトチェック（1 時間ごと）

    このハンドラーは CloudWatch Events の定期的なトリガーによって呼び出されます。
    最後のアクティビティから 2 時間経過していないかを確認し、必要に応じて ECS を停止します。

    Args:
        event: CloudWatch Events からのイベント
        context: Lambda コンテキスト

    Returns:
        dict: チェック結果
    """
    manager = get_ecs_manager()
    
    try:
        # システム全体の最後のアクティビティを取得
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table("SystemActivity")
        
        response = table.get_item(Key={"entityId": "global"})
        
        if "Item" not in response:
            # 初めてのチェックの場合、アクティビティを記録
            table.put_item(
                Item={
                    "entityId": "global",
                    "lastActivityAt": datetime.utcnow().isoformat(),
                }
            )
            logger.info("SystemActivity initialized")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "initialized",
                    "message": "SystemActivity initialized on first check"
                }),
                "headers": {"Content-Type": "application/json"},
            }
        
        last_activity = response["Item"].get("lastActivityAt")
        check_id = context.request_id
        
        result = manager.check_and_auto_sleep(
            last_activity_timestamp=last_activity,
            check_id=check_id
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps(result),
            "headers": {"Content-Type": "application/json"},
        }
    
    except Exception as e:
        logger.error(f"Error in CloudWatch timeout check: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": f"Error checking timeout: {str(e)}"
            }),
            "headers": {"Content-Type": "application/json"},
        }
