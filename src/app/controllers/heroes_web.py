"""HTTP routes for /heroes/form and /heroes/components.js.

A zero-JS HTML form (progressively enhanced with the web components served from
/heroes/components.js) and the JS itself -- see app.web_components for the
reusable templates both are built from. Reuses app.controllers.heroes's CRUD/RBAC
dependencies directly, same as app.controllers.heroes_xml.
"""

from app.controllers.crud_router import build_web_router
from app.controllers.heroes import HeroCRUD, ReadRoles, WriteRoles
from app.views.hero import HeroCreate

router = build_web_router(
    prefix="/heroes",
    tags=["heroes"],
    resource="hero",
    api_base="/v2/heroes",
    fields=("name", "powers"),
    create_schema=HeroCreate,
    crud_dependency=HeroCRUD,
    read_roles=ReadRoles,
    write_roles=WriteRoles,
)
