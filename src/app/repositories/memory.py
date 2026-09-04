"""In-memory implementation of the Repository protocol, used when MODE=mock.

Parameterized purely by a SQLAlchemy model class, matching sqlalchemy.py's shape --
adding a new mock-backed resource never requires a new repository class, only a
model. Unlike SQLAlchemyRepository, there is no server to supply `created_at`/
`updated_at` via `server_default`/`onupdate` (see app.models.base.IdentifiedBase),
so this repository sets them itself.

Every method below is `# pragma: no cover` for tests/e2e specifically: e2e drives
one live process with a single fixed MODE for its whole run (MODE=dev here -- see
.devcontainer/compose.yml), so a repository that's only ever selected under
MODE=mock (app.controllers.heroes.get_hero_crud) can never be called in that run.
tests/unit exercises every method directly and still counts toward its own 95%
gate -- the pragma only affects what's counted, not whether these lines run there.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.models.base import IdentifiedBase


class InMemoryRepository[ModelT: IdentifiedBase]:
    """Repository backed by a plain dict, keyed by an auto-incrementing id."""

    def __init__(self, model: type[ModelT]) -> None:
        """Bind this repository to the SQLAlchemy model class it stores instances of."""
        self._model = model
        self._records: dict[int, ModelT] = {}
        self._next_id = 1

    async def get(
        self, record_id: int
    ) -> ModelT | None:  # pragma: no cover -- see module docstring
        """Return the record with the given id, or None if it doesn't exist."""
        return self._records.get(record_id)

    async def list(  # pragma: no cover -- see module docstring
        self, *, skip: int = 0, limit: int = 100
    ) -> Sequence[ModelT]:
        """Return up to `limit` records, skipping the first `skip`, ordered by id."""
        return list(self._records.values())[skip : skip + limit]

    async def create(
        self, data: dict[str, Any]
    ) -> ModelT:  # pragma: no cover -- see module docstring
        """Create a new record from the given field values and return it."""
        now = datetime.now(UTC)
        instance = self._model(id=self._next_id, created_at=now, updated_at=now, **data)
        self._records[self._next_id] = instance
        self._next_id += 1
        return instance

    async def update(  # pragma: no cover -- see module docstring
        self, record_id: int, data: dict[str, Any]
    ) -> ModelT | None:
        """Apply the given field values to the record with the given id, if it exists."""
        instance = self._records.get(record_id)
        if instance is None:
            return None
        for field, value in data.items():
            setattr(instance, field, value)
        instance.updated_at = datetime.now(UTC)
        return instance

    async def delete(self, record_id: int) -> bool:  # pragma: no cover -- see module docstring
        """Delete the record with the given id; return whether it existed."""
        return self._records.pop(record_id, None) is not None
