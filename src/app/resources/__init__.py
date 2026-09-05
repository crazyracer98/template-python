"""Resource routers: one subpackage per resource (e.g. `heroes/`).

Each subpackage combines its versioned sibling routers into the single
router `app.main` mounts -- see `app.controllers.crud_router`'s
`build_resource_router` for how one version's own router is built, and
`heroes/__init__.py` for how a resource's versions combine into one.
"""
