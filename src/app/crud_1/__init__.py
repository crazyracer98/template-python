"""Resource routers for the `/crud/v{ROUTER_VERSION}` API, combined into one router.

Each resource subpackage (e.g. `heroes/`) combines its own versioned sibling
routers into one router carrying its own resource-relative prefix (e.g.
`heroes/__init__.py`'s router already spans `/heroes/v1` and `/heroes/v2`) --
see `app.controllers.crud_router`'s `build_resource_router` for how one
version's own router is built. This module only combines each resource's
router into the one `router` `app.main` mounts at `/crud/v{ROUTER_VERSION}`,
so the router-version segment is named once, at that mount site, instead of
by every resource, and a new resource stays a single `include_router` call
here. Neither `include_router` call below takes a `prefix` -- each included
router already carries its own full, meaningful prefix, so there is no
further segment to add here.
"""

from fastapi import APIRouter

from app.crud_1.heroes import router as heroes_router

router = APIRouter()
router.include_router(heroes_router)
