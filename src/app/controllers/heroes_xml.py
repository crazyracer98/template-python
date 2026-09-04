"""HTTP routes for /heroes/xml -- the same Hero CRUD operations, in XML.

Reuses app.controllers.heroes's CRUD dependency/RBAC dependencies directly rather
than duplicating them (same "controllers" import-linter layer, so this is an
intra-layer import, not a cross-layer one).
"""

from app.controllers.crud_router import build_xml_router
from app.controllers.heroes import DeleteRoles, HeroCRUD, ReadRoles, WriteRoles
from app.views.hero import HeroCreate, HeroUpdate

router = build_xml_router(
    prefix="/heroes/xml",
    tags=["heroes"],
    resource_label="Hero",
    item_tag="hero",
    list_tag="heroes",
    create_schema=HeroCreate,
    update_schema=HeroUpdate,
    crud_dependency=HeroCRUD,
    read_roles=ReadRoles,
    write_roles=WriteRoles,
    delete_roles=DeleteRoles,
)
