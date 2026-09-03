"""Declarative base, async engine/session, and the FastAPI DB dependency."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# NullPool: an asyncpg connection is tied to the event loop it was opened on, and
# pooling would hand one from a closed-out loop to a new one -- fine for the app's
# own single long-lived event loop, but tests/integration mixes pytest-asyncio's
# loop with TestClient's own background-thread loop, which pooling can't survive
# ("cannot perform operation: another operation is in progress"). A fresh
# connection per checkout sidesteps that everywhere, at the cost of connection
# reuse -- acceptable for this template's traffic; front it with PgBouncer instead
# of re-enabling pooling here if that ever matters.
engine = create_async_engine(settings.database_url, poolclass=NullPool)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base every SQLAlchemy model inherits from."""


class IdentifiedBase(Base):
    """Base for models with a single-column integer primary key named `id`.

    Repository/CRUD generics (see app.repositories and app.crud) are bound to this
    type so they can order/select by `id` without each model redeclaring the column.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped AsyncSession, committed on success."""
    async with async_session_factory() as session:
        yield session
        await session.commit()
