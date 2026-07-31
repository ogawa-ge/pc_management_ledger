"""
テストユーティリティと共通フィクスチャ
"""

import pytest
from unittest.mock import Mock, MagicMock
import os


@pytest.fixture(autouse=True)
def mock_aws_environment():
    """AWS 環境変数のモック"""
    os.environ["AWS_REGION"] = "ap-northeast-1"
    os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:8000"
    yield
    # クリーンアップは省略（テスト後も環境変数は残る）


@pytest.fixture
def dynamodb_mock():
    """DynamoDB クライアントのモック"""
    mock_client = Mock()
    mock_resource = Mock()

    # テーブルモック
    mock_table = Mock()
    mock_resource.Table.return_value = mock_table

    return {
        "client": mock_client,
        "resource": mock_resource,
        "table": mock_table,
    }


@pytest.fixture
def gemini_api_mock():
    """Gemini API クライアントのモック"""
    mock_client = Mock()

    # レスポンスモック
    mock_response = Mock()
    mock_response.text = """
    {
        "cpu": "Intel Core i7-1260P",
        "memory": "16GB",
        "storage": "512GB SSD",
        "os": "Windows 11 Pro"
    }
    """

    mock_client.generate_content.return_value = mock_response

    return mock_client


@pytest.fixture
def auth_mock():
    """認証関連のモック"""
    mock_auth = Mock()

    mock_auth.get_user_from_token.return_value = {
        "user_id": "user-001",
        "email": "user@example.com",
        "role": "user",
    }

    return mock_auth
