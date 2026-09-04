"""HTTP routes for the Hero resource -- a worked example of the generic CRUD interface."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.base import CRUDInterface
from app.models.base import get_db
from app.models.hero import Hero as HeroModel
from app.oidc import require_roles
from app.repositories.base import Repository
from app.repositories.memory import InMemoryRepository
from app.repositories.sqlalchemy import SQLAlchemyRepository
from app.views.hero import Hero, HeroCreate, HeroUpdate

router = APIRouter(prefix="/heroes", tags=["heroes"])

settings = get_settings()

# Built once at import time regardless of MODE (cheap, no I/O) -- see
# repositories/README.md's "Do" for adding a non-SQLAlchemy Repository like this
# one. Shared across requests so state persists between them, the same way a real
# database would.
_mock_repository: Repository[HeroModel] = InMemoryRepository(HeroModel)


def get_hero_crud(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CRUDInterface[Hero, HeroModel]:
    """Build a request-scoped CRUD interface for Hero.

    MODE=mock uses the shared in-memory repository instead of `session` -- an
    unused AsyncSession's commit() never opens a connection, so `session` stays a
    harmless, uniform dependency across every mode rather than needing two
    differently-signatured variants of this function.
    """
    repository: Repository[HeroModel] = (
        _mock_repository if settings.mode == "mock" else SQLAlchemyRepository(session, HeroModel)
    )
    return CRUDInterface(schema=Hero, repository=repository)


HeroCRUD = Annotated[CRUDInterface[Hero, HeroModel], Depends(get_hero_crud)]

ReadRoles = Depends(require_roles("viewer", "editor", "maintainer", "detective"))
WriteRoles = Depends(require_roles("editor", "maintainer"))
DeleteRoles = Depends(require_roles("maintainer"))


@router.get("", dependencies=[ReadRoles])
async def list_heroes(crud: HeroCRUD, skip: int = 0, limit: int = 100) -> list[Hero]:
    """List heroes."""
    return await crud.list(skip=skip, limit=limit)


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[WriteRoles])
async def create_hero(hero: HeroCreate, crud: HeroCRUD) -> Hero:
    """Create a hero."""
    return await crud.create(hero)


@router.get("/{hero_id:int}", dependencies=[ReadRoles])
async def get_hero(hero_id: int, crud: HeroCRUD) -> Hero:
    """Get a hero by id."""
    hero = await crud.get(hero_id)
    if hero is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return hero


@router.patch("/{hero_id:int}", dependencies=[WriteRoles])
async def update_hero(hero_id: int, hero: HeroUpdate, crud: HeroCRUD) -> Hero:
    """Partially update a hero."""
    updated = await crud.update(hero_id, hero)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return updated


@router.delete("/{hero_id:int}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[DeleteRoles])
async def delete_hero(hero_id: int, crud: HeroCRUD) -> None:
    """Delete a hero."""
    deleted = await crud.delete(hero_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
