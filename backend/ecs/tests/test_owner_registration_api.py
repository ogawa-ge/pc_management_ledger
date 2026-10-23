from src.main import RequestPrincipal, app, get_request_principal
from src.models.user import User


PC_RESPONSE = {
    "pcId": "N-001",
    "ownerId": "user-001",
    "type": "N",
    "status": "Unused",
    "model": "Test Model",
    "createdAt": "2026-08-19T00:00:00",
    "updatedAt": "2026-08-19T00:00:00",
}

HEADERS = {"Idempotency-Key": "11111111-1111-4111-8111-111111111111"}


def test_admin_can_register_pc_for_existing_owner(api_client, user_repository_mock, pc_create_mock):
    user_repository_mock.get_user_by_id.return_value = User(
        user_id="user-001", name="Alice", email="alice@example.com", role="User"
    )
    pc_create_mock.return_value = PC_RESPONSE

    response = api_client.post(
        "/api/pcs",
        json={"ownerId": "user-001", "specsText": "specs", "pcType": "N"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["ownerId"] == "user-001"
    pc_create_mock.assert_called_once_with(
        "user-001", "specs", "N", HEADERS["Idempotency-Key"],
        "request-owner", "2026-09-25T00:00:00+00:00"
    )


def test_general_user_can_register_pc_for_self(api_client, user_repository_mock, pc_create_mock):
    app.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        user_id="user-001", role="User"
    )
    user_repository_mock.get_user_by_id.return_value = User(
        user_id="user-001", name="Alice", email="alice@example.com", role="User"
    )
    pc_create_mock.return_value = PC_RESPONSE

    response = api_client.post(
        "/api/pcs",
        json={"ownerId": "user-001", "specsText": "specs", "pcType": "N"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    pc_create_mock.assert_called_once()


def test_missing_owner_does_not_save(api_client, pc_create_mock):
    response = api_client.post(
        "/api/pcs",
        json={"specsText": "specs", "pcType": "N"},
        headers=HEADERS,
    )

    assert response.status_code == 422
    pc_create_mock.assert_not_called()


def test_unknown_owner_does_not_save(api_client, user_repository_mock, pc_create_mock):
    user_repository_mock.get_user_by_id.return_value = None

    response = api_client.post(
        "/api/pcs",
        json={"ownerId": "missing", "specsText": "specs", "pcType": "N"},
        headers=HEADERS,
    )

    assert response.status_code == 404
    pc_create_mock.assert_not_called()


def test_general_user_cannot_register_for_other_owner(api_client, user_repository_mock, pc_create_mock):
    app.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        user_id="user-001", role="User"
    )
    user_repository_mock.get_user_by_id.return_value = User(
        user_id="user-002", name="Bob", email="bob@example.com", role="User"
    )

    response = api_client.post(
        "/api/pcs",
        json={"ownerId": "user-002", "specsText": "specs", "pcType": "N"},
        headers=HEADERS,
    )

    assert response.status_code == 403
    pc_create_mock.assert_not_called()


def test_unauthenticated_registration_does_not_save(unauthenticated_client, pc_create_mock):
    response = unauthenticated_client.post(
        "/api/pcs",
        json={"ownerId": "user-001", "specsText": "specs", "pcType": "N"},
        headers=HEADERS,
    )

    assert response.status_code == 401
    pc_create_mock.assert_not_called()