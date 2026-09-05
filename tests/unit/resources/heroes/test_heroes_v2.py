"""Unit test: /crud/v1/heroes/v2/json CRUD routes, with the Hero repository faked out."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.crud.base import CRUDInterface
from app.main import app
from app.models.hero import Hero as HeroModel
from app.oidc import get_current_claims
from app.repositories.memory import InMemoryRepository
from app.resources.heroes.heroes_v2 import get_hero_crud
from app.views.hero_v2 import HeroV2

client = TestClient(app)


def _override_crud(repository: InMemoryRepository[HeroModel]) -> CRUDInterface[HeroV2, HeroModel]:
    """Build a CRUDInterface backed by the given in-memory repository."""
    return CRUDInterface(schema=HeroV2, repository=repository)


def test_hero_crud_lifecycle(authed: None) -> None:
    """Create, list, get, update, and delete a hero through the HTTP routes."""
    # One repository instance shared across every request in this test -- FastAPI
    # calls the override afresh per request, so a per-call repository would silently
    # discard state between requests.
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = lambda: _override_crud(repository)
    try:
        create_response = client.post(
            "/crud/v1/heroes/v2/json", json={"name": "Spider-Man", "powers": ["Wall-crawling"]}
        )
        assert create_response.status_code == 201
        hero_id = create_response.json()["id"]

        list_response = client.get("/crud/v1/heroes/v2/json")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        get_response = client.get("/crud/v1/heroes/v2/json", params={"id": hero_id})
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Spider-Man"

        update_response = client.patch(
            "/crud/v1/heroes/v2/json", params={"id": hero_id}, json={"powers": ["Web-slinging"]}
        )
        assert update_response.status_code == 200
        assert update_response.json()["powers"] == ["Web-slinging"]

        delete_response = client.delete("/crud/v1/heroes/v2/json", params={"id": hero_id})
        assert delete_response.status_code == 204

        missing_response = client.get("/crud/v1/heroes/v2/json", params={"id": hero_id})
        assert missing_response.status_code == 404
    finally:
        del app.dependency_overrides[get_hero_crud]


def test_get_missing_hero_returns_404(authed: None) -> None:
    """GET /crud/v1/heroes/v2/json?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = lambda: _override_crud(InMemoryRepository(HeroModel))
    try:
        response = client.get("/crud/v1/heroes/v2/json", params={"id": 999})
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_update_missing_hero_returns_404(authed: None) -> None:
    """PATCH /crud/v1/heroes/v2/json?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = lambda: _override_crud(InMemoryRepository(HeroModel))
    try:
        response = client.patch(
            "/crud/v1/heroes/v2/json", params={"id": 999}, json={"name": "Nobody"}
        )
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_delete_missing_hero_returns_404(authed: None) -> None:
    """DELETE /crud/v1/heroes/v2/json?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = lambda: _override_crud(InMemoryRepository(HeroModel))
    try:
        response = client.delete("/crud/v1/heroes/v2/json", params={"id": 999})
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_hero_routes_require_auth() -> None:
    """GET /crud/v1/heroes/v2/json with no Authorization header is rejected with 401."""
    response = client.get("/crud/v1/heroes/v2/json")
    assert response.status_code == 401


def test_hero_create_requires_write_role() -> None:
    """POST /crud/v1/heroes/v2/json with only the viewer role is rejected with 403."""
    settings = get_settings()
    app.dependency_overrides[get_current_claims] = lambda: {
        "sub": "viewer-user",
        "resource_access": {settings.oidc_client_id: {"roles": ["viewer"]}},
    }
    try:
        response = client.post("/crud/v1/heroes/v2/json", json={"name": "X", "powers": ["Y"]})
    finally:
        del app.dependency_overrides[get_current_claims]
    assert response.status_code == 403
