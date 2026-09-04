"""HTTP routes for the Hero resource -- a worked example of the generic CRUD interface."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.crud_router import build_json_router
from app.crud.base import CRUDInterface
from app.crud.dependency import build_repository_provider
from app.models.base import get_db
from app.models.hero import Hero as HeroModel
from app.oidc import require_roles
from app.views.hero import Hero, HeroCreate, HeroUpdate

_hero_repository = build_repository_provider(HeroModel)


def get_hero_crud(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CRUDInterface[Hero, HeroModel]:
    """Build a request-scoped CRUD interface for Hero.

    MODE=mock uses the shared in-memory repository instead of `session` -- an
    unused AsyncSession's commit() never opens a connection, so `session` stays a
    harmless, uniform dependency across every mode rather than needing two
    differently-signatured variants of this function.
    """
    return CRUDInterface(schema=Hero, repository=_hero_repository(session))


HeroCRUD = Annotated[CRUDInterface[Hero, HeroModel], Depends(get_hero_crud)]

ReadRoles = Depends(require_roles("viewer", "editor", "maintainer", "detective"))
WriteRoles = Depends(require_roles("editor", "maintainer"))
DeleteRoles = Depends(require_roles("maintainer"))

router = build_json_router(
    prefix="/heroes",
    tags=["heroes"],
    resource_label="Hero",
    schema=Hero,
    create_schema=HeroCreate,
    update_schema=HeroUpdate,
    crud_dependency=HeroCRUD,
    read_roles=ReadRoles,
    write_roles=WriteRoles,
    delete_roles=DeleteRoles,
)
