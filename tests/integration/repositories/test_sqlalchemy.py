"""Integration test: SQLAlchemyRepository against the real Postgres stack service."""

from app.models.base import async_session_factory
from app.models.hero import Hero
from app.repositories.sqlalchemy import SQLAlchemyRepository


async def test_crud_roundtrip_against_real_postgres() -> None:
    """create/get/list/update/delete all round-trip through a real Postgres session.

    Runs inside one uncommitted session so nothing is left behind afterwards --
    closing the session without committing rolls back everything written here.
    """
    async with async_session_factory() as session:
        repository = SQLAlchemyRepository(session, Hero)

        created = await repository.create({"name": "Iron Man", "powers": ["Powered armor"]})
        assert created.id is not None

        fetched = await repository.get(created.id)
        assert fetched is not None
        assert fetched.name == "Iron Man"

        heroes = await repository.list()
        assert any(hero.id == created.id for hero in heroes)

        updated = await repository.update(created.id, {"powers": ["Repulsor blasts"]})
        assert updated is not None
        assert updated.powers == ["Repulsor blasts"]

        assert await repository.delete(created.id) is True
        assert await repository.get(created.id) is None
        assert await repository.delete(created.id) is False
        assert await repository.update(created.id, {"powers": ["N/A"]}) is None
