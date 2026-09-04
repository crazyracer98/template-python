"""HTTP routes for /v1/heroes -- the deprecated single-power Hero shape.

Deprecated in favor of /v2/heroes (app.controllers.heroes), which supports
multiple powers per hero. Wraps the same CRUD app.controllers.heroes
already builds via app.crud.compat.CompatCRUD, converting to/from the v1
view with app.views.hero_v1's converter functions -- no new persistence
code, only the version-compatibility shape.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.controllers.heroes import DeleteRoles, HeroCRUD, ReadRoles, WriteRoles
from app.crud.compat import CompatCRUD
from app.http_headers import sunset
from app.models.hero import Hero as HeroModel
from app.views.hero import Hero
from app.views.hero_v1 import (
    HeroV1,
    HeroV1Create,
    HeroV1Update,
    hero_to_v1,
    hero_v1_create_to_v2,
    hero_v1_update_to_v2,
)

# DeleteRoles/ReadRoles/WriteRoles are re-exported for heroes_v1_xml.py/heroes_v1_web.py to
# import, same as app.controllers.heroes does for heroes_xml.py/heroes_web.py -- mypy --strict's
# implicit_reexport=False needs this listed explicitly, since they're imported here, not defined.
__all__ = ["DeleteRoles", "HeroV1CRUD", "ReadRoles", "WriteRoles"]

_SUNSET_AT = datetime(2027, 1, 1, tzinfo=UTC)

router = APIRouter(
    prefix="/heroes",
    tags=["heroes"],
    dependencies=[Depends(sunset(_SUNSET_AT, link="/v2/heroes"))],
)


def get_hero_v1_crud(crud: HeroCRUD) -> CompatCRUD[HeroV1, Hero, HeroModel]:
    """Build a v1-shaped CRUD interface backed by the current (v2) Hero CRUD."""
    return CompatCRUD(
        crud,
        to_legacy=hero_to_v1,
        from_legacy_create=hero_v1_create_to_v2,
        from_legacy_update=hero_v1_update_to_v2,
    )


HeroV1CRUD = Annotated[CompatCRUD[HeroV1, Hero, HeroModel], Depends(get_hero_v1_crud)]


@router.get("", dependencies=[ReadRoles])
async def list_heroes_v1(crud: HeroV1CRUD, skip: int = 0, limit: int = 100) -> list[HeroV1]:
    """List heroes in the deprecated v1 shape."""
    return await crud.list(skip=skip, limit=limit)


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[WriteRoles])
async def create_hero_v1(hero: HeroV1Create, crud: HeroV1CRUD) -> HeroV1:
    """Create a hero from a v1-shaped payload."""
    return await crud.create(hero)


@router.get("/{hero_id:int}", dependencies=[ReadRoles])
async def get_hero_v1(hero_id: int, crud: HeroV1CRUD) -> HeroV1:
    """Get a hero by id, in the deprecated v1 shape."""
    hero = await crud.get(hero_id)
    if hero is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return hero


@router.patch("/{hero_id:int}", dependencies=[WriteRoles])
async def update_hero_v1(hero_id: int, hero: HeroV1Update, crud: HeroV1CRUD) -> HeroV1:
    """Partially update a hero via a v1-shaped payload."""
    updated = await crud.update(hero_id, hero)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return updated


@router.delete("/{hero_id:int}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[DeleteRoles])
async def delete_hero_v1(hero_id: int, crud: HeroV1CRUD) -> None:
    """Delete a hero."""
    deleted = await crud.delete(hero_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
