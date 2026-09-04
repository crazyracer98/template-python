"""HTTP routes for /v1/heroes/form and /v1/heroes/components.js.

The deprecated single-power Hero shape's zero-JS HTML form and web-component
JS -- see app.controllers.heroes_web for the v2 counterpart this mirrors, and
app.web_components for the reusable templates both are built from. Reuses
app.controllers.heroes_v1's CRUD/RBAC dependencies directly, same as
app.controllers.heroes_v1_xml. Also applies the same sunset(...) router
dependency heroes_v1.py does, so form/JS responses carry the same
Sunset/Deprecation/Link headers as the JSON v1 routes.
"""

from fastapi import Depends

from app.controllers.crud_router import build_web_router
from app.controllers.heroes_v1 import SUNSET_AT, HeroV1CRUD, ReadRoles, WriteRoles
from app.http_headers import sunset
from app.views.hero_v1 import HeroV1Create

router = build_web_router(
    prefix="/heroes",
    tags=["heroes"],
    resource="hero",
    api_base="/v1/heroes",
    fields=("name", "superpower"),
    create_schema=HeroV1Create,
    crud_dependency=HeroV1CRUD,
    read_roles=ReadRoles,
    write_roles=WriteRoles,
    router_dependencies=[Depends(sunset(SUNSET_AT, link="/v2/heroes"))],
)
