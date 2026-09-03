# app/controllers/

The Controller layer: FastAPI routers, each `include_router`'d into
`app.main`'s `app`. Highest layer in `src/app/`'s import order — may
import from any other `app/` subpackage, but nothing else may import
from here (see the root `CLAUDE.md`'s "src/app/ layering" section).

- `health.py` — `/health/live` and `/health/ready`.
- `heroes.py` — `/heroes`, the example CRUD resource; see `../README.md`'s
  "Example CRUD resource: Hero".
- `protected.py` — `/protected`, a minimal example of `Depends
  (get_current_claims)`.

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
