"""In-memory implementation of the Repository protocol, used when MODE=mock.

Parameterized purely by a SQLAlchemy model class, matching sqlalchemy.py's shape --
adding a new mock-backed resource never requires a new repository class, only a
model. Unlike SQLAlchemyRepository, there is no server to supply `created_at`/
`updated_at` via `server_default`/`onupdate` (see app.models.base.IdentifiedBase),
so this repository sets them itself -- as naive UTC datetimes, matching the naive
`TIMESTAMP` columns Postgres stores them as (both conventionally UTC, per
IdentifiedBase's own docstring), so a datetime filter value (normalized to naive
UTC the same way in app.controllers.crud_query) compares correctly against either
backend.

tests/unit exercises every method below directly; tests/e2e's MODE=mock leg
exercises them too through the real HTTP stack.
"""

import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from app.models.base import IdentifiedBase
from app.repositories.filtering import FilterClause, FilterOp, SortClause


def _now() -> datetime:
    """Return the current time as naive UTC, matching how Postgres stores timestamps."""
    return datetime.now(UTC).replace(tzinfo=None)


_PREDICATES: dict[FilterOp, Callable[[Any, Any], bool]] = {
    FilterOp.EQ: lambda value, target: bool(value == target),
    FilterOp.NE: lambda value, target: bool(value != target),
    FilterOp.LT: lambda value, target: bool(value < target),
    FilterOp.LTE: lambda value, target: bool(value <= target),
    FilterOp.GT: lambda value, target: bool(value > target),
    FilterOp.GTE: lambda value, target: bool(value >= target),
    FilterOp.IN: lambda value, target: value in target,
    FilterOp.CONTAINS: lambda value, target: str(target) in str(value),
    FilterOp.ICONTAINS: lambda value, target: str(target).casefold() in str(value).casefold(),
    FilterOp.REGEX: lambda value, target: re.search(str(target), str(value)) is not None,
}


def _matches(instance: object, clause: FilterClause) -> bool:
    value = getattr(instance, clause.field)
    return _PREDICATES[clause.op](value, clause.value)


def _sort_key(instance: object, clause: SortClause) -> Any:  # noqa: ANN401
    return getattr(instance, clause.field)


class InMemoryRepository[ModelT: IdentifiedBase]:
    """Repository backed by a plain dict, keyed by an auto-incrementing id."""

    def __init__(self, model: type[ModelT]) -> None:
        """Bind this repository to the SQLAlchemy model class it stores instances of."""
        self._model = model
        self._records: dict[int, ModelT] = {}
        self._next_id = 1

    def _matching(self, filters: Sequence[FilterClause]) -> list[ModelT]:
        return [
            instance
            for instance in self._records.values()
            if all(_matches(instance, clause) for clause in filters)
        ]

    def _sorted(self, instances: list[ModelT], sort: Sequence[SortClause]) -> list[ModelT]:
        result = instances
        for clause in reversed(sort):
            result = sorted(
                result, key=lambda instance: _sort_key(instance, clause), reverse=clause.descending
            )
        return result

    async def get(self, record_id: int) -> ModelT | None:
        """Return the record with the given id, or None if it doesn't exist."""
        return self._records.get(record_id)

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
    ) -> Sequence[ModelT]:
        """Return up to `limit` matching records, skipping the first `skip`."""
        matching = self._matching(filters)
        ordered = self._sorted(matching, sort) if sort else matching
        return ordered[skip : skip + limit]

    async def count(self, *, filters: Sequence[FilterClause] = ()) -> int:
        """Return how many records match the given filters.

        Called by app.controllers.crud_actions before a bulk update/delete, to cap
        how many records a single action can affect.
        """
        return len(self._matching(filters))

    async def create(self, data: dict[str, Any]) -> ModelT:
        """Create a new record from the given field values and return it."""
        now = _now()
        instance = self._model(id=self._next_id, created_at=now, updated_at=now, **data)
        self._records[self._next_id] = instance
        self._next_id += 1
        return instance

    async def update(self, record_id: int, data: dict[str, Any]) -> ModelT | None:
        """Apply the given field values to the record with the given id, if it exists."""
        instance = self._records.get(record_id)
        if instance is None:
            return None
        for field, value in data.items():
            setattr(instance, field, value)
        instance.updated_at = _now()
        return instance

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        return self._records.pop(record_id, None) is not None

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: dict[str, Any]
    ) -> Sequence[ModelT]:
        """Apply the given field values to every record matching the filters; return them."""
        instances = self._matching(filters)
        now = _now()
        for instance in instances:
            for field, value in data.items():
                setattr(instance, field, value)
            instance.updated_at = now
        return instances

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[ModelT]:
        """Delete every record matching the filters; return the records that were deleted."""
        instances = self._matching(filters)
        for instance in instances:
            del self._records[instance.id]
        return instances
