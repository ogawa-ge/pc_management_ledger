import pytest

from src.models.user import User


def _make_pc_item(
    pc_id: str,
    *,
    status: str = "InUse",
    owner_id: str | None = "user-001",
    model: str | None = "ThinkPad X1 Carbon",
):
    item = {
        "pcId": pc_id,
        "type": "Notebook",
        "status": status,
        "pcName": f"PC-{pc_id}",
        "cpu": "Intel Core i7",
        "memory": "16.0",
        "storage": "512.0",
        "os": "Windows 11 Pro",
        "manufacturer": "Lenovo",
        "model": model,
        "gpu": "Intel Iris Xe",
        "serialNumber": f"SN-{pc_id}",
        "createdAt": "2026-11-19T00:00:00",
        "updatedAt": "2026-11-19T00:00:00",
    }
    if owner_id is not None:
        item["ownerId"] = owner_id
    return item


def test_get_pcs_resolves_owner_names_and_handles_non_in_use_and_missing(
    api_client, ecs_aws_clients, user_repository_mock
):
    pcs_table = ecs_aws_clients["tables"]["PCs"]
    pcs_table.scan.return_value = {
        "Items": [
            _make_pc_item("N-001", status="InUse", owner_id="user-001"),
            _make_pc_item("N-002", status="InUse", owner_id="user-email-only"),
            _make_pc_item("N-003", status="InUse", owner_id="deleted-user"),
            _make_pc_item("N-004", status="InUse", owner_id=None),
            _make_pc_item("N-005", status="Unused", owner_id="user-001"),
            _make_pc_item("N-006", status="PendingDisposal", owner_id="user-001"),
            _make_pc_item("N-007", status="Disposed", owner_id="user-001"),
        ]
    }
    user_repository_mock.get_all_users.return_value = [
        User(user_id="user-001", name="山田 太郎", email="yamada@example.com", role="User"),
        User(user_id="user-email-only", name=None, email="only@example.com", role="User"),
    ]

    response = api_client.get("/api/pcs")

    assert response.status_code == 200
    body = response.json()
    by_id = {pc["pcId"]: pc for pc in body}
    assert by_id["N-001"]["ownerName"] == "山田 太郎"
    assert by_id["N-002"]["ownerName"] == "only@example.com"
    assert by_id["N-003"]["ownerName"] == "不明なユーザー"
    assert by_id["N-004"]["ownerName"] is None
    assert by_id["N-005"]["ownerName"] is None
    assert by_id["N-006"]["ownerName"] is None
    assert by_id["N-007"]["ownerName"] is None
    user_repository_mock.get_all_users.assert_called_once()


def test_get_pcs_with_status_filter_passes_filter_expression(
    api_client, ecs_aws_clients, user_repository_mock
):
    pcs_table = ecs_aws_clients["tables"]["PCs"]
    pcs_table.scan.return_value = {
        "Items": [_make_pc_item("N-010", status="Unused", owner_id="user-001")]
    }

    response = api_client.get("/api/pcs?status=Unused")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["ownerName"] is None
    pcs_table.scan.assert_called_once_with(
        FilterExpression="#st = :status",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":status": "Unused"},
    )
    user_repository_mock.get_all_users.assert_not_called()


def test_get_pc_by_id_returns_resolved_owner_name(
    api_client, ecs_aws_clients, user_repository_mock
):
    pcs_table = ecs_aws_clients["tables"]["PCs"]
    pcs_table.get_item.return_value = {
        "Item": _make_pc_item("N-001", status="InUse", owner_id="user-001")
    }
    user_repository_mock.get_user_by_id.return_value = User(
        user_id="user-001", name="山田 太郎", email="yamada@example.com", role="User"
    )

    response = api_client.get("/api/pcs/N-001")

    assert response.status_code == 200
    body = response.json()
    assert body["pcId"] == "N-001"
    assert body["ownerName"] == "山田 太郎"
    assert body["model"] == "ThinkPad X1 Carbon"
    user_repository_mock.get_user_by_id.assert_called_once_with("user-001")


def test_get_pc_by_id_returns_unknown_user_when_in_use_owner_missing(
    api_client, ecs_aws_clients, user_repository_mock
):
    pcs_table = ecs_aws_clients["tables"]["PCs"]
    pcs_table.get_item.return_value = {
        "Item": _make_pc_item("N-002", status="InUse", owner_id="missing-user")
    }
    user_repository_mock.get_user_by_id.return_value = None

    response = api_client.get("/api/pcs/N-002")

    assert response.status_code == 200
    assert response.json()["ownerName"] == "不明なユーザー"
    user_repository_mock.get_user_by_id.assert_called_once_with("missing-user")


@pytest.mark.parametrize("status", ["Unused", "PendingDisposal", "Disposed"])
def test_get_pc_by_id_returns_none_owner_name_for_non_in_use(
    api_client, ecs_aws_clients, user_repository_mock, status
):
    pcs_table = ecs_aws_clients["tables"]["PCs"]
    pcs_table.get_item.return_value = {
        "Item": _make_pc_item("N-003", status=status, owner_id="user-001")
    }

    response = api_client.get("/api/pcs/N-003")

    assert response.status_code == 200
    assert response.json()["ownerName"] is None
    user_repository_mock.get_user_by_id.assert_not_called()


def test_get_pc_by_id_returns_none_owner_name_when_owner_id_missing(
    api_client, ecs_aws_clients, user_repository_mock
):
    pcs_table = ecs_aws_clients["tables"]["PCs"]
    pcs_table.get_item.return_value = {
        "Item": _make_pc_item("N-004", status="InUse", owner_id=None)
    }

    response = api_client.get("/api/pcs/N-004")

    assert response.status_code == 200
    assert response.json()["ownerName"] is None
    user_repository_mock.get_user_by_id.assert_not_called()


def test_get_pc_by_id_returns_404_when_not_found(
    api_client, ecs_aws_clients
):
    pcs_table = ecs_aws_clients["tables"]["PCs"]
    pcs_table.get_item.return_value = {}

    response = api_client.get("/api/pcs/N-999")

    assert response.status_code == 404
    assert response.json()["detail"] == "PC not found: N-999"
