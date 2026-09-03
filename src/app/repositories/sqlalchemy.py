"""Generic SQLAlchemy implementation of the Repository protocol.

Parameterized purely by a SQLAlchemy model class (app.models.base.IdentifiedBase
subclass) -- adding a new resource never requires a new repository class, only a
new model.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import IdentifiedBase


class SQLAlchemyRepository[ModelT: IdentifiedBase]:
    """Repository backed by a SQLAlchemy async session and a single mapped model."""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        """Bind this repository to a session and the SQLAlchemy model it persists."""
        self._session = session
        self._model = model

    async def get(self, record_id: int) -> ModelT | None:
        """Return the record with the given id, or None if it doesn't exist."""
        return await self._session.get(self._model, record_id)

    async def list(self, *, skip: int = 0, limit: int = 100) -> Sequence[ModelT]:
        """Return up to `limit` records, skipping the first `skip`, ordered by id."""
        result = await self._session.execute(
            select(self._model).order_by(self._model.id).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, data: dict[str, Any]) -> ModelT:
        """Insert a new row from the given field values and return it."""
        instance = self._model(**data)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update(self, record_id: int, data: dict[str, Any]) -> ModelT | None:
        """Apply the given field values to the record with the given id, if it exists."""
        instance = await self.get(record_id)
        if instance is None:
            return None
        for field, value in data.items():
            setattr(instance, field, value)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        instance = await self.get(record_id)
        if instance is None:
            return False
        await self._session.delete(instance)
        await self._session.flush()
        return True
