"""HTTP routes for /heroes/form and /heroes/components.js.

A zero-JS HTML form (progressively enhanced with the web components served from
/heroes/components.js) and the JS itself -- see app.web_components for the
reusable templates both are built from. Reuses app.controllers.heroes's CRUD/RBAC
dependencies directly, same as app.controllers.heroes_xml.
"""

from typing import Annotated

from fastapi import APIRouter, Form, status
from fastapi.responses import RedirectResponse, Response

from app.controllers.heroes import HeroCRUD, ReadRoles, WriteRoles
from app.views.hero import HeroCreate
from app.web_components import render_crud_component_js, render_crud_form

router = APIRouter(prefix="/heroes", tags=["heroes"])

_FIELDS = ("name", "superpower")


@router.get("/form", dependencies=[ReadRoles])
async def hero_form() -> Response:
    """Serve the zero-JS Hero form + web-component demo page."""
    return Response(
        content=render_crud_form("hero", _FIELDS, "/heroes"),
        media_type="text/html",
    )


@router.post("/form", status_code=status.HTTP_303_SEE_OTHER, dependencies=[WriteRoles])
async def submit_hero_form(
    crud: HeroCRUD,
    name: Annotated[str, Form()],
    superpower: Annotated[str, Form()],
) -> RedirectResponse:
    """Create a hero from a plain HTML form submission and redirect back to the form."""
    await crud.create(HeroCreate(name=name, superpower=superpower))
    return RedirectResponse("/heroes/form", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/components.js")
async def hero_components_js() -> Response:
    """Serve the vanilla-JS custom elements for the Hero resource."""
    return Response(
        content=render_crud_component_js("hero", "/heroes", _FIELDS),
        media_type="application/javascript",
    )
