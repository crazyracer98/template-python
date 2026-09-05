# app/resources/

Resource routers: one subpackage per resource, each combining that
resource's versioned sibling routers (built from `../controllers/`'s
generic factories) into the single router `app.main` mounts. Sits after
`controllers` in `src/app/`'s import order — may import from
`app.controllers` (its generic router factories) or any lower layer, but
nothing else may import from here except `main` (see `../README.md`'s
"Layering" section).

- `heroes/` — the example CRUD resource; see `../README.md`'s "Example
  CRUD resource: Hero".
  - `heroes_v2.py` — `/crud/v1/heroes/v2/{json,xml,web}`, the current
    Hero shape.
  - `heroes_v1.py` — `/crud/v1/heroes/v1/{json,xml,web}`, the deprecated
    sibling version; see "API and model versioning" below.
  - `__init__.py` — combines `heroes_v2.py`/`heroes_v1.py`'s routers
    into the one `router` `main.py` mounts.

## Multi-version resources as a package

A resource that carries more than one API version (see "API and model
versioning" below) gets its own package here rather than a single
module, so each version's controller stays its own file (`heroes_v2.py`,
`heroes_v1.py`, ...) instead of accreting an ever-longer suffix pile in
one module. The package's `__init__.py` is the only thing `app.main`
ever imports for that resource — it combines every version's own
already-full-prefixed router (each built by
`app.controllers.crud_router.build_resource_router`, see
`../controllers/README.md`'s "Generic CRUD router factories") into one
`router`, so a resource stays a single `include_router` call at the
mount site no matter how many versions it carries internally:

```python
router = APIRouter()
router.include_router(heroes_v2_router)
router.include_router(heroes_v1_router)
```

Neither `include_router` call above takes a `prefix` — each included
router already carries its own full, meaningful prefix from its own
`build_resource_router(prefix=...)` call, so there is no further segment
to add here. A resource simple enough to never need more than one
version can skip the package shape and stay a single flat module
instead (still living here, not in `controllers/`) — the package layout
is what a *versioned* resource needs, not a rule every resource follows.

## API and model versioning

A resource's routes are versioned along three independent, explicit path
segments: `/crud/v{router_version}/heroes/v{model_version}/{format}` —
e.g. `/crud/v1/heroes/v2/json` (current Hero shape), `/crud/v1/heroes/v1/xml`
(deprecated shape), `/crud/v1/heroes/v2/web/form`. There is no bare
unversioned alias on any of the three axes; callers pick a router
version, a resource-shape version, and a format explicitly. See
`docs/adrs/0009-explicit-crud-router-and-model-versioning-segments.md`
for the full reasoning; it supersedes
`docs/adrs/0002-api-and-model-versioning.md`.

`router_version` (`app.controllers.crud_router`'s `ROUTER_VERSION`
constant) names a version of the generic router factories themselves,
not a resource's shape — every resource imports it rather than
hardcoding `"v1"`. The DB model (`app.models`) always represents the
*current* shape only — an older API version is a `views` + `crud`
concern, never a second table/model. Only `app.views` classes carry a
numeric suffix, current version included (e.g. `views/hero_v2.py`'s
`HeroV2*`, matching the already-suffixed `views/hero_v1.py`'s
`HeroV1*`).

A deprecated version follows the `*_vN.py` pattern: a `views/hero_vN.py`
module defining that version's Pydantic shape plus pure converter
functions to/from the current version's views (see
`app.views.hero_v1`), and a sibling controller module (`heroes_v1.py`)
that calls the same `build_resource_router` `../controllers/README.md`'s
"Generic CRUD router factories" describes, with `crud_dependency`
pointing at a `CompatCRUD`-typed dependency instead of a
`CRUDInterface`-typed one. `app.crud.compat.CompatCRUD` is the reusable
wrapper that adapts the current version's `CRUDInterface` to speak in
the deprecated view's shape, so the deprecated router needs no new
persistence wiring — see `app.crud.README.md`. Apply
`app.http_headers.sunset(...)` via the deprecated resource-version's
`router_dependencies=[...]` `build_resource_router` argument (not per
format) so every route under it — JSON/XML/web alike — advertises
`Sunset`/`Deprecation`/`Link` headers at once; a router's own
`dependencies` merge into every route of a sub-router later
`include_router`'d into it, so one declaration on the combined router
reaches all three formats. Because that's now a single shared
declaration rather than one per format, the `Link` header points at the
successor resource-version's base path (e.g. `/crud/v1/heroes/v2`), not
a format-specific equivalent.

## Do

- Add a new resource as its own subpackage here (or a flat module, if it
  will never carry more than one version): a per-request `CRUDInterface`
  builder function (`get_<resource>_crud`, depended on via
  `Annotated[..., Depends(...)]` for reuse across that router's routes,
  following `heroes/heroes_v2.py`'s shape — `app.crud.dependency.
  build_repository_provider` supplies the MODE-aware repository it
  wraps), then one `app.controllers.crud_router.build_resource_router(...)`
  call (or a single `build_json_router(...)` call directly, for a
  resource that only ever needs JSON).
- `include_router` a new resource's router in `app.main`.

## Don't

- Put persistence or conversion logic directly in a route body — that
  belongs in `app.crud`/`app.repositories`; a route should stay a thin
  translation between HTTP and a `CRUDInterface` call.
- Add resource-agnostic router-building logic here — a new generic
  factory (usable by any resource) belongs in
  `app.controllers.crud_router`, not duplicated inside a resource
  package.
