"""Unit test: InMemoryRepository's filter/sort/bulk logic, one case per FilterOp.

Uses the Hero model directly (not mocked) since InMemoryRepository is generic over
any IdentifiedBase subclass and Hero is already the example resource in this repo.
"""

import pytest

from app.models.hero import Hero
from app.repositories.filtering import FilterClause, FilterOp, SortClause
from app.repositories.memory import InMemoryRepository


@pytest.fixture
async def repository() -> InMemoryRepository[Hero]:
    """Return a fresh InMemoryRepository seeded with three heroes."""
    repo = InMemoryRepository(Hero)
    await repo.create({"name": "Batman", "powers": ["Detective skills"]})
    await repo.create({"name": "Batgirl", "powers": ["Detective skills"]})
    await repo.create({"name": "Superman", "powers": ["Flight"]})
    return repo


async def test_filter_eq(repository: InMemoryRepository[Hero]) -> None:
    """EQ matches only records with the exact field value."""
    matching = await repository.list(filters=[FilterClause("name", FilterOp.EQ, "Batman")])
    assert [hero.name for hero in matching] == ["Batman"]


async def test_filter_ne(repository: InMemoryRepository[Hero]) -> None:
    """NE matches every record except those with the exact field value."""
    matching = await repository.list(filters=[FilterClause("name", FilterOp.NE, "Batman")])
    assert {hero.name for hero in matching} == {"Batgirl", "Superman"}


async def test_filter_lt_lte_gt_gte(repository: InMemoryRepository[Hero]) -> None:
    """LT/LTE/GT/GTE compare against the given value."""
    heroes = await repository.list()
    ids = sorted(hero.id for hero in heroes)
    lt = await repository.list(filters=[FilterClause("id", FilterOp.LT, ids[1])])
    assert [hero.id for hero in lt] == [ids[0]]
    lte = await repository.list(filters=[FilterClause("id", FilterOp.LTE, ids[1])])
    assert sorted(hero.id for hero in lte) == ids[:2]
    gt = await repository.list(filters=[FilterClause("id", FilterOp.GT, ids[1])])
    assert [hero.id for hero in gt] == [ids[2]]
    gte = await repository.list(filters=[FilterClause("id", FilterOp.GTE, ids[1])])
    assert sorted(hero.id for hero in gte) == ids[1:]


async def test_filter_in(repository: InMemoryRepository[Hero]) -> None:
    """IN matches records whose field value is a member of the given collection."""
    matching = await repository.list(
        filters=[FilterClause("name", FilterOp.IN, ["Batman", "Superman"])]
    )
    assert {hero.name for hero in matching} == {"Batman", "Superman"}


async def test_filter_contains(repository: InMemoryRepository[Hero]) -> None:
    """CONTAINS matches a case-sensitive substring."""
    matching = await repository.list(filters=[FilterClause("name", FilterOp.CONTAINS, "Bat")])
    assert {hero.name for hero in matching} == {"Batman", "Batgirl"}
    assert await repository.list(filters=[FilterClause("name", FilterOp.CONTAINS, "bat")]) == []


async def test_filter_icontains(repository: InMemoryRepository[Hero]) -> None:
    """ICONTAINS matches a case-insensitive substring."""
    matching = await repository.list(filters=[FilterClause("name", FilterOp.ICONTAINS, "bat")])
    assert {hero.name for hero in matching} == {"Batman", "Batgirl"}


async def test_filter_regex(repository: InMemoryRepository[Hero]) -> None:
    """REGEX matches records whose field value matches the given pattern."""
    matching = await repository.list(filters=[FilterClause("name", FilterOp.REGEX, "^Bat.*")])
    assert {hero.name for hero in matching} == {"Batman", "Batgirl"}


async def test_sort_ascending_and_descending(repository: InMemoryRepository[Hero]) -> None:
    """Sorting orders by field value, reversed when descending is set."""
    ascending = await repository.list(sort=[SortClause("name")])
    assert [hero.name for hero in ascending] == ["Batgirl", "Batman", "Superman"]
    descending = await repository.list(sort=[SortClause("name", descending=True)])
    assert [hero.name for hero in descending] == ["Superman", "Batman", "Batgirl"]


async def test_count_matches_filters(repository: InMemoryRepository[Hero]) -> None:
    """count() reports how many records match the given filters."""
    assert await repository.count() == 3
    assert await repository.count(filters=[FilterClause("name", FilterOp.ICONTAINS, "bat")]) == 2


async def test_get_update_and_delete_by_id(repository: InMemoryRepository[Hero]) -> None:
    """get()/update()/delete() (single-record) round-trip by id.

    Exercised directly here since Hero's own real HTTP routes no longer call these
    for update/delete -- app.crud_1.heroes.heroes_v2.get_hero_crud always sets an
    OwnerScope, which routes CRUDInterface.update/delete through update_many/
    delete_many instead (see app.interfaces.base.OwnerScope's docstring).
    """
    heroes = await repository.list()
    batman = next(hero for hero in heroes if hero.name == "Batman")

    fetched = await repository.get(batman.id)
    assert fetched is not None
    assert fetched.name == "Batman"

    updated = await repository.update(batman.id, {"powers": ["Martial arts"]})
    assert updated is not None
    assert updated.powers == ["Martial arts"]

    assert await repository.delete(batman.id) is True
    assert await repository.get(batman.id) is None
    assert await repository.delete(batman.id) is False
    assert await repository.update(batman.id, {"powers": ["N/A"]}) is None


async def test_update_many_applies_to_every_match(repository: InMemoryRepository[Hero]) -> None:
    """update_many() applies the update to every record matching the filters."""
    updated = await repository.update_many(
        filters=[FilterClause("name", FilterOp.ICONTAINS, "bat")],
        data={"powers": ["Martial arts"]},
    )
    assert {hero.name for hero in updated} == {"Batman", "Batgirl"}
    assert all(hero.powers == ["Martial arts"] for hero in updated)
    assert await repository.count() == 3


async def test_delete_many_removes_every_match(repository: InMemoryRepository[Hero]) -> None:
    """delete_many() removes every record matching the filters and returns them."""
    deleted = await repository.delete_many(
        filters=[FilterClause("name", FilterOp.ICONTAINS, "bat")]
    )
    assert {hero.name for hero in deleted} == {"Batman", "Batgirl"}
    assert await repository.count() == 1
