"""HTTP routes for /v1/heroes/xml -- the deprecated single-power Hero shape, in XML.

Reuses app.controllers.heroes_v1's CRUD dependency/RBAC dependencies directly
rather than duplicating them (same "controllers" import-linter layer, so this
is an intra-layer import, not a cross-layer one).
"""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.controllers.heroes_v1 import (
    DeleteRoles,
    HeroV1CRUD,
    ReadRoles,
    WriteRoles,
)
from app.views.hero_v1 import HeroV1Create, HeroV1Update
from app.xml_codec import from_xml, to_xml

router = APIRouter(prefix="/heroes/xml", tags=["heroes"])

_XML_MEDIA_TYPE = "application/xml"


@router.get("", dependencies=[ReadRoles])
async def list_heroes_v1_xml(crud: HeroV1CRUD, skip: int = 0, limit: int = 100) -> Response:
    """List heroes as an XML document, in the deprecated v1 shape."""
    heroes = await crud.list(skip=skip, limit=limit)
    body = "<heroes>" + "".join(to_xml(hero, "hero") for hero in heroes) + "</heroes>"
    return Response(content=body, media_type=_XML_MEDIA_TYPE)


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[WriteRoles])
async def create_hero_v1_xml(crud: HeroV1CRUD, request: Request) -> Response:
    """Create a hero from a v1-shaped XML request body."""
    hero = from_xml(await request.body(), HeroV1Create)
    created = await crud.create(hero)
    return Response(
        content=to_xml(created, "hero"),
        media_type=_XML_MEDIA_TYPE,
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/{hero_id:int}", dependencies=[ReadRoles])
async def get_hero_v1_xml(hero_id: int, crud: HeroV1CRUD) -> Response:
    """Get a hero by id, as an XML document, in the deprecated v1 shape."""
    hero = await crud.get(hero_id)
    if hero is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return Response(content=to_xml(hero, "hero"), media_type=_XML_MEDIA_TYPE)


@router.patch("/{hero_id:int}", dependencies=[WriteRoles])
async def update_hero_v1_xml(hero_id: int, crud: HeroV1CRUD, request: Request) -> Response:
    """Partially update a hero from a v1-shaped XML request body."""
    hero = from_xml(await request.body(), HeroV1Update)
    updated = await crud.update(hero_id, hero)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return Response(content=to_xml(updated, "hero"), media_type=_XML_MEDIA_TYPE)


@router.delete("/{hero_id:int}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[DeleteRoles])
async def delete_hero_v1_xml(hero_id: int, crud: HeroV1CRUD) -> None:
    """Delete a hero."""
    deleted = await crud.delete(hero_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
