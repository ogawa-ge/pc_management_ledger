from unittest.mock import Mock, call

from src.models.user import UserRepository


def test_empty_users_is_successful_empty_array(api_client, user_repository_mock):
    user_repository_mock.get_all_users.return_value = []

    response = api_client.get("/api/users")

    assert response.status_code == 200
    assert response.json() == []


def test_repository_reads_all_pages_and_deduplicates_user_id():
    table = Mock()
    table.scan.side_effect = [
        {
            "Items": [
                {"userId": "user-001", "name": "Alice", "email": "alice@example.com", "role": "User"},
            ],
            "LastEvaluatedKey": {"userId": "user-001"},
        },
        {
            "Items": [
                {"userId": "user-001", "name": "Duplicate", "email": "duplicate@example.com", "role": "User"},
                {"userId": "user-002", "role": "User"},
            ],
        },
    ]

    users = UserRepository(table).get_all_users()

    assert [user.user_id for user in users] == ["user-001", "user-002"]
    assert users[1].name is None
    assert users[1].email is None
    assert table.scan.call_args_list == [
        call(),
        call(ExclusiveStartKey={"userId": "user-001"}),
    ]


def test_dynamodb_list_failure_is_not_converted_to_empty_array(api_client, user_repository_mock):
    user_repository_mock.get_all_users.side_effect = RuntimeError("DynamoDB unavailable")

    response = api_client.get("/api/users")

    assert response.status_code == 503
    assert response.json() == {"detail": "Failed to get users"}


def test_owner_recheck_failure_does_not_save(api_client, user_repository_mock, pc_create_mock):
    user_repository_mock.get_user_by_id.side_effect = RuntimeError("DynamoDB unavailable")

    response = api_client.post(
        "/api/pcs",
        json={"ownerId": "user-001", "specsText": "specs", "pcType": "N"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Failed to verify owner"}
    pc_create_mock.assert_not_called()