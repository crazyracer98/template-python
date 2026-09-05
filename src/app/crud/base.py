"""Generic CRUD interface.

Feed it a Pydantic view (app.views) and a Repository (app.repositories) to persist
it through, and it exposes CRUD operations that speak entirely in terms of that
view -- converting to and from the backing ORM model via the view's own
`from_attributes` support (see app.views.base.ORMView) is the only place that
conversion happens, so a new resource never needs its own CRUD class.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel

from app.repositories.base import Repository
from app.repositories.filtering import FilterClause, SortClause


class CRUDLike[SchemaT: BaseModel](Protocol):
    """Structural shape both CRUDInterface and CompatCRUD satisfy.

    Lets app.controllers.crud_router's router factories depend on "anything with
    these methods" rather than concretely on CRUDInterface, so the same
    factory builds both a current-version router (backed by CRUDInterface) and a
    deprecated one (backed by app.crud.compat.CompatCRUD) identically.
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

    def __init__(self, schema: type[SchemaT], repository: Repository[ModelT]) -> None:
        """Bind this interface to the view it returns and the repository it persists through."""
        self._schema = schema
        self._repository = repository

    async def get(self, record_id: int) -> SchemaT | None:
        """Return the record with the given id as a view, or None if it doesn't exist."""
        instance = await self._repository.get(record_id)
        return self._schema.model_validate(instance) if instance is not None else None

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
    ) -> list[SchemaT]:
        """Return up to `limit` matching records as views, skipping the first `skip`."""
        instances = await self._repository.list(skip=skip, limit=limit, filters=filters, sort=sort)
        return [self._schema.model_validate(instance) for instance in instances]

    async def count(self, *, filters: Sequence[FilterClause] = ()) -> int:  # pragma: no cover
        """Return how many records match the given filters.

        Not called by any route yet -- reserved for a future total-count response
        header -- so it never runs through the real HTTP stack tests/integration/
        tests/e2e exercise. Covered directly by tests/unit/crud.
        """
        return await self._repository.count(filters=filters)

    async def create(self, data: BaseModel) -> SchemaT:
        """Create a record from the given input view and return it as a view."""
        instance = await self._repository.create(data.model_dump())
        return self._schema.model_validate(instance)

    async def update(self, record_id: int, data: BaseModel) -> SchemaT | None:
        """Apply the given input view's set fields to the record, if it exists."""
        instance = await self._repository.update(record_id, data.model_dump(exclude_unset=True))
        return self._schema.model_validate(instance) if instance is not None else None

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        return await self._repository.delete(record_id)

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: BaseModel
    ) -> Sequence[SchemaT]:
        """Apply the given input view's set fields to every matching record; return them."""
        instances = await self._repository.update_many(
            filters=filters, data=data.model_dump(exclude_unset=True)
        )
        return [self._schema.model_validate(instance) for instance in instances]

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[SchemaT]:
        """Delete every record matching the filters; return the records that were deleted."""
        instances = await self._repository.delete_many(filters=filters)
        return [self._schema.model_validate(instance) for instance in instances]
