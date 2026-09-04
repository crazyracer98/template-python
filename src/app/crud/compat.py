"""Generic backward-compatibility wrapper around CRUDInterface.

Wraps a current-version CRUDInterface and exposes the same CRUD operations
in terms of an older (deprecated) view, converting responses down to the
legacy shape and incoming payloads up to the current shape via
caller-supplied converter functions -- so a deprecated API version keeps
working against the same repository/current model as the version that
superseded it, without its own duplicated CRUD wiring.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.crud.base import CRUDInterface


class CompatCRUD[LegacySchemaT: BaseModel, SchemaT: BaseModel, ModelT]:
    """CRUD operations shaped like an older API version, backed by the current CRUDInterface.

    `from_legacy_create`/`from_legacy_update` take `Any` rather than a specific legacy
    payload type: each resource's converter function is typed against its own concrete
    `*Create`/`*Update` view (narrower than `BaseModel`), and `Callable`'s contravariant
    parameter typing would otherwise reject that narrower-than-`BaseModel` signature here.
    """

    def __init__(
        self,
        crud: CRUDInterface[SchemaT, ModelT],
        *,
        to_legacy: Callable[[SchemaT], LegacySchemaT],
        from_legacy_create: Callable[[Any], BaseModel],
        from_legacy_update: Callable[[Any], BaseModel],
    ) -> None:
        """Bind this wrapper to the current CRUD it delegates to and its conversion functions."""
        self._crud = crud
        self._to_legacy = to_legacy
        self._from_legacy_create = from_legacy_create
        self._from_legacy_update = from_legacy_update

    async def get(self, record_id: int) -> LegacySchemaT | None:
        """Return the record with the given id in the legacy shape, or None."""
        current = await self._crud.get(record_id)
        return self._to_legacy(current) if current is not None else None

    async def list(self, *, skip: int = 0, limit: int = 100) -> list[LegacySchemaT]:
        """Return up to `limit` records in the legacy shape, skipping the first `skip`."""
        return [self._to_legacy(item) for item in await self._crud.list(skip=skip, limit=limit)]

    async def create(self, data: BaseModel) -> LegacySchemaT:
        """Create a record from a legacy-shaped payload and return it in the legacy shape."""
        created = await self._crud.create(self._from_legacy_create(data))
        return self._to_legacy(created)

    async def update(self, record_id: int, data: BaseModel) -> LegacySchemaT | None:
        """Apply a legacy-shaped partial update, returning the result in the legacy shape."""
        updated = await self._crud.update(record_id, self._from_legacy_update(data))
        return self._to_legacy(updated) if updated is not None else None

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        return await self._crud.delete(record_id)
