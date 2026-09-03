"""Generic repository protocol: the storage-agnostic contract app.crud talks to."""

from collections.abc import Sequence
from typing import Any, Protocol


class Repository[ModelT](Protocol):
    """Storage-agnostic CRUD contract for a single kind of persisted record."""

    async def get(self, record_id: int) -> ModelT | None:
        """Return the record with the given id, or None if it doesn't exist."""
        ...  # pragma: no cover -- Protocol stub, never executed directly

    async def list(self, *, skip: int = 0, limit: int = 100) -> Sequence[ModelT]:
        """Return up to `limit` records, skipping the first `skip`."""
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
