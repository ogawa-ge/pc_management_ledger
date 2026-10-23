from fastapi.routing import APIRoute

from src.main import app


IDEMPOTENT_STATE_CHANGING_ROUTES = {
    ("POST", "/api/pcs"),
    ("POST", "/api/pcs/{pc_id}/return"),
    ("PATCH", "/api/pcs/{pc_id}/status"),
}

NON_PERSISTENT_MUTATING_ROUTES = {
    ("POST", "/api/pcs/parse-specs"),
}


def test_every_mutating_route_has_an_explicit_classification():
    actual_routes = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method in {"POST", "PUT", "PATCH", "DELETE"}
    }

    classified_routes = (
        IDEMPOTENT_STATE_CHANGING_ROUTES | NON_PERSISTENT_MUTATING_ROUTES
    )

    assert actual_routes == classified_routes


def test_persistent_state_changing_routes_are_fixed_to_three_contract_routes():
    assert IDEMPOTENT_STATE_CHANGING_ROUTES == {
        ("POST", "/api/pcs"),
        ("POST", "/api/pcs/{pc_id}/return"),
        ("PATCH", "/api/pcs/{pc_id}/status"),
    }


def test_parse_specs_is_explicitly_non_persistent():
    assert NON_PERSISTENT_MUTATING_ROUTES == {
        ("POST", "/api/pcs/parse-specs"),
    }