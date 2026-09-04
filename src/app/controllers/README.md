# app/controllers/

The Controller layer: FastAPI routers, each `include_router`'d into
`app.main`'s `app`. Highest layer in `src/app/`'s import order — may
import from any other `app/` subpackage, but nothing else may import
from here (see `../README.md`'s "Layering" section).

- `health.py` — `/health/live` and `/health/ready`.
- `heroes.py` — `/heroes`, the example CRUD resource; see `../README.md`'s
  "Example CRUD resource: Hero".
- `heroes_xml.py` / `heroes_web.py` — sibling routers on `heroes.py`'s
  `/heroes` resource, see "Multi-format CRUD" below.
- `protected.py` — `/protected`, a minimal example of `Depends
  (get_current_claims)`.

## RBAC

Add a role requirement to a route with `dependencies=[Depends
(require_roles("editor", "maintainer"))]` from `app.oidc` (see
`../README.md`'s "RBAC" section for the mechanism), or a module-level
`Depends(...)` constant reused across a router's routes — see
`heroes.py`'s `ReadRoles`/`WriteRoles`/`DeleteRoles`.

## Multi-format CRUD

A resource's JSON CRUD router can grow sibling routers on separate
endpoints, following `heroes_xml.py`/`heroes_web.py`'s pattern: reuse
the JSON router's `<Resource>CRUD` dependency and role dependencies
directly (an intra-layer import — both routers stay in
`app.controllers`) rather than duplicating them. `app.xml_codec.
to_xml`/`from_xml` (generic over any flat Pydantic model) and
`app.web_components.render_crud_form`/`render_crud_component_js`
(generic over resource name/field list/API base path) are the reusable
pieces; only the router wiring is resource-specific. A route whose path
could otherwise collide with a resource's `/{id}` route (e.g.
`/heroes/xml`) needs that id parameter typed as `{id:int}` — Starlette's
typed path converter, so a non-integer literal segment never matches it,
regardless of router registration order.

## Do

- Add a new resource's router as its own module here, following
  `heroes.py`'s shape: a per-request `CRUDInterface` builder function
  (`get_<resource>_crud`, depended on via `Annotated[..., Depends(...)]`
  for reuse across that router's routes), then the routes themselves.
- Add auth to a route with `Depends(get_current_claims)` from
  `app.oidc` — a route with no such dependency is public.
- `include_router` a new router in `app.main`.

## Don't

- Put persistence or conversion logic directly in a route body — that
  belongs in `app.crud`/`app.repositories`; a route should stay a thin
  translation between HTTP and a `CRUDInterface` call.
