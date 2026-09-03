"""Unit test: /heroes CRUD routes, with the Hero repository faked out."""

from typing import Any

from fastapi.testclient import TestClient

from app.controllers.heroes import get_hero_crud
from app.crud.base import CRUDInterface
from app.main import app
from app.models.hero import Hero as HeroModel
from app.views.hero import Hero

client = TestClient(app)


class _FakeHeroRepository:
    """In-memory stand-in for SQLAlchemyRepository, backed by real Hero instances."""

    def __init__(self) -> None:
        """Start with no heroes and the first id to hand out."""
        self._heroes: dict[int, HeroModel] = {}
        self._next_id = 1

    async def get(self, record_id: int) -> HeroModel | None:
        """Return the hero with the given id, or None if it doesn't exist."""
        return self._heroes.get(record_id)

    async def list(self, *, skip: int = 0, limit: int = 100) -> list[HeroModel]:
        """Return up to `limit` heroes, skipping the first `skip`."""
        return list(self._heroes.values())[skip : skip + limit]

    async def create(self, data: dict[str, Any]) -> HeroModel:
        """Create and return a new hero from the given field values."""
        hero = HeroModel(id=self._next_id, **data)
        self._heroes[self._next_id] = hero
        self._next_id += 1
        return hero

    async def update(self, record_id: int, data: dict[str, Any]) -> HeroModel | None:
        """Update the hero with the given id and return it, or None if it doesn't exist."""
        hero = self._heroes.get(record_id)
        if hero is None:
            return None
        for field, value in data.items():
            setattr(hero, field, value)
        return hero

    async def delete(self, record_id: int) -> bool:
        """Delete the hero with the given id; return whether it existed."""
        return self._heroes.pop(record_id, None) is not None


def _override_crud(
    repository: _FakeHeroRepository,
) -> CRUDInterface[Hero, HeroModel]:
    """Build a CRUDInterface backed by the given fake repository."""
    return CRUDInterface(schema=Hero, repository=repository)


def test_hero_crud_lifecycle() -> None:
    """Create, list, get, update, and delete a hero through the HTTP routes."""
    # One repository instance shared across every request in this test -- FastAPI
    # calls the override afresh per request, so a per-call repository would silently
    # discard state between requests.
    repository = _FakeHeroRepository()
    app.dependency_overrides[get_hero_crud] = lambda: _override_crud(repository)
    try:
        create_response = client.post(
            "/heroes", json={"name": "Spider-Man", "superpower": "Wall-crawling"}
        )
        assert create_response.status_code == 201
        hero_id = create_response.json()["id"]

        list_response = client.get("/heroes")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        get_response = client.get(f"/heroes/{hero_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Spider-Man"

        update_response = client.patch(f"/heroes/{hero_id}", json={"superpower": "Web-slinging"})
        assert update_response.status_code == 200
        assert update_response.json()["superpower"] == "Web-slinging"

        delete_response = client.delete(f"/heroes/{hero_id}")
        assert delete_response.status_code == 204

        missing_response = client.get(f"/heroes/{hero_id}")
        assert missing_response.status_code == 404
    finally:
        del app.dependency_overrides[get_hero_crud]


def test_get_missing_hero_returns_404() -> None:
    """GET /heroes/{id} for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = lambda: _override_crud(_FakeHeroRepository())
    try:
        response = client.get("/heroes/999")
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_update_missing_hero_returns_404() -> None:
    """PATCH /heroes/{id} for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = lambda: _override_crud(_FakeHeroRepository())
    try:
        response = client.patch("/heroes/999", json={"name": "Nobody"})
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_delete_missing_hero_returns_404() -> None:
    """DELETE /heroes/{id} for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = lambda: _override_crud(_FakeHeroRepository())
    try:
        response = client.delete("/heroes/999")
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404
