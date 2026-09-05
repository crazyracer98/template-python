"""Unit test: /crud/v1/heroes/v2/json CRUD routes, with the Hero repository faked out."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.config import get_settings
from app.crud_1.heroes.heroes_v2 import get_hero_crud
from app.main import app
from app.models.hero import Hero as HeroModel
from app.oidc import get_current_claims
from app.repositories.memory import InMemoryRepository

from .conftest import override_hero_crud as _override_crud

client = TestClient(app)


@contextmanager
def _authed_as(sub: str) -> Iterator[None]:
    """Override get_current_claims to authenticate as `sub`, with every RBAC role.

    Restores whatever override was in place on exit, so this can nest inside the
    `authed` fixture (tests/unit/conftest.py) without clobbering it.
    """
    settings = get_settings()
    previous = app.dependency_overrides.get(get_current_claims)
    app.dependency_overrides[get_current_claims] = lambda: {
        "sub": sub,
        "resource_access": {
            settings.oidc_client_id: {
                "roles": ["viewer", "editor", "maintainer", "security", "detective"]
            }
        },
    }
    try:
        yield
    finally:
        if previous is None:
            del app.dependency_overrides[get_current_claims]
        else:
            app.dependency_overrides[get_current_claims] = previous


def test_hero_crud_lifecycle(authed: None) -> None:
    """Create, list, get, update, and delete a hero through the HTTP routes."""
    # One repository instance shared across every request in this test -- FastAPI
    # calls the override afresh per request, so a per-call repository would silently
    # discard state between requests.
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = _override_crud(repository)
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
    app.dependency_overrides[get_hero_crud] = _override_crud(InMemoryRepository(HeroModel))
    try:
        response = client.get("/crud/v1/heroes/v2/json", params={"id": 999})
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_update_missing_hero_returns_404(authed: None) -> None:
    """PATCH /crud/v1/heroes/v2/json?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = _override_crud(InMemoryRepository(HeroModel))
    try:
        response = client.patch(
            "/crud/v1/heroes/v2/json", params={"id": 999}, json={"name": "Nobody"}
        )
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_delete_missing_hero_returns_404(authed: None) -> None:
    """DELETE /crud/v1/heroes/v2/json?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = _override_crud(InMemoryRepository(HeroModel))
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


# --- Ownership: reads open to everyone, writes restricted to the creator -----


def test_hero_create_stamps_owner_id_from_claims(authed: None) -> None:
    """create() stamps owner_id from the caller's own claims, ignoring any client input."""
    app.dependency_overrides[get_hero_crud] = _override_crud(InMemoryRepository(HeroModel))
    try:
        response = client.post(
            "/crud/v1/heroes/v2/json", json={"name": "Spider-Man", "powers": ["Wall-crawling"]}
        )
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.json()["owner_id"] == "test-user"


def test_any_caller_can_list_and_get_another_owners_hero(authed: None) -> None:
    """Bob can list/get a hero Alice ("test-user") created -- reads are open to everyone."""
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = _override_crud(repository)
    try:
        alices_hero = client.post(
            "/crud/v1/heroes/v2/json", json={"name": "Storm", "powers": ["Weather control"]}
        ).json()

        with _authed_as("bob"):
            list_response = client.get("/crud/v1/heroes/v2/json")
            assert any(hero["id"] == alices_hero["id"] for hero in list_response.json())

            get_response = client.get("/crud/v1/heroes/v2/json", params={"id": alices_hero["id"]})
            assert get_response.status_code == 200
    finally:
        del app.dependency_overrides[get_hero_crud]


def test_caller_cannot_update_another_owners_hero(authed: None) -> None:
    """Bob's PATCH by id 404s (and makes no change) for a hero Alice created."""
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = _override_crud(repository)
    try:
        alices_hero = client.post(
            "/crud/v1/heroes/v2/json", json={"name": "Storm", "powers": ["Weather control"]}
        ).json()

        with _authed_as("bob"):
            response = client.patch(
                "/crud/v1/heroes/v2/json",
                params={"id": alices_hero["id"]},
                json={"powers": ["Hijacked"]},
            )
            assert response.status_code == 404

        unchanged = client.get("/crud/v1/heroes/v2/json", params={"id": alices_hero["id"]})
        assert unchanged.json()["powers"] == ["Weather control"]
    finally:
        del app.dependency_overrides[get_hero_crud]


def test_caller_cannot_delete_another_owners_hero(authed: None) -> None:
    """Bob's DELETE by id 404s (and deletes nothing) for a hero Alice created."""
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = _override_crud(repository)
    try:
        alices_hero = client.post(
            "/crud/v1/heroes/v2/json", json={"name": "Storm", "powers": ["Weather control"]}
        ).json()

        with _authed_as("bob"):
            response = client.delete("/crud/v1/heroes/v2/json", params={"id": alices_hero["id"]})
            assert response.status_code == 404

        still_there = client.get("/crud/v1/heroes/v2/json", params={"id": alices_hero["id"]})
        assert still_there.status_code == 200
    finally:
        del app.dependency_overrides[get_hero_crud]


def test_caller_bulk_update_and_delete_do_not_reach_another_owners_hero(authed: None) -> None:
    """Bob's bulk PATCH/DELETE, filtered broadly, matches none of Alice's heroes."""
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = _override_crud(repository)
    try:
        client.post(
            "/crud/v1/heroes/v2/json",
            json={"name": "Shared Name Test", "powers": ["Weather control"]},
        )

        with _authed_as("bob"):
            bulk_update = client.patch(
                "/crud/v1/heroes/v2/json",
                params={"name__icontains": "Shared Name Test"},
                json={"powers": ["Hijacked"]},
            )
            assert bulk_update.status_code == 200
            assert bulk_update.json()["matched"] == 0

            bulk_delete = client.delete(
                "/crud/v1/heroes/v2/json", params={"name__icontains": "Shared Name Test"}
            )
            assert bulk_delete.status_code == 200
            assert bulk_delete.json()["matched"] == 0

        # Still there and unchanged -- Bob's bulk actions matched nothing of Alice's.
        still_there = client.get(
            "/crud/v1/heroes/v2/json", params={"name__icontains": "Shared Name Test"}
        )
        assert len(still_there.json()) == 1
        assert still_there.json()[0]["powers"] == ["Weather control"]
    finally:
        del app.dependency_overrides[get_hero_crud]
