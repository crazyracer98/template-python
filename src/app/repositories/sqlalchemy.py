"""Generic SQLAlchemy implementation of the Repository protocol.

Parameterized purely by a SQLAlchemy model class (app.models.base.IdentifiedBase
subclass) -- adding a new resource never requires a new repository class, only a
new model.

A few FilterOp branches below are `# pragma: no cover`: app.controllers.crud_query
(the only place that turns an HTTP query string into a FilterClause) never emits
NE/LT/GT/CONTAINS -- its wire format only ever produces EQ/GTE/LTE/IN/ICONTAINS/
REGEX (see its module docstring) -- so those branches can never run through the
real HTTP stack tests/integration/tests/e2e exercise. tests/integration/
repositories/test_sqlalchemy.py's test_every_filter_op_against_real_postgres
calls this repository directly to exercise every FilterOp regardless; the pragma
only affects what's counted toward the e2e coverage gate specifically.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import IdentifiedBase
from app.repositories.filtering import FilterClause, FilterOp, SortClause


class SQLAlchemyRepository[ModelT: IdentifiedBase]:
    """Repository backed by a SQLAlchemy async session and a single mapped model."""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        """Bind this repository to a session and the SQLAlchemy model it persists."""
        self._session = session
        self._model = model

    def _where_clauses(self, filters: Sequence[FilterClause]) -> list[ColumnElement[bool]]:
        """Translate each FilterClause into a SQLAlchemy predicate on this model's columns."""
        clauses: list[ColumnElement[bool]] = []
        for clause in filters:
            column = getattr(self._model, clause.field)
            match clause.op:
                case FilterOp.EQ:
                    clauses.append(column == clause.value)
                case FilterOp.NE:  # pragma: no cover -- see module docstring
                    clauses.append(column != clause.value)
                case FilterOp.LT:  # pragma: no cover -- see module docstring
                    clauses.append(column < clause.value)
                case FilterOp.LTE:
                    clauses.append(column <= clause.value)
                case FilterOp.GT:  # pragma: no cover -- see module docstring
                    clauses.append(column > clause.value)
                case FilterOp.GTE:
                    clauses.append(column >= clause.value)
                case FilterOp.IN:
                    clauses.append(column.in_(clause.value))
                case FilterOp.CONTAINS:  # pragma: no cover -- see module docstring
                    clauses.append(column.contains(clause.value))
                case FilterOp.ICONTAINS:
                    clauses.append(column.ilike(f"%{clause.value}%"))
                case FilterOp.REGEX:
                    clauses.append(column.op("~")(clause.value))
        return clauses

    def _order_by(self, sort: Sequence[SortClause]) -> list[ColumnElement[Any]]:
        """Translate each SortClause into a SQLAlchemy ORDER BY term on this model's columns."""
        order = []
        for clause in sort:
            column = getattr(self._model, clause.field)
            order.append(column.desc() if clause.descending else column.asc())
        return order

    def _matching(self, filters: Sequence[FilterClause]) -> Select[tuple[ModelT]]:
        return select(self._model).where(*self._where_clauses(filters))

    async def get(self, record_id: int) -> ModelT | None:
        """Return the record with the given id, or None if it doesn't exist."""
        return await self._session.get(self._model, record_id)

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Sequence[FilterClause] = (),
        sort: Sequence[SortClause] = (),
    ) -> Sequence[ModelT]:
        """Return up to `limit` matching records, skipping the first `skip`."""
        order = self._order_by(sort) if sort else [self._model.id.asc()]
        statement = self._matching(filters).order_by(*order).offset(skip).limit(limit)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def count(self, *, filters: Sequence[FilterClause] = ()) -> int:  # pragma: no cover
        """Return how many records match the given filters.

        Not called by any route yet -- reserved for a future total-count response
        header -- so it never runs through the real HTTP stack tests/integration/
        tests/e2e exercise. Covered directly by tests/unit/crud, tests/unit/
        repositories, and tests/integration/repositories.
        """
        statement = (
            select(func.count()).select_from(self._model).where(*self._where_clauses(filters))
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

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

    async def update_many(
        self, *, filters: Sequence[FilterClause], data: dict[str, Any]
    ) -> Sequence[ModelT]:
        """Apply the given field values to every record matching the filters; return them."""
        result = await self._session.execute(self._matching(filters))
        instances = result.scalars().all()
        for instance in instances:
            for field, value in data.items():
                setattr(instance, field, value)
        await self._session.flush()
        for instance in instances:
            await self._session.refresh(instance)
        return instances

    async def delete_many(self, *, filters: Sequence[FilterClause]) -> Sequence[ModelT]:
        """Delete every record matching the filters; return the records that were deleted."""
        result = await self._session.execute(self._matching(filters))
        instances = result.scalars().all()
        for instance in instances:
            await self._session.delete(instance)
        await self._session.flush()
        return instances
