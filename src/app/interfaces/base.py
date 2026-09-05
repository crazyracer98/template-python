"""Generic CRUD interface.

Feed it a Pydantic view (app.views) and a Repository (app.repositories) to persist
it through, and it exposes CRUD operations that speak entirely in terms of that
view -- converting to and from the backing ORM model via the view's own
`from_attributes` support (see app.views.base.ORMView) is the only place that
conversion happens, so a new resource never needs its own CRUD class.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from app.repositories.base import Repository
from app.repositories.filtering import FilterClause, FilterOp, SortClause


@dataclass(frozen=True)
class OwnerScope:
    """Opt-in per-user/per-tenant scoping for a CRUDInterface.

    Restricts `update`/`delete`/`update_many`/`delete_many` (always) and
    `get`/`list`/`count` (when `read_scoped` is True, the default) to records
    where `field == value` -- typically `value` is the caller's claims["sub"],
    resolved at CRUD-dependency-build time (see app.crud_1.heroes.get_hero_crud
    for the per-request build pattern this attaches to) -- and stamps `field`
    with `value` on create so a caller can't create a record owned by someone
    else.

    `read_scoped=False` opens reads to every caller while keeping writes
    owner-restricted: every authenticated caller sees every record via `get`/
    `list`/`count`, but can only `update`/`delete` (single or bulk) the records
    they themselves created -- see `app.crud_1.heroes.heroes_v2` for why Hero
    uses this shape rather than the fully-scoped default.

    Deliberately a CRUDInterface-level concept, not a Repository one: passing
    `owner=None` (the default) changes nothing, so a resource that never opts
    in is unaffected, and app.repositories stays unaware "ownership" exists at
    all -- see docs/adrs/0011-owner-scoped-crud-example-resource.md.
    """

    field: str
    value: Any
    read_scoped: bool = True

    def filter(self) -> FilterClause:
        """Return the equality FilterClause this scope adds to every query."""
        return FilterClause(self.field, FilterOp.EQ, self.value)


class CRUDLike[SchemaT: BaseModel](Protocol):
    """Structural shape both CRUDInterface and CompatCRUD satisfy.

    Lets app.controllers.crud_router's router factories depend on "anything with
    these methods" rather than concretely on CRUDInterface, so the same
    factory builds both a current-version router (backed by CRUDInterface) and a
    deprecated one (backed by app.interfaces.compat.CompatCRUD) identically.
    """

    async def get(self, record_id: int) -> SchemaT | None:
        """Return the record with the given id as a view, or None if it doesn't exist."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
    ) -> list[SchemaT]:
        """Return up to `limit` matching records as views, skipping the first `skip`."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def count(self, *, filters: Sequence[FilterClause] = ()) -> int:
        """Return how many records match the given filters."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def create(self, data: BaseModel) -> SchemaT:
        """Create a record from the given input view and return it as a view."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def update(self, record_id: int, data: BaseModel) -> SchemaT | None:
        """Apply the given input view's set fields to the record, if it exists."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: BaseModel
    ) -> Sequence[SchemaT]:
        """Apply the given input view's set fields to every matching record; return them."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[SchemaT]:
        """Delete every record matching the filters; return the records that were deleted."""
        ...  # pragma: no cover -- Protocol stub, never executed directly


class CRUDInterface[SchemaT: BaseModel, ModelT]:
    """CRUD operations for one resource, parameterized by its view and repository."""

    def __init__(
        self,
        schema: type[SchemaT],
        repository: Repository[ModelT],
        *,
        owner: OwnerScope | None = None,
    ) -> None:
        """Bind this interface to the view/repository it converts through.

        `owner`, if given, restricts every operation below to records this owner
        created -- see OwnerScope's own docstring.
        """
        self._schema = schema
        self._repository = repository
        self._owner = owner

    def _scoped(self, filters: Sequence[FilterClause]) -> Sequence[FilterClause]:
        """Add this interface's owner filter (if any) to a write operation's filters.

        Always applied when `owner` is set, regardless of `owner.read_scoped` --
        writes stay owner-restricted even when reads are opened up to everyone.
        """
        return filters if self._owner is None else (*filters, self._owner.filter())

    def _read_scoped(self, filters: Sequence[FilterClause]) -> Sequence[FilterClause]:
        """Add this interface's owner filter (if any) to a read operation's filters.

        Unlike `_scoped`, this is a no-op when `owner.read_scoped` is False --
        `get`/`list`/`count` then see every record, not just this owner's.
        """
        if self._owner is None or not self._owner.read_scoped:
            return filters
        return (*filters, self._owner.filter())

    async def get(self, record_id: int) -> SchemaT | None:
        """Return the record with the given id as a view, or None if it doesn't exist."""
        if self._owner is None or not self._owner.read_scoped:
            instance = await self._repository.get(record_id)
            return self._schema.model_validate(instance) if instance is not None else None
        matches = await self._repository.list(
            filters=self._read_scoped(_id_filter(record_id)), limit=1
        )
        return self._schema.model_validate(matches[0]) if matches else None

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
    ) -> list[SchemaT]:
        """Return up to `limit` matching records as views, skipping the first `skip`."""
        instances = await self._repository.list(
            skip=skip, limit=limit, filters=self._read_scoped(filters), sort=sort
        )
        return [self._schema.model_validate(instance) for instance in instances]

    async def count(self, *, filters: Sequence[FilterClause] = ()) -> int:
        """Return how many records match the given filters.

        Called by app.controllers.crud_actions before a bulk update/delete, to cap
        how many records a single action can affect.
        """
        return await self._repository.count(filters=self._read_scoped(filters))

    async def create(self, data: BaseModel) -> SchemaT:
        """Create a record from the given input view and return it as a view.

        When `owner` is set, the owned field is stamped from the scope rather than
        trusted from `data` -- a caller can't create a record owned by someone else.
        """
        values = data.model_dump()
        if self._owner is not None:
            values[self._owner.field] = self._owner.value
        instance = await self._repository.create(values)
        return self._schema.model_validate(instance)

    async def update(self, record_id: int, data: BaseModel) -> SchemaT | None:
        """Apply the given input view's set fields to the record, if it exists."""
        if self._owner is None:
            instance = await self._repository.update(record_id, data.model_dump(exclude_unset=True))
            return self._schema.model_validate(instance) if instance is not None else None
        updated = await self._repository.update_many(
            filters=self._scoped(_id_filter(record_id)), data=data.model_dump(exclude_unset=True)
        )
        return self._schema.model_validate(updated[0]) if updated else None

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        if self._owner is None:
            return await self._repository.delete(record_id)
        deleted = await self._repository.delete_many(filters=self._scoped(_id_filter(record_id)))
        return bool(deleted)

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: BaseModel
    ) -> Sequence[SchemaT]:
        """Apply the given input view's set fields to every matching record; return them."""
        instances = await self._repository.update_many(
            filters=self._scoped(filters), data=data.model_dump(exclude_unset=True)
        )
        return [self._schema.model_validate(instance) for instance in instances]

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[SchemaT]:
        """Delete every record matching the filters; return the records that were deleted."""
        instances = await self._repository.delete_many(filters=self._scoped(filters))
        return [self._schema.model_validate(instance) for instance in instances]


def _id_filter(record_id: int) -> tuple[FilterClause]:
    """Return a single-element filter sequence matching one record by id."""
    return (FilterClause("id", FilterOp.EQ, record_id),)
