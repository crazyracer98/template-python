"""HTTP routes for /v1/heroes/xml -- the deprecated single-power Hero shape, in XML.

Reuses app.controllers.heroes_v1's CRUD dependency/RBAC dependencies directly
rather than duplicating them (same "controllers" import-linter layer, so this
is an intra-layer import, not a cross-layer one). Also applies the same
sunset(...) router dependency heroes_v1.py does, so XML responses carry the
same Sunset/Deprecation/Link headers as the JSON v1 routes.
"""

from fastapi import Depends

from app.controllers.crud_router import build_xml_router
from app.controllers.heroes_v1 import SUNSET_AT, DeleteRoles, HeroV1CRUD, ReadRoles, WriteRoles
from app.http_headers import sunset
from app.views.hero_v1 import HeroV1Create, HeroV1Update

router = build_xml_router(
    prefix="/heroes/xml",
    tags=["heroes"],
    resource_label="Hero",
    item_tag="hero",
    list_tag="heroes",
    create_schema=HeroV1Create,
    update_schema=HeroV1Update,
    crud_dependency=HeroV1CRUD,
    read_roles=ReadRoles,
    write_roles=WriteRoles,
    delete_roles=DeleteRoles,
    router_dependencies=[Depends(sunset(SUNSET_AT, link="/v2/heroes/xml"))],
)
