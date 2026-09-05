# app/controllers/

The Controller layer: FastAPI routers, each `include_router`'d into
`app.main`'s `app`. Highest layer in `src/app/`'s import order — may
import from any other `app/` subpackage, but nothing else may import
from here (see `../README.md`'s "Layering" section).

- `health.py` — `/health/live` and `/health/ready`.
- `heroes.py` — `/crud/v1/heroes/v2/{json,xml,web}`, the example CRUD
  resource; see `../README.md`'s "Example CRUD resource: Hero".
- `heroes_v1.py` — the deprecated `/crud/v1/heroes/v1/{json,xml,web}`
  sibling version, see "API and model versioning" below.
- `protected.py` — `/protected`, a minimal example of `Depends
  (get_current_claims)`.

## RBAC

Add a role requirement to a route with `dependencies=[Depends
(require_roles("editor", "maintainer"))]` from `app.oidc` (see
`../README.md`'s "RBAC" section for the mechanism), or a module-level
`Depends(...)` constant reused across a router's routes — see
`heroes.py`'s `ReadRoles`/`WriteRoles`/`DeleteRoles`.

## Generic CRUD router factories

`crud_router.py`'s `build_json_router`/`build_xml_router`/`build_web_router`
build a resource's list/create/get/update/delete routes (or, for
`build_web_router`, its `/form` + `/components.js` routes) internally, as
closures over the Pydantic views and CRUD dependency passed to them.
`build_resource_router` composes all three into one resource-version's
combined `APIRouter`, mounting each under its own `/json`/`/xml`/`/web`
sub-prefix — `heroes.py`/`heroes_v1.py` are one `build_resource_router(...)`
call each, not three separate per-format router modules; see "API and
model versioning" below and `docs/adrs/0009-...md` for the full path
shape. Each factory takes `crud_dependency` as an
`Annotated[app.crud.base.CRUDLike[...], Depends(...)]`-shaped value —
`CRUDLike` is a `Protocol` both `CRUDInterface` (current version) and
`CompatCRUD` (deprecated version, see "API and model versioning" below)
satisfy structurally, so the same factories build both.

**Record addressing, filtering/sorting, and bulk actions** (`build_json_router`/
`build_xml_router`): a single record is addressed by an `id` query
parameter, not a path segment — `GET/PATCH/DELETE <prefix>?id=5`, 404 if
missing. `id` names the query key regardless of a resource's own id-field
name, the same way every generated route used to name its path parameter
`record_id` before addressing moved off the path. Without `id`, `GET` lists
(optionally filtered/sorted, see
`app.controllers.crud_query`'s module docstring for the `field__op=value`/
`sort=` wire format) and `PATCH`/`DELETE` act in bulk over whatever filters
are given — a request with **no** filters and no `id` is rejected (422 via
`RequestValidationError`) rather than silently acting on every record.
`app.controllers.crud_actions`'s `resolve_list_or_get`/`resolve_update`/
`resolve_delete` implement this id/filter/bulk decision once, shared by both
factories; each wraps the same calls in its own response format (JSON body
vs. an XML-rendered `Response`). Before a bulk update/delete actually runs,
`crud_actions.py` counts how many records the filters match
(`CRUDLike.count`) and refuses the action (400) above
`app.config.Settings.bulk_action_max_matched` (default 1000) — a
technically-non-empty but always-true filter (e.g. `id__gte=0`) would
otherwise still match every row. A bulk action that does run is logged
(`INFO`, actor/path/filters/ids) for auditing, and is itself rate-limited —
see `app/README.md`'s "Rate limiting". A bulk action's response
(`app.views.bulk.BulkUpdateResult`/`BulkDeleteResult`) carries the matched
count and the ids affected, not the full records. `build_json_router` also
serves `GET <prefix>/filters`, the same per-field-type introspection
`crud_query.py` uses to parse, as JSON — the `<resource>-list>` web component
(`app.web_components`) fetches this once to render filter/sort/bulk controls
generically, without either side hardcoding a resource's fields.

The generated route functions' `crud`/`record` parameters are annotated
with a TypeVar-bound runtime value (e.g. `create_schema`, a `type[CreateT]`
parameter of the enclosing factory) — mypy cannot resolve that statically,
so those specific lines carry a narrow `# type: ignore[valid-type]`/
`# type: ignore[no-any-return]`, justified by `crud_router.py`'s own module
docstring; the factories' own public signatures stay fully strict-typed, so
a caller like `heroes.py` gets normal type-checking on its
`build_json_router(...)` call.

`build_xml_router`/`build_web_router`'s routes construct and return their
own `Response`/`RedirectResponse` directly (XML bodies, redirects, JS) —
FastAPI does **not** merge a `dependencies=[...]` entry's `response.headers`
mutations (e.g. `app.http_headers.sunset(...)`, see "API and model
versioning" below) into a route's own returned `Response`, only into its
own auto-built one, so every such route also takes the injected
`response: Response` and merges it in via `crud_router.py`'s private
`_with_dependency_headers` before returning. Skipping this silently drops
router-level headers on every XML/web route with no visible error — this
bit the deprecated v1 XML/web routes once, before the helper was
introduced (see "API and model versioning").

`build_web_router`'s `/form` POST route parses `Request.form()` generically
(field names aren't known until the factory is called, so a typed
`Form()` parameter per field isn't possible) — it attaches an
`openapi_extra` describing each field as a required string so Swagger UI
still documents the submission shape, rather than showing an undocumented
body.

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

`router_version` (`crud_router.py`'s `ROUTER_VERSION` constant) names a
version of the generic router factories themselves, not a resource's
shape — every resource imports it rather than hardcoding `"v1"`. The DB
model (`app.models`) always represents the *current* shape only — an
older API version is a `views` + `crud` concern, never a second
table/model. Only `app.views` classes carry a numeric suffix, current
version included (e.g. `views/hero_v2.py`'s `HeroV2*`, matching the
already-suffixed `views/hero_v1.py`'s `HeroV1*`).

A deprecated version follows the `*_vN.py` pattern: a `views/hero_vN.py`
module defining that version's Pydantic shape plus pure converter
functions to/from the current version's views (see
`app.views.hero_v1`), and a sibling controller module (`heroes_v1.py`)
that calls the same `build_resource_router` "Generic CRUD router
factories" above describes, with `crud_dependency` pointing at a
`CompatCRUD`-typed dependency instead of a `CRUDInterface`-typed one.
`app.crud.compat.CompatCRUD` is the reusable wrapper that adapts the
current version's `CRUDInterface` to speak in the deprecated view's
shape, so the deprecated router needs no new persistence wiring — see
`app.crud.README.md`. Apply `app.http_headers.sunset(...)` via the
deprecated resource-version's `router_dependencies=[...]`
`build_resource_router` argument (not per format) so every route under
it — JSON/XML/web alike — advertises `Sunset`/`Deprecation`/`Link`
headers at once; a router's own `dependencies` merge into every route of
a sub-router later `include_router`'d into it, so one declaration on the
combined router reaches all three formats. Because that's now a single
shared declaration rather than one per format, the `Link` header points
at the successor resource-version's base path (e.g.
`/crud/v1/heroes/v2`), not a format-specific equivalent.

## Do

- Add a new resource's router as its own module here: a per-request
  `CRUDInterface` builder function (`get_<resource>_crud`, depended on via
  `Annotated[..., Depends(...)]` for reuse across that router's routes,
  following `heroes.py`'s shape — `app.crud.dependency.
  build_repository_provider` supplies the MODE-aware repository it wraps),
  then one `build_resource_router(...)` call (or a single
  `build_json_router(...)` call directly, for a resource that only ever
  needs JSON — see "Generic CRUD router factories" above).
- Add auth to a route with `Depends(get_current_claims)` from
  `app.oidc` — a route with no such dependency is public.
- `include_router` a new router in `app.main`.

## Don't

- Put persistence or conversion logic directly in a route body — that
  belongs in `app.crud`/`app.repositories`; a route should stay a thin
  translation between HTTP and a `CRUDInterface` call.
