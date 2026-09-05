"""HTTP routes for /crud/v{ROUTER_VERSION}/heroes/v1 -- the deprecated single-power Hero shape.

Deprecated in favor of /crud/v{ROUTER_VERSION}/heroes/v2 (app.controllers.heroes),
which supports multiple powers per hero. Wraps the same CRUD app.controllers.heroes
already builds via app.crud.compat.CompatCRUD, converting to/from the v1
view with app.views.hero_v1's converter functions -- no new persistence
code, only the version-compatibility shape.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends

from app.controllers.crud_router import ROUTER_VERSION, build_resource_router
from app.controllers.heroes import DeleteRoles, HeroCRUD, ReadRoles, WriteRoles
from app.crud.compat import CompatCRUD
from app.http_headers import sunset
from app.models.hero import Hero as HeroModel
from app.views.hero_v1 import (
    HeroV1,
    HeroV1Create,
    HeroV1Update,
    hero_v1_create_to_v2,
    hero_v1_update_to_v2,
    hero_v2_to_v1,
)
from app.views.hero_v2 import HeroV2

SUNSET_AT = datetime(2027, 1, 1, tzinfo=UTC)
_V2_PREFIX = f"/crud/v{ROUTER_VERSION}/heroes/v2"


def get_hero_v1_crud(crud: HeroCRUD) -> CompatCRUD[HeroV1, HeroV2, HeroModel]:
    """Build a v1-shaped CRUD interface backed by the current (v2) Hero CRUD."""
    return CompatCRUD(
        crud,
        to_legacy=hero_v2_to_v1,
        from_legacy_create=hero_v1_create_to_v2,
        from_legacy_update=hero_v1_update_to_v2,
    )


HeroV1CRUD = Annotated[CompatCRUD[HeroV1, HeroV2, HeroModel], Depends(get_hero_v1_crud)]

router = build_resource_router(
    prefix=f"/crud/v{ROUTER_VERSION}/heroes/v1",
    tags=["heroes"],
    resource_label="Hero",
    resource="hero",
    item_tag="hero",
    list_tag="heroes",
    fields=("name", "superpower"),
    schema=HeroV1,
    create_schema=HeroV1Create,
    update_schema=HeroV1Update,
    crud_dependency=HeroV1CRUD,
    read_roles=ReadRoles,
    write_roles=WriteRoles,
    delete_roles=DeleteRoles,
    router_dependencies=[Depends(sunset(SUNSET_AT, link=_V2_PREFIX))],
)
