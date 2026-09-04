"""Generic MODE-aware Repository selection, shared by every resource's CRUD dependency."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.base import IdentifiedBase
from app.repositories.base import Repository
from app.repositories.memory import InMemoryRepository
from app.repositories.sqlalchemy import SQLAlchemyRepository

settings = get_settings()


def build_repository_provider[ModelT: IdentifiedBase](
    model: type[ModelT],
) -> Callable[[AsyncSession], Repository[ModelT]]:
    """Return a per-request Repository[ModelT] provider: shared in-memory under
    MODE=mock, a fresh SQLAlchemyRepository bound to the request's session otherwise.
    """
    mock_repository: Repository[ModelT] = InMemoryRepository(model)

    def provider(session: AsyncSession) -> Repository[ModelT]:
        return mock_repository if settings.mode == "mock" else SQLAlchemyRepository(session, model)

    return provider
