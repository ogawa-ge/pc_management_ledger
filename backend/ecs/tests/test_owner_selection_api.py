from src.main import RequestPrincipal, app, get_request_principal
from src.models.user import User


def test_admin_get_users_returns_camel_case_users(api_client, user_repository_mock):
    user_repository_mock.get_all_users.return_value = [
        User(user_id="user-001", name="Alice", email="alice@example.com", role="User"),
        User(user_id="admin-001", name="Admin", email="admin@example.com", role="Admin"),
    ]

    response = api_client.get("/api/users")

    assert response.status_code == 200
    assert response.json() == [
        {"userId": "user-001", "name": "Alice", "email": "alice@example.com", "role": "User", "createdAt": None, "updatedAt": None},
        {"userId": "admin-001", "name": "Admin", "email": "admin@example.com", "role": "Admin", "createdAt": None, "updatedAt": None},
    ]


def test_unauthenticated_get_users_is_rejected(unauthenticated_client):
    response = unauthenticated_client.get("/api/users")

    assert response.status_code == 401


def test_general_user_get_users_is_rejected(api_client):
    app.dependency_overrides[get_request_principal] = lambda: RequestPrincipal(
        user_id="user-001",
        role="User",
    )

    response = api_client.get("/api/users")

    assert response.status_code == 403