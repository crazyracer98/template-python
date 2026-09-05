"""Unit test: CRUDInterface's generic get/list/create/update/delete logic.

Uses an in-memory fake Repository and a small standalone Pydantic view, not tied
to Hero/SQLAlchemy at all, to prove the CRUD interface is genuinely generic.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from app.interfaces.base import CRUDInterface, OwnerScope
from app.repositories.filtering import FilterClause, FilterOp, SortClause


@dataclass
class _WidgetRecord:
    """Stand-in for a persisted record, independent of any ORM."""

    id: int
    label: str
    owner_id: str = ""


class _Widget(BaseModel):
    """View returned by the CRUD interface."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    owner_id: str = ""


class _WidgetCreate(BaseModel):
    """View accepted when creating a widget."""

    label: str


class _WidgetUpdate(BaseModel):
    """View accepted when updating a widget."""

    label: str


class _FakeWidgetRepository:
    """In-memory Repository implementation, keyed by id."""

    def __init__(self) -> None:
        """Start with no records and the first id to hand out."""
        self._records: dict[int, _WidgetRecord] = {}
        self._next_id = 1

    def _matching(self, filters: Sequence[FilterClause]) -> list[_WidgetRecord]:
        def matches(record: _WidgetRecord, clause: FilterClause) -> bool:
            value = getattr(record, clause.field)
            if clause.op is FilterOp.EQ:
                return bool(value == clause.value)
            if clause.op is FilterOp.ICONTAINS:
                return str(clause.value).casefold() in str(value).casefold()
            raise NotImplementedError(clause.op)

        return [r for r in self._records.values() if all(matches(r, c) for c in filters)]

    async def get(self, record_id: int) -> _WidgetRecord | None:
        """Return the record with the given id, or None if it doesn't exist."""
        return self._records.get(record_id)

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
    ) -> list[_WidgetRecord]:
        """Return up to `limit` matching records, skipping the first `skip`."""
        matching = self._matching(filters)
        if sort:
            for clause in reversed(sort):
                matching = sorted(
                    matching, key=lambda r: getattr(r, clause.field), reverse=clause.descending
                )
        return matching[skip : skip + limit]

    async def count(self, *, filters: Sequence[FilterClause] = ()) -> int:
        """Return how many records match the given filters."""
        return len(self._matching(filters))

    async def create(self, data: dict[str, Any]) -> _WidgetRecord:
        """Create and return a new record from the given field values."""
        record = _WidgetRecord(id=self._next_id, **data)
        self._records[self._next_id] = record
        self._next_id += 1
        return record

    async def update(self, record_id: int, data: dict[str, Any]) -> _WidgetRecord | None:
        """Update the record with the given id and return it, or None if it doesn't exist."""
        record = self._records.get(record_id)
        if record is None:
            return None
        for field, value in data.items():
            setattr(record, field, value)
        return record

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        return self._records.pop(record_id, None) is not None

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: dict[str, Any]
    ) -> Sequence[_WidgetRecord]:
        """Apply the given field values to every record matching the filters; return them."""
        matching = self._matching(filters)
        for record in matching:
            for field, value in data.items():
                setattr(record, field, value)
        return matching

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[_WidgetRecord]:
        """Delete every record matching the filters; return the records that were deleted."""
        matching = self._matching(filters)
        for record in matching:
            del self._records[record.id]
        return matching


@pytest.fixture
def crud() -> CRUDInterface[_Widget, _WidgetRecord]:
    """Return a CRUDInterface bound to a fresh in-memory fake repository."""
    return CRUDInterface(schema=_Widget, repository=_FakeWidgetRepository())


async def test_create_and_get(crud: CRUDInterface[_Widget, _WidgetRecord]) -> None:
    """create() persists a record and returns it as a view; get() finds it by id."""
    created = await crud.create(_WidgetCreate(label="a"))
    assert created == _Widget(id=created.id, label="a")
    assert await crud.get(created.id) == created


async def test_get_missing_returns_none(crud: CRUDInterface[_Widget, _WidgetRecord]) -> None:
    """get() returns None for an id that doesn't exist."""
    assert await crud.get(999) is None


async def test_list_returns_every_created_record(
    crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """list() returns every created record as a view."""
    await crud.create(_WidgetCreate(label="a"))
    await crud.create(_WidgetCreate(label="b"))
    assert [widget.label for widget in await crud.list()] == ["a", "b"]


async def test_list_applies_filters(crud: CRUDInterface[_Widget, _WidgetRecord]) -> None:
    """list() passes filters through to the repository."""
    await crud.create(_WidgetCreate(label="apple"))
    await crud.create(_WidgetCreate(label="banana"))
    filtered = await crud.list(filters=[FilterClause("label", FilterOp.EQ, "apple")])
    assert [widget.label for widget in filtered] == ["apple"]


async def test_list_applies_sort(crud: CRUDInterface[_Widget, _WidgetRecord]) -> None:
    """list() passes sort clauses through to the repository."""
    await crud.create(_WidgetCreate(label="b"))
    await crud.create(_WidgetCreate(label="a"))
    sorted_widgets = await crud.list(sort=[SortClause("label")])
    assert [widget.label for widget in sorted_widgets] == ["a", "b"]


async def test_count_matches_filters(crud: CRUDInterface[_Widget, _WidgetRecord]) -> None:
    """count() reports how many records match the given filters."""
    await crud.create(_WidgetCreate(label="a"))
    await crud.create(_WidgetCreate(label="b"))
    assert await crud.count() == 2
    assert await crud.count(filters=[FilterClause("label", FilterOp.EQ, "a")]) == 1


async def test_update_applies_only_set_fields(
    crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """update() persists the new value and returns the updated view."""
    created = await crud.create(_WidgetCreate(label="a"))
    updated = await crud.update(created.id, _WidgetUpdate(label="b"))
    assert updated is not None
    assert updated.label == "b"


async def test_update_missing_returns_none(crud: CRUDInterface[_Widget, _WidgetRecord]) -> None:
    """update() returns None for an id that doesn't exist."""
    assert await crud.update(999, _WidgetUpdate(label="b")) is None


async def test_delete(crud: CRUDInterface[_Widget, _WidgetRecord]) -> None:
    """delete() removes the record and reports it existed; a second delete reports False."""
    created = await crud.create(_WidgetCreate(label="a"))
    assert await crud.delete(created.id) is True
    assert await crud.delete(created.id) is False


async def test_update_many_applies_to_every_match(
    crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """update_many() applies the update to every record matching the filters."""
    await crud.create(_WidgetCreate(label="apple"))
    await crud.create(_WidgetCreate(label="apricot"))
    await crud.create(_WidgetCreate(label="banana"))
    updated = await crud.update_many(
        filters=[FilterClause("label", FilterOp.ICONTAINS, "ap")],
        data=_WidgetUpdate(label="updated"),
    )
    assert {widget.label for widget in updated} == {"updated"}
    assert len(updated) == 2
    assert await crud.count() == 3


async def test_delete_many_removes_every_match(
    crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """delete_many() removes every record matching the filters and returns them."""
    await crud.create(_WidgetCreate(label="apple"))
    await crud.create(_WidgetCreate(label="apricot"))
    await crud.create(_WidgetCreate(label="banana"))
    deleted = await crud.delete_many(filters=[FilterClause("label", FilterOp.ICONTAINS, "ap")])
    assert len(deleted) == 2
    assert await crud.count() == 1


# --- OwnerScope: opt-in per-owner scoping ------------------------------------
#
# Two CRUDInterfaces sharing one repository, scoped to different owners, prove
# neither can reach the other's records -- mirroring how a real resource would
# build one CRUDInterface per request from the caller's own claims.


@pytest.fixture
def repository() -> _FakeWidgetRepository:
    """Return a fresh in-memory fake repository, shared by two owner-scoped interfaces."""
    return _FakeWidgetRepository()


@pytest.fixture
def alice_crud(repository: _FakeWidgetRepository) -> CRUDInterface[_Widget, _WidgetRecord]:
    """Return a CRUDInterface scoped to owner "alice", backed by the shared repository."""
    return CRUDInterface(
        schema=_Widget, repository=repository, owner=OwnerScope("owner_id", "alice")
    )


@pytest.fixture
def bob_crud(repository: _FakeWidgetRepository) -> CRUDInterface[_Widget, _WidgetRecord]:
    """Return a CRUDInterface scoped to owner "bob", backed by the shared repository."""
    return CRUDInterface(schema=_Widget, repository=repository, owner=OwnerScope("owner_id", "bob"))


async def test_owner_create_stamps_owner_field_ignoring_input(
    alice_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """create() stamps the owner field from the scope, not from caller input."""
    created = await alice_crud.create(_WidgetCreate(label="a"))
    assert created.owner_id == "alice"


async def test_owner_get_cannot_reach_another_owners_record(
    alice_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """get() returns None for a record that exists but belongs to a different owner."""
    alices = await alice_crud.create(_WidgetCreate(label="a"))
    assert await bob_crud.get(alices.id) is None
    assert await alice_crud.get(alices.id) == alices


async def test_owner_list_only_returns_own_records(
    alice_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """list() only returns the records owned by this interface's scope, filters included."""
    await alice_crud.create(_WidgetCreate(label="apple"))
    await bob_crud.create(_WidgetCreate(label="banana"))
    assert [w.label for w in await alice_crud.list()] == ["apple"]
    assert [w.label for w in await bob_crud.list()] == ["banana"]


async def test_owner_count_only_counts_own_records(
    alice_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """count() only counts records owned by this interface's scope."""
    await alice_crud.create(_WidgetCreate(label="apple"))
    await bob_crud.create(_WidgetCreate(label="banana"))
    assert await alice_crud.count() == 1
    assert await bob_crud.count() == 1


async def test_owner_update_cannot_reach_another_owners_record(
    alice_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """update() returns None (and makes no change) for another owner's record."""
    alices = await alice_crud.create(_WidgetCreate(label="a"))
    assert await bob_crud.update(alices.id, _WidgetUpdate(label="hijacked")) is None
    assert (await alice_crud.get(alices.id)).label == "a"  # type: ignore[union-attr]


async def test_owner_delete_cannot_reach_another_owners_record(
    alice_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """delete() reports False (and deletes nothing) for another owner's record."""
    alices = await alice_crud.create(_WidgetCreate(label="a"))
    assert await bob_crud.delete(alices.id) is False
    assert await alice_crud.get(alices.id) == alices


async def test_owner_update_many_only_matches_own_records(
    alice_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """update_many() only applies to records owned by this interface's scope."""
    await alice_crud.create(_WidgetCreate(label="apple"))
    await bob_crud.create(_WidgetCreate(label="apricot"))
    updated = await bob_crud.update_many(
        filters=[FilterClause("label", FilterOp.ICONTAINS, "ap")],
        data=_WidgetUpdate(label="updated"),
    )
    assert [w.label for w in updated] == ["updated"]
    assert (await alice_crud.get((await alice_crud.list())[0].id)).label == "apple"  # type: ignore[union-attr]


async def test_owner_delete_many_only_matches_own_records(
    alice_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """delete_many() only deletes records owned by this interface's scope."""
    await alice_crud.create(_WidgetCreate(label="apple"))
    await bob_crud.create(_WidgetCreate(label="apricot"))
    deleted = await bob_crud.delete_many(filters=[FilterClause("label", FilterOp.ICONTAINS, "ap")])
    assert len(deleted) == 1
    assert await alice_crud.count() == 1
    assert await bob_crud.count() == 0


# --- OwnerScope(read_scoped=False): open reads, owner-restricted writes ------


@pytest.fixture
def alice_open_reads_crud(
    repository: _FakeWidgetRepository,
) -> CRUDInterface[_Widget, _WidgetRecord]:
    """Return a CRUDInterface scoped to "alice" with reads opened to every owner."""
    return CRUDInterface(
        schema=_Widget,
        repository=repository,
        owner=OwnerScope("owner_id", "alice", read_scoped=False),
    )


@pytest.fixture
def bob_open_reads_crud(
    repository: _FakeWidgetRepository,
) -> CRUDInterface[_Widget, _WidgetRecord]:
    """Return a CRUDInterface scoped to "bob" with reads opened to every owner."""
    return CRUDInterface(
        schema=_Widget,
        repository=repository,
        owner=OwnerScope("owner_id", "bob", read_scoped=False),
    )


async def test_read_scoped_false_lets_every_owner_list_every_record(
    alice_open_reads_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_open_reads_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """list()/count() see every record regardless of owner when read_scoped=False."""
    await alice_open_reads_crud.create(_WidgetCreate(label="apple"))
    await bob_open_reads_crud.create(_WidgetCreate(label="banana"))
    assert {w.label for w in await alice_open_reads_crud.list()} == {"apple", "banana"}
    assert await bob_open_reads_crud.count() == 2


async def test_read_scoped_false_lets_every_owner_get_by_id(
    alice_open_reads_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_open_reads_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """get() finds another owner's record by id when read_scoped=False."""
    alices = await alice_open_reads_crud.create(_WidgetCreate(label="apple"))
    found = await bob_open_reads_crud.get(alices.id)
    assert found == alices


async def test_read_scoped_false_still_blocks_update_of_another_owners_record(
    alice_open_reads_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_open_reads_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """update() still 404s (returns None) for another owner's record, reads aside."""
    alices = await alice_open_reads_crud.create(_WidgetCreate(label="apple"))
    assert await bob_open_reads_crud.update(alices.id, _WidgetUpdate(label="hijacked")) is None
    assert (await alice_open_reads_crud.get(alices.id)).label == "apple"  # type: ignore[union-attr]


async def test_read_scoped_false_still_blocks_delete_of_another_owners_record(
    alice_open_reads_crud: CRUDInterface[_Widget, _WidgetRecord],
    bob_open_reads_crud: CRUDInterface[_Widget, _WidgetRecord],
) -> None:
    """delete() still reports False for another owner's record, reads aside."""
    alices = await alice_open_reads_crud.create(_WidgetCreate(label="apple"))
    assert await bob_open_reads_crud.delete(alices.id) is False
    assert await alice_open_reads_crud.get(alices.id) == alices
