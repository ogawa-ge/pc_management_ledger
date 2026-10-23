"""
ログイン時のユーザー登録（POST /api/auth/sync-user）とドメイン判定のテスト
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

LAMBDA_ROOT = Path(__file__).resolve().parents[1] / "lambda"
if str(LAMBDA_ROOT) not in sys.path:
    sys.path.insert(0, str(LAMBDA_ROOT))

from src.services import auth_service  # noqa: E402

ALLOWED_DOMAIN = "example.co.jp"


@pytest.fixture
def users_table(monkeypatch):
    table = Mock()
    dynamodb = Mock()
    dynamodb.Table.return_value = table
    monkeypatch.setattr(auth_service, "dynamodb", dynamodb)
    return table


def return_attributes_as_new_user(table, role="User"):
    def update_item(**kwargs):
        values = kwargs["ExpressionAttributeValues"]
        return {
            "Attributes": {
                "userId": kwargs["Key"]["userId"],
                "email": values[":email"],
                "role": role,
                "createdAt": values[":now"],
                "updatedAt": values[":now"],
            }
        }

    table.update_item.side_effect = update_item


def return_attributes_as_existing_user(table, role):
    def update_item(**kwargs):
        values = kwargs["ExpressionAttributeValues"]
        return {
            "Attributes": {
                "userId": kwargs["Key"]["userId"],
                "email": values[":email"],
                "role": role,
                "createdAt": "2026-01-01T00:00:00+00:00",
                "updatedAt": values[":now"],
            }
        }

    table.update_item.side_effect = update_item


class TestSyncUser:
    def test_new_user_is_created_with_user_role(self, users_table):
        return_attributes_as_new_user(users_table)

        result = auth_service.sync_user("google-sub-001", f"taro@{ALLOWED_DOMAIN}", "Taro")

        assert result == {"userId": "google-sub-001", "role": "User", "created": True}
        users_table.update_item.assert_called_once()
        update_expression = users_table.update_item.call_args.kwargs["UpdateExpression"]
        assert "#role = if_not_exists(#role, :user)" in update_expression
        assert "createdAt = if_not_exists(createdAt, :now)" in update_expression

    def test_existing_admin_keeps_admin_role(self, users_table):
        return_attributes_as_existing_user(users_table, role="Admin")

        result = auth_service.sync_user("google-sub-002", f"hanako@{ALLOWED_DOMAIN}", "Hanako")

        assert result == {"userId": "google-sub-002", "role": "Admin", "created": False}

    def test_email_is_saved_in_lowercase(self, users_table):
        return_attributes_as_new_user(users_table)

        auth_service.sync_user("google-sub-003", "Taro@EXAMPLE.CO.JP", None)

        values = users_table.update_item.call_args.kwargs["ExpressionAttributeValues"]
        assert values[":email"] == f"taro@{ALLOWED_DOMAIN}"

    def test_name_is_not_written_when_missing(self, users_table):
        return_attributes_as_new_user(users_table)

        auth_service.sync_user("google-sub-004", f"jiro@{ALLOWED_DOMAIN}", None)

        update_expression = users_table.update_item.call_args.kwargs["UpdateExpression"]
        assert "#name" not in update_expression

    @pytest.mark.parametrize(
        "user_id, email",
        [("google-sub-005", ""), ("", f"saburo@{ALLOWED_DOMAIN}"), ("  ", f"saburo@{ALLOWED_DOMAIN}")],
    )
    def test_missing_user_id_or_email_raises_value_error(self, users_table, user_id, email):
        with pytest.raises(ValueError):
            auth_service.sync_user(user_id, email, None)

        users_table.update_item.assert_not_called()
