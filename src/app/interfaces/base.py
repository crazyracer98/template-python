"""Generic CRUD interface.

Feed it a Pydantic view (app.views) and a Repository (app.repositories) to persist
it through, and it exposes CRUD operations that speak entirely in terms of that
view -- converting to and from the backing ORM model via the view's own
`from_attributes` support (see app.views.base.ORMView) is the only place that
conversion happens, so a new resource never needs its own CRUD class.

A few branches below are `# pragma: no cover` for the same reason as
app.repositories.sqlalchemy's module docstring: Hero -- the only resource
tests/e2e's journeys exercise -- always builds its CRUDInterface with `owner`
and `revisions` both set (see app.crud_1.heroes.heroes_v2.get_hero_crud), and
`owner.read_scoped=False`, so the `owner is None`/`revisions is None`/
`owner.read_scoped is True` branches below can never run through `tests/e2e`.
tests/unit/interfaces/test_base.py exercises every one of them directly against
a standalone owner-less/revision-less CRUDInterface, which is what actually
covers them for the primary (`pytest`, i.e. tests/unit + tests/integration)
coverage gate; the pragma only affects what's counted toward the separate
`pytest tests/e2e` coverage gate.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from app.repositories.base import Repository
from app.repositories.filtering import FilterClause, FilterOp, SortClause


class RevisionSink(Protocol):
    """Opt-in append-only revision-history hook for a CRUDInterface.

    A small Protocol (rather than a concrete class) so app.interfaces stays
    unaware of app.models.revision.Revision's own storage shape -- see
    RepositoryRevisionSink below for the concrete adapter every resource that
    opts in actually uses.
    """

    async def record(
        self, *, resource: str, record_id: int, action: str, snapshot: dict[str, Any], actor: str
    ) -> None:
        """Append one revision log entry."""
        ...  # pragma: no cover -- Protocol stub, never executed directly


@dataclass(frozen=True)
class RepositoryRevisionSink:
    """RevisionSink backed by a plain Repository[Revision] -- no bespoke storage class needed.

    `app.models.revision.Revision` is just another IdentifiedBase model, so the
    same `Repository[ModelT]`/`build_repository_provider` machinery every other
    resource uses already knows how to persist it (SQLAlchemy-backed in dev/
    production, in-memory under MODE=mock) -- this is a thin adapter from
    RevisionSink's `record(...)` call shape to `Repository.create(...)`'s dict shape.
    """

    repository: Repository[Any]

    async def record(
        self, *, resource: str, record_id: int, action: str, snapshot: dict[str, Any], actor: str
    ) -> None:
        """Persist one revision row via the wrapped repository's create()."""
        await self.repository.create(
            {
                "resource": resource,
                "record_id": record_id,
                "action": action,
                "snapshot": snapshot,
                "actor": actor,
            }
        )


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

    async def get(
        self, record_id: int, *, include_archived: bool = False, include_unpublished: bool = False
    ) -> SchemaT | None:
        """Return the record with the given id as a view, or None if it doesn't exist."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
        include_archived: bool = False,
        include_unpublished: bool = False,
    ) -> list[SchemaT]:
        """Return up to `limit` matching records as views, skipping the first `skip`."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def count(
        self,
        *,
        filters: Sequence[FilterClause] = (),
        include_archived: bool = False,
        include_unpublished: bool = False,
    ) -> int:
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
        revisions: RevisionSink | None = None,
        resource: str | None = None,
        actor: str = "unknown",
    ) -> None:
        """Bind this interface to the view/repository it converts through.

        `owner`, if given, restricts every operation below to records this owner
        created -- see OwnerScope's own docstring.

        `revisions`, if given, is called once per successful create/update/
        update_many/delete/delete_many with a snapshot of the affected record --
        `revisions=None` (the default) changes nothing, the same opt-in shape as
        `owner`. `resource` (e.g. "hero") and `actor` (typically the caller's
        `claims["sub"]`, resolved once per request the same way `owner`'s `value`
        is) are only meaningful when `revisions` is set.
        """
        self._schema = schema
        self._repository = repository
        self._owner = owner
        self._revisions = revisions
        self._resource = resource
        self._actor = actor

    async def _record_revision(self, *, record_id: int, action: str, snapshot: SchemaT) -> None:
        """Call the configured RevisionSink, if any, with a JSON-safe snapshot."""
        if self._revisions is None:
            return  # pragma: no cover -- see module docstring
        await self._revisions.record(
            resource=self._resource or "",
            record_id=record_id,
            action=action,
            snapshot=snapshot.model_dump(mode="json"),
            actor=self._actor,
        )

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
        return (*filters, self._owner.filter())  # pragma: no cover -- see module docstring

    async def get(
        self, record_id: int, *, include_archived: bool = False, include_unpublished: bool = False
    ) -> SchemaT | None:
        """Return the record with the given id as a view, or None if it doesn't exist.

        `include_archived`/`include_unpublished` override the default Archivable/
        Schedulable exclusion for a model carrying those mixins -- a no-op
        otherwise, see app.repositories.sqlalchemy/app.repositories.memory.
        """
        if self._owner is None or not self._owner.read_scoped:
            instance = await self._repository.get(
                record_id,
                include_archived=include_archived,
                include_unpublished=include_unpublished,
            )
            return self._schema.model_validate(instance) if instance is not None else None
        matches = await self._repository.list(  # pragma: no cover -- see module docstring
            filters=self._read_scoped(_id_filter(record_id)),
            limit=1,
            include_archived=include_archived,
            include_unpublished=include_unpublished,
        )
        return (  # pragma: no cover -- see module docstring
            self._schema.model_validate(matches[0]) if matches else None
        )

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
        include_archived: bool = False,
        include_unpublished: bool = False,
    ) -> list[SchemaT]:
        """Return up to `limit` matching records as views, skipping the first `skip`.

        See `get`'s docstring for `include_archived`/`include_unpublished`.
        """
        instances = await self._repository.list(
            skip=skip,
            limit=limit,
            filters=self._read_scoped(filters),
            sort=sort,
            include_archived=include_archived,
            include_unpublished=include_unpublished,
        )
        return [self._schema.model_validate(instance) for instance in instances]

    async def count(
        self,
        *,
        filters: Sequence[FilterClause] = (),
        include_archived: bool = False,
        include_unpublished: bool = False,
    ) -> int:
        """Return how many records match the given filters.

        Called by app.controllers.crud_actions before a bulk update/delete, to cap
        how many records a single action can affect.
        """
        return await self._repository.count(
            filters=self._read_scoped(filters),
            include_archived=include_archived,
            include_unpublished=include_unpublished,
        )

    async def create(self, data: BaseModel) -> SchemaT:
        """Create a record from the given input view and return it as a view.

        When `owner` is set, the owned field is stamped from the scope rather than
        trusted from `data` -- a caller can't create a record owned by someone else.

        `exclude_unset=True`: a field the caller genuinely omitted (as opposed to one
        explicitly set to its own default) is left out of `values` entirely, so the
        repository/column's own default applies -- required for a Draftable create
        (see app.controllers.crud_router's `/draft` route, whose body validates
        against a resource's all-optional `*Update` view): an omitted non-nullable
        lifecycle field like Lockable's `is_locked` must take its column default
        (e.g. `False`), not an explicit `None`, which every normal create-schema
        field (always required, so always "set") is unaffected by.
        """
        values = data.model_dump(exclude_unset=True)
        if self._owner is not None:  # pragma: no cover -- see module docstring
            values[self._owner.field] = self._owner.value
        instance = await self._repository.create(values)
        result = self._schema.model_validate(instance)
        await self._record_revision(
            record_id=instance.id,  # type: ignore[attr-defined]
            action="create",
            snapshot=result,
        )
        return result

    async def update(self, record_id: int, data: BaseModel) -> SchemaT | None:
        """Apply the given input view's set fields to the record, if it exists."""
        if self._owner is None:  # pragma: no cover -- see module docstring
            instance = await self._repository.update(record_id, data.model_dump(exclude_unset=True))
            if instance is None:
                return None
            result = self._schema.model_validate(instance)
        else:
            updated = await self._repository.update_many(
                filters=self._scoped(_id_filter(record_id)),
                data=data.model_dump(exclude_unset=True),
            )
            if not updated:
                return None
            result = self._schema.model_validate(updated[0])
        await self._record_revision(record_id=record_id, action="update", snapshot=result)
        return result

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        snapshot = (
            await self._pre_delete_snapshot(record_id) if self._revisions is not None else None
        )
        if self._owner is None:  # pragma: no cover -- see module docstring
            deleted = await self._repository.delete(record_id)
        else:
            deleted_records = await self._repository.delete_many(
                filters=self._scoped(_id_filter(record_id))
            )
            deleted = bool(deleted_records)
        if deleted and snapshot is not None:
            await self._record_revision(record_id=record_id, action="delete", snapshot=snapshot)
        return deleted

    async def _pre_delete_snapshot(self, record_id: int) -> SchemaT | None:
        """Return a view of the record before it's deleted, for the revision log."""
        instance = await self._repository.get(
            record_id, include_archived=True, include_unpublished=True
        )
        return self._schema.model_validate(instance) if instance is not None else None

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: BaseModel
    ) -> Sequence[SchemaT]:
        """Apply the given input view's set fields to every matching record; return them."""
        instances = await self._repository.update_many(
            filters=self._scoped(filters), data=data.model_dump(exclude_unset=True)
        )
        results = [self._schema.model_validate(instance) for instance in instances]
        for result in results:
            await self._record_revision(record_id=result.id, action="update", snapshot=result)  # type: ignore[attr-defined]
        return results

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[SchemaT]:
        """Delete every record matching the filters; return the records that were deleted."""
        instances = await self._repository.delete_many(filters=self._scoped(filters))
        results = [self._schema.model_validate(instance) for instance in instances]
        for result in results:
            await self._record_revision(record_id=result.id, action="delete", snapshot=result)  # type: ignore[attr-defined]
        return results

    async def restore(self, record_id: int) -> SchemaT | None:
        """Clear `archived_at` on the record with the given id; return it, or None."""
        if self._owner is None:  # pragma: no cover -- see module docstring
            instance = await self._repository.restore(record_id)
            return self._schema.model_validate(instance) if instance is not None else None
        restored = await self._repository.restore_many(filters=self._scoped(_id_filter(record_id)))
        return self._schema.model_validate(restored[0]) if restored else None

    async def restore_many(self, *, filters: Sequence[FilterClause]) -> Sequence[SchemaT]:
        """Clear `archived_at` on every record matching the filters; return them."""
        instances = await self._repository.restore_many(filters=self._scoped(filters))
        return [self._schema.model_validate(instance) for instance in instances]


def _id_filter(record_id: int) -> tuple[FilterClause]:
    """Return a single-element filter sequence matching one record by id."""
    return (FilterClause("id", FilterOp.EQ, record_id),)
