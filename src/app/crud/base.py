"""Generic CRUD interface.

Feed it a Pydantic view (app.views) and a Repository (app.repositories) to persist
it through, and it exposes CRUD operations that speak entirely in terms of that
view -- converting to and from the backing ORM model via the view's own
`from_attributes` support (see app.views.base.ORMView) is the only place that
conversion happens, so a new resource never needs its own CRUD class.
"""

from typing import Protocol

from pydantic import BaseModel

from app.repositories.base import Repository


class CRUDLike[SchemaT: BaseModel](Protocol):
    """Structural shape both CRUDInterface and CompatCRUD satisfy.

    Lets app.controllers.crud_router's router factories depend on "anything with
    these five async methods" rather than concretely on CRUDInterface, so the same
    factory builds both a current-version router (backed by CRUDInterface) and a
    deprecated one (backed by app.crud.compat.CompatCRUD) identically.
    """

    async def get(self, record_id: int) -> SchemaT | None:
        """Return the record with the given id as a view, or None if it doesn't exist."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def list(self, *, skip: int = 0, limit: int = 100) -> list[SchemaT]:
        """Return up to `limit` records as views, skipping the first `skip`."""
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

    async def list(self, *, skip: int = 0, limit: int = 100) -> list[SchemaT]:
        """Return up to `limit` records as views, skipping the first `skip`."""
        instances = await self._repository.list(skip=skip, limit=limit)
        return [self._schema.model_validate(instance) for instance in instances]

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
