"""HTTP routes for the current (v2) Hero resource -- a worked example of the generic CRUD interface.

One `build_resource_router` call builds the JSON/XML/web sibling routes
together. `prefix=""` here deliberately: this router carries none of its
own mount prefix -- `app.crud_1.heroes`'s `__init__.py` is the one that
assigns `/heroes/v2` explicitly, via `include_router(router, prefix=...)`,
when it combines this with the deprecated `heroes_v1.py` sibling into the
one `router` `app.crud_1` mounts. See `crud_1/README.md`'s "Don't" section
for why a resource-version router should never bake in its own prefix.
`api_prefix` is still the full absolute path, though -- see
`crud_router.py`'s "Generic CRUD router factories" and `docs/adrs/0009-...md`.
"""

from typing import Annotated

from fastapi import Depends

from app.controllers.crud_router import ROUTER_VERSION, build_resource_router
from app.interfaces.base import CRUDInterface
from app.interfaces.dependency import build_repository_provider
from app.models.base import DBSession
from app.models.hero import Hero as HeroModel
from app.oidc import require_roles
from app.views.hero_v2 import HeroV2, HeroV2Create, HeroV2Update

_hero_repository = build_repository_provider(HeroModel)


def get_hero_crud(session: DBSession) -> CRUDInterface[HeroV2, HeroModel]:
    """Build a request-scoped CRUD interface for Hero.

    MODE=mock uses the shared in-memory repository instead of `session` -- an
    unused AsyncSession's commit() never opens a connection, so `session` stays a
    harmless, uniform dependency across every mode rather than needing two
    differently-signatured variants of this function.
    """
    return CRUDInterface(schema=HeroV2, repository=_hero_repository(session))


HeroCRUD = Annotated[CRUDInterface[HeroV2, HeroModel], Depends(get_hero_crud)]

ReadRoles = Depends(require_roles("viewer", "editor", "maintainer", "detective"))
WriteRoles = Depends(require_roles("editor", "maintainer"))
DeleteRoles = Depends(require_roles("maintainer"))

router = build_resource_router(
    prefix="",
    api_prefix=f"/crud/v{ROUTER_VERSION}/heroes/v2",
    tags=["heroes"],
    resource_label="Hero",
    resource="hero",
    item_tag="hero",
    list_tag="heroes",
    fields=("name", "powers"),
    schema=HeroV2,
    create_schema=HeroV2Create,
    update_schema=HeroV2Update,
    crud_dependency=HeroCRUD,
    read_roles=ReadRoles,
    write_roles=WriteRoles,
    delete_roles=DeleteRoles,
)
