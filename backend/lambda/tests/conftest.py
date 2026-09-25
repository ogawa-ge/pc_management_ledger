import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest


LAMBDA_ROOT = Path(__file__).resolve().parents[1]
if str(LAMBDA_ROOT) not in sys.path:
    sys.path.insert(0, str(LAMBDA_ROOT))

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-northeast-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")


@pytest.fixture
def fixed_now():
    return datetime(2026, 9, 25, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def lambda_aws_clients(monkeypatch):
    ecs_client = Mock(name="ecs_client")
    logs_client = Mock(name="logs_client")
    ec2_client = Mock(name="ec2_client")
    dynamodb_resource = Mock(name="dynamodb_resource")
    system_activity_table = Mock(name="system_activity_table")
    dynamodb_resource.Table.return_value = system_activity_table

    clients = {
        "ecs": ecs_client,
        "logs": logs_client,
        "ec2": ec2_client,
    }

    import src.services.ecs_manager as ecs_manager_module

    monkeypatch.setattr(
        ecs_manager_module.boto3,
        "client",
        lambda service_name, **_kwargs: clients[service_name],
    )
    monkeypatch.setattr(
        ecs_manager_module.boto3,
        "resource",
        lambda service_name, **_kwargs: dynamodb_resource
        if service_name == "dynamodb"
        else Mock(name=f"{service_name}_resource"),
    )
    monkeypatch.setattr(ecs_manager_module, "logs_client", logs_client)

    return {
        "ecs": ecs_client,
        "logs": logs_client,
        "ec2": ec2_client,
        "dynamodb": dynamodb_resource,
        "system_activity_table": system_activity_table,
    }


@pytest.fixture
def ecs_manager(lambda_aws_clients):
    from src.services.ecs_manager import ECSManager

    return ECSManager(cluster_name="test-cluster")