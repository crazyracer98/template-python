"""HTTP routes for /v1/heroes/form and /v1/heroes/components.js.

The deprecated single-power Hero shape's zero-JS HTML form and web-component
JS -- see app.controllers.heroes_web for the v2 counterpart this mirrors, and
app.web_components for the reusable templates both are built from. Reuses
app.controllers.heroes_v1's CRUD/RBAC dependencies directly, same as
app.controllers.heroes_v1_xml.
"""

from typing import Annotated

from fastapi import APIRouter, Form, status
from fastapi.responses import RedirectResponse, Response

from app.controllers.heroes_v1 import HeroV1CRUD, ReadRoles, WriteRoles
from app.views.hero_v1 import HeroV1Create
from app.web_components import render_crud_component_js, render_crud_form

router = APIRouter(prefix="/heroes", tags=["heroes"])

_FIELDS = ("name", "superpower")
_API_BASE = "/v1/heroes"


@router.get("/form", dependencies=[ReadRoles])
async def hero_v1_form() -> Response:
    """Serve the zero-JS Hero form + web-component demo page, in the deprecated v1 shape."""
    return Response(
        content=render_crud_form("hero", _FIELDS, _API_BASE),
        media_type="text/html",
    )


@router.post("/form", status_code=status.HTTP_303_SEE_OTHER, dependencies=[WriteRoles])
async def submit_hero_v1_form(
    crud: HeroV1CRUD,
    name: Annotated[str, Form()],
    superpower: Annotated[str, Form()],
) -> RedirectResponse:
    """Create a hero from a plain HTML form submission and redirect back to the form."""
    await crud.create(HeroV1Create(name=name, superpower=superpower))
    return RedirectResponse(f"{_API_BASE}/form", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/components.js")
async def hero_v1_components_js() -> Response:
    """Serve the vanilla-JS custom elements for the deprecated v1 Hero shape."""
    return Response(
        content=render_crud_component_js("hero", _API_BASE, _FIELDS),
        media_type="application/javascript",
    )
