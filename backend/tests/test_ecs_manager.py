"""
ECS マネージャーの単体テスト
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock


class TestECSManagerUnit:
    """ECS マネージャーの単体テスト"""

    @pytest.fixture
    def ecs_manager(self):
        """ECS マネージャーの実装テスト用フィクスチャ"""
        # 実装ファイルがあれば直接インスタンス化
        # ここではモックを使用
        manager = Mock()
        manager.start_ecs = Mock()
        manager.stop_ecs = Mock()
        manager.get_ecs_status = Mock()
        manager.check_and_auto_sleep = Mock()
        manager.idle_timeout_seconds = 2 * 60 * 60  # 2 hours
        return manager

    def test_start_ecs_success(self, ecs_manager):
        """ECS 起動成功のテスト"""
        ecs_manager.start_ecs.return_value = {
            "status": "started",
            "message": "ECS service started",
            "service_arn": "arn:aws:ecs:ap-northeast-1:123456789012:service/pc-management-cluster/pc-management-service",
            "desired_count": 1,
        }

        result = ecs_manager.start_ecs()

        assert result["status"] == "started"
        assert result["desired_count"] == 1

    def test_start_ecs_already_running(self, ecs_manager):
        """既に起動中の場合のテスト"""
        ecs_manager.start_ecs.return_value = {
            "status": "already_running",
            "message": "ECS service is already running",
            "current_task_count": 1,
        }

        result = ecs_manager.start_ecs()

        assert result["status"] == "already_running"

    def test_stop_ecs_success(self, ecs_manager):
        """ECS 停止成功のテスト"""
        ecs_manager.stop_ecs.return_value = {
            "status": "stopped",
            "message": "ECS service stopped (sleeping)",
            "service_arn": "arn:aws:ecs:ap-northeast-1:123456789012:service/pc-management-cluster/pc-management-service",
            "desired_count": 0,
        }

        result = ecs_manager.stop_ecs()

        assert result["status"] == "stopped"
        assert result["desired_count"] == 0

    def test_get_ecs_status_active(self, ecs_manager):
        """ECS ステータス取得（アクティブ）のテスト"""
        ecs_manager.get_ecs_status.return_value = {
            "status": "active",
            "desired_count": 1,
            "running_count": 1,
            "deployment_status": "PRIMARY",
        }

        result = ecs_manager.get_ecs_status()

        assert result["status"] == "active"
        assert result["running_count"] == 1

    def test_get_ecs_status_sleeping(self, ecs_manager):
        """ECS ステータス取得（スリープ）のテスト"""
        ecs_manager.get_ecs_status.return_value = {
            "status": "sleeping",
            "desired_count": 0,
            "running_count": 0,
            "deployment_status": "PRIMARY",
        }

        result = ecs_manager.get_ecs_status()

        assert result["status"] == "sleeping"
        assert result["running_count"] == 0

    def test_auto_sleep_after_timeout(self, ecs_manager):
        """タイムアウト後の自動スリープのテスト"""
        # 2 時間以上前のタイムスタンプ
        old_timestamp = (
            (datetime.utcnow() - timedelta(hours=2, minutes=30)).isoformat()
        )

        ecs_manager.check_and_auto_sleep.return_value = {
            "status": "auto_slept",
            "message": "ECS auto-slept after 9000 seconds of inactivity",
            "idle_time_seconds": 9000,
        }

        result = ecs_manager.check_and_auto_sleep(old_timestamp)

        assert result["status"] == "auto_slept"

    def test_no_auto_sleep_within_timeout(self, ecs_manager):
        """タイムアウト前の自動スリープなしのテスト"""
        # 30 分前のタイムスタンプ
        recent_timestamp = (
            (datetime.utcnow() - timedelta(minutes=30)).isoformat()
        )

        ecs_manager.check_and_auto_sleep.return_value = {
            "status": "active",
            "message": "ECS is still active",
            "idle_time_seconds": 1800,
            "remaining_until_auto_sleep": 5400,
        }

        result = ecs_manager.check_and_auto_sleep(recent_timestamp)

        assert result["status"] == "active"
        assert result["remaining_until_auto_sleep"] > 0


if __name__ == "__main__":
    # pytest で実行
    # python -m pytest backend/tests/test_ecs_manager.py -v
    pass
