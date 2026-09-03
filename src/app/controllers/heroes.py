"""HTTP routes for the Hero resource -- a worked example of the generic CRUD interface."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDInterface
from app.models.base import get_db
from app.models.hero import Hero as HeroModel
from app.repositories.sqlalchemy import SQLAlchemyRepository
from app.views.hero import Hero, HeroCreate, HeroUpdate

router = APIRouter(prefix="/heroes", tags=["heroes"])


def get_hero_crud(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CRUDInterface[Hero, HeroModel]:
    """Build a request-scoped CRUD interface for Hero, bound to this request's DB session."""
    return CRUDInterface(schema=Hero, repository=SQLAlchemyRepository(session, HeroModel))


HeroCRUD = Annotated[CRUDInterface[Hero, HeroModel], Depends(get_hero_crud)]


@router.get("")
async def list_heroes(crud: HeroCRUD, skip: int = 0, limit: int = 100) -> list[Hero]:
    """List heroes."""
    return await crud.list(skip=skip, limit=limit)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_hero(hero: HeroCreate, crud: HeroCRUD) -> Hero:
    """Create a hero."""
    return await crud.create(hero)


@router.get("/{hero_id}")
async def get_hero(hero_id: int, crud: HeroCRUD) -> Hero:
    """Get a hero by id."""
    hero = await crud.get(hero_id)
    if hero is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return hero


@router.patch("/{hero_id}")
async def update_hero(hero_id: int, hero: HeroUpdate, crud: HeroCRUD) -> Hero:
    """Partially update a hero."""
    updated = await crud.update(hero_id, hero)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return updated


@router.delete("/{hero_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hero(hero_id: int, crud: HeroCRUD) -> None:
    """Delete a hero."""
    deleted = await crud.delete(hero_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
