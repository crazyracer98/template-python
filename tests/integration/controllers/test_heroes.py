"""Integration test: /v2/heroes CRUD routes against the real Postgres stack service."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.oidc import get_current_claims

client = TestClient(app)


@pytest.fixture(autouse=True)
def _authed() -> Iterator[None]:
    """Grant every RBAC role for the duration of each test in this module."""
    settings = get_settings()
    app.dependency_overrides[get_current_claims] = lambda: {
        "sub": "test-user",
        "resource_access": {
            settings.oidc_client_id: {
                "roles": ["viewer", "editor", "maintainer", "security", "detective"]
            }
        },
    }
    yield
    del app.dependency_overrides[get_current_claims]


def test_hero_crud_lifecycle_against_real_postgres() -> None:
    """Create, list, get, update, and delete a hero through the live app and real DB."""
    create_response = client.post(
        "/v2/heroes", json={"name": "Wonder Woman", "powers": ["Super strength"]}
    )
    assert create_response.status_code == 201
    hero_id = create_response.json()["id"]

    try:
        list_response = client.get("/v2/heroes")
        assert list_response.status_code == 200
        assert any(hero["id"] == hero_id for hero in list_response.json())

        get_response = client.get(f"/v2/heroes/{hero_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Wonder Woman"

        update_response = client.patch(f"/v2/heroes/{hero_id}", json={"powers": ["Lasso of truth"]})
        assert update_response.status_code == 200
        assert update_response.json()["powers"] == ["Lasso of truth"]
    finally:
        delete_response = client.delete(f"/v2/heroes/{hero_id}")
        assert delete_response.status_code == 204

    missing_response = client.get(f"/v2/heroes/{hero_id}")
    assert missing_response.status_code == 404
