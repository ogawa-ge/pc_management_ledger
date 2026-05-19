"""
ECS 自動スリープおよび起動ロジック

このモジュールは、AWS ECS タスクの自動スリープ/起動を管理します。
- ユーザーが資産管理機能にアクセスする際に ECS を起動
- 2 時間のアイドル時間後に自動的にスリープ状態に遷移
"""

import boto3
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from botocore.exceptions import ClientError


class ECSManager:
    """ECS タスクの起動・停止・スリープ管理を行うクラス"""

    def __init__(self, cluster_name: str = "pc-management-cluster"):
        """
        ECSManager を初期化します

        Args:
            cluster_name (str): ECS クラスター名
        """
        self.ecs_client = boto3.client("ecs")
        self.cluster_name = cluster_name
        self.task_definition = "pc-management-ecs-task"
        # ECS のスリープを実現するため、タスク数を 0 に設定する状態を「スリープ」と定義
        self.sleep_task_count = 0
        self.active_task_count = 1
        self.idle_timeout_seconds = 2 * 60 * 60  # 2 hours

    def start_ecs(self) -> Dict[str, Any]:
        """
        ECS タスクを起動します（スリープ状態から復帰）

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

            return {
                "status": "started",
                "message": "ECS service started",
                "service_arn": update_response["service"]["serviceArn"],
                "desired_count": self.active_task_count,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except ClientError as e:
            return {
                "status": "error",
                "message": f"Failed to start ECS: {str(e)}",
                "error_code": e.response["Error"]["Code"],
            }

    def stop_ecs(self) -> Dict[str, Any]:
        """
        ECS タスクをスリープ状態にします（スケールダウン）

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

            return {
                "status": "stopped",
                "message": "ECS service stopped (sleeping)",
                "service_arn": update_response["service"]["serviceArn"],
                "desired_count": self.sleep_task_count,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except ClientError as e:
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
        self, last_activity_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        アイドル時間をチェックし、必要に応じて自動スリープを実行します

        Args:
            last_activity_timestamp (Optional[str]): 最後のアクティビティのタイムスタンプ（ISO8601形式）

        Returns:
            Dict[str, Any]: チェック結果とアクションの結果
        """
        try:
            current_status = self.get_ecs_status()

            if current_status.get("status") == "error":
                return current_status

            # ECS が既にスリープしている場合はスキップ
            if current_status.get("running_count", 0) == 0:
                return {
                    "status": "already_sleeping",
                    "message": "ECS is already in sleep state",
                }

            if not last_activity_timestamp:
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
                sleep_result = self.stop_ecs()
                return {
                    "status": "auto_slept",
                    "message": f"ECS auto-slept after {idle_time} seconds of inactivity",
                    "idle_time_seconds": idle_time,
                    "action_result": sleep_result,
                }
            else:
                remaining_time = self.idle_timeout_seconds - idle_time
                return {
                    "status": "active",
                    "message": "ECS is still active",
                    "idle_time_seconds": idle_time,
                    "remaining_until_auto_sleep": remaining_time,
                }

        except ValueError as e:
            return {
                "status": "error",
                "message": f"Invalid timestamp format: {str(e)}",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error checking auto-sleep: {str(e)}",
            }

    def ensure_ecs_running(self) -> Dict[str, Any]:
        """
        ECS が実行中であることを確認し、必要に応じて起動します

        Returns:
            Dict[str, Any]: 実行結果
        """
        current_status = self.get_ecs_status()

        if current_status.get("status") == "error":
            return current_status

        if current_status.get("running_count", 0) > 0:
            return {
                "status": "already_running",
                "message": "ECS is already running",
                "running_count": current_status.get("running_count", 0),
            }

        # ECS が起動していない場合、起動処理を実行
        return self.start_ecs()


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
        event: Lambda イベント
        context: Lambda コンテキスト

    Returns:
        dict: API レスポンス
    """
    manager = get_ecs_manager()
    result = manager.start_ecs()

    return {
        "statusCode": 200,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }


def lambda_handler_ecs_stop(event, context):
    """
    Lambda 関数: ECS をスリープ状態に移行するハンドラー

    Args:
        event: Lambda イベント
        context: Lambda コンテキスト

    Returns:
        dict: API レスポンス
    """
    manager = get_ecs_manager()
    result = manager.stop_ecs()

    return {
        "statusCode": 200,
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
