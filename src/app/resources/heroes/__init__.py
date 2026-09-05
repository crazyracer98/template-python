"""HTTP routes for the Hero resource: the current (v2) and deprecated (v1) sibling versions.

`heroes_v2.py`/`heroes_v1.py` each build their own full-prefixed
`build_resource_router(...)` router (see `app.controllers.crud_router`'s
"Generic CRUD router factories"); this module only combines the two into the
one `router` `main.py` mounts, so a resource that gains further versions
stays a single `include_router` call at the mount site regardless of how many
versions it carries internally. Neither `include_router` call below takes a
`prefix` -- each included router already carries its own full, meaningful
prefix from its own `build_resource_router(prefix=...)` call, so there is no
further segment to add here.
"""

from fastapi import APIRouter

from app.resources.heroes.heroes_v1 import router as heroes_v1_router
from app.resources.heroes.heroes_v2 import router as heroes_v2_router

router = APIRouter()
router.include_router(heroes_v2_router)
router.include_router(heroes_v1_router)
