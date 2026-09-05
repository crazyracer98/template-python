"""Integration test: SQLAlchemyRepository against the real Postgres stack service."""

from app.models.base import async_session_factory
from app.models.hero import Hero
from app.repositories.filtering import FilterClause, FilterOp, SortClause
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


async def test_filter_sort_and_bulk_actions_against_real_postgres() -> None:
    """list/count/update_many/delete_many honor FilterClause/SortClause against Postgres.

    Runs inside one uncommitted session, same isolation as the roundtrip test above.
    """
    async with async_session_factory() as session:
        repository = SQLAlchemyRepository(session, Hero)

        batman = await repository.create({"name": "Batman", "powers": ["Detective skills"]})
        batgirl = await repository.create({"name": "Batgirl", "powers": ["Detective skills"]})
        superman = await repository.create({"name": "Superman", "powers": ["Flight"]})

        name_filter = [FilterClause("name", FilterOp.ICONTAINS, "bat")]
        assert await repository.count(filters=name_filter) == 2

        matching = await repository.list(filters=name_filter, sort=[SortClause("name")])
        assert [hero.name for hero in matching] == ["Batgirl", "Batman"]

        id_filter = [FilterClause("id", FilterOp.IN, [batman.id, batgirl.id, superman.id])]
        descending = await repository.list(
            filters=id_filter, sort=[SortClause("name", descending=True)]
        )
        assert [hero.name for hero in descending] == ["Superman", "Batman", "Batgirl"]

        updated = await repository.update_many(
            filters=name_filter, data={"powers": ["Martial arts"]}
        )
        assert {hero.id for hero in updated} == {batman.id, batgirl.id}
        assert all(hero.powers == ["Martial arts"] for hero in updated)

        deleted = await repository.delete_many(filters=name_filter)
        assert {hero.id for hero in deleted} == {batman.id, batgirl.id}
        assert await repository.get(batman.id) is None
        assert await repository.get(superman.id) is not None


async def test_every_filter_op_against_real_postgres() -> None:
    """Each FilterOp maps to a working predicate in the real Postgres backend.

    Runs inside one uncommitted session, same isolation as the tests above.
    """
    async with async_session_factory() as session:
        repository = SQLAlchemyRepository(session, Hero)
        low = await repository.create({"name": "FilterOp Low", "powers": ["A"]})
        high = await repository.create({"name": "FilterOp High", "powers": ["A"]})
        ids = [low.id, high.id]

        def by(op: FilterOp, value: object) -> list[FilterClause]:
            return [FilterClause("id", FilterOp.IN, ids), FilterClause("id", op, value)]

        assert [h.id for h in await repository.list(filters=by(FilterOp.EQ, low.id))] == [low.id]
        assert {h.id for h in await repository.list(filters=by(FilterOp.NE, low.id))} == {high.id}
        assert [h.id for h in await repository.list(filters=by(FilterOp.LT, high.id))] == [low.id]
        assert {h.id for h in await repository.list(filters=by(FilterOp.LTE, high.id))} == {
            low.id,
            high.id,
        }
        assert [h.id for h in await repository.list(filters=by(FilterOp.GT, low.id))] == [high.id]
        assert {h.id for h in await repository.list(filters=by(FilterOp.GTE, low.id))} == {
            low.id,
            high.id,
        }
        assert {
            h.id
            for h in await repository.list(
                filters=[
                    FilterClause("name", FilterOp.CONTAINS, "FilterOp"),
                    FilterClause("id", FilterOp.IN, ids),
                ]
            )
        } == {low.id, high.id}
        assert [
            h.id
            for h in await repository.list(
                filters=[FilterClause("name", FilterOp.REGEX, "^FilterOp Low$")]
            )
        ] == [low.id]
