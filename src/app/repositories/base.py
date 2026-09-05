"""Generic repository protocol: the storage-agnostic contract app.crud talks to."""

from collections.abc import Sequence
from typing import Any, Protocol

from app.repositories.filtering import FilterClause, SortClause


class Repository[ModelT](Protocol):
    """Storage-agnostic CRUD contract for a single kind of persisted record."""

    async def get(self, record_id: int) -> ModelT | None:
        """Return the record with the given id, or None if it doesn't exist."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
    ) -> Sequence[ModelT]:
        """Return up to `limit` matching records, skipping the first `skip`."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def count(self, *, filters: Sequence[FilterClause] = ()) -> int:
        """Return how many records match the given filters."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def create(self, data: dict[str, Any]) -> ModelT:
        """Create and return a new record from the given field values."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def update(self, record_id: int, data: dict[str, Any]) -> ModelT | None:
        """Update the record with the given id and return it, or None if it doesn't exist."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: dict[str, Any]
    ) -> Sequence[ModelT]:
        """Apply the given field values to every record matching the filters; return them."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[ModelT]:
        """Delete every record matching the filters; return the records that were deleted."""
        ...  # pragma: no cover -- Protocol stub, never executed directly
