"""FastAPI app entrypoint: wires up settings, migrations, routers, and lifespan."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from alembic.config import Config
from fastapi import FastAPI

from alembic import command
from app.config import get_settings
from app.controllers import health, heroes, protected

settings = get_settings()


def _run_migrations() -> None:
    """Apply any pending Alembic migrations against the configured database.

    Blocking (Alembic's async recipe runs its own asyncio.run internally), so the
    caller must run this off the event loop -- see lifespan below. `alembic.ini` is
    resolved relative to the current working directory: the repo root in the
    devcontainer and under pytest, /app in the runner image (see the root
    Dockerfile's runner stage, which copies alembic.ini/alembic/ there).
    """
    command.upgrade(Config("alembic.ini"), "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Apply pending migrations before serving, then run normally until shutdown."""
    await asyncio.to_thread(_run_migrations)
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": settings.oidc_client_id,
    },
)

app.include_router(health.router)
app.include_router(heroes.router)
app.include_router(protected.router)
