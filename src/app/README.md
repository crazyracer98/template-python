# app/

The FastAPI application package (`app.main:app`), laid out as an MVC-ish
split across subpackages, each with its own `README.md`:

- `models/` — the Model layer: SQLAlchemy ORM.
- `views/` — the View layer: Pydantic schemas.
- `controllers/` — the Controller layer: FastAPI routers.
- `repositories/` — storage-agnostic CRUD access, backing `crud/`.
- `crud/` — the generic CRUD interface built from a view + a repository.
- `health/` — the health check interface and registry.

`main.py`, `config.py`, and `oidc.py` stay flat, outside any subpackage.

- `main.py` — FastAPI app instance, router wiring, and the lifespan hook
  that applies pending Alembic migrations on startup.
- `oidc.py` — provider-agnostic OIDC bearer-token validation (PKCE-
  compatible; not Keycloak-specific).
- `config.py` — settings, read from environment variables.

See the root `CLAUDE.md`'s "src/app/ layering" section for the strict,
`import-linter`-enforced import order between these, and its "Alembic
migrations" section for how startup migrations work.

## Example CRUD resource: Hero

`models/hero.py` / `views/hero.py` / `controllers/heroes.py` are a
worked example of the generic CRUD interface, wired up as `/heroes`
(list/create/get/update/delete — see `controllers/heroes.py`). Adding
another resource follows the same three-file shape: an `IdentifiedBase`
subclass in `models/`, an `ORMView` subclass (plus `*Create`/`*Update`
variants) in `views/`, and a router in `controllers/` that builds a
`CRUDInterface(schema=<View>, repository=SQLAlchemyRepository(session,
<Model>))` per request — see `crud/README.md` and
`repositories/README.md` for what each side of that call does.

## Do

- Add new settings as typed fields on `Settings` in `config.py`, sourced
  from the compose files' `environment:` blocks.
- Annotate every function signature — `mypy --strict` and ruff's `ANN`
  rules both require it.
- Add auth to a new route with `Depends(get_current_claims)` from
  `oidc.py` — a route with no such dependency is public.
- Register a new external service's health check with
  `HealthRegistry.register` in `health/registry.py`'s
  `get_health_registry` — see `health/README.md`.

## Don't

- Read from a `.env` file, or add one back — see the root `CLAUDE.md`.
- Hardcode a real secret's value here — real secrets belong in
  `.secrets/`, referenced from a compose file.
- Assume a claim beyond `sub` is present on every provider's tokens —
  `decode_bearer_token`'s return value is whatever the provider's JWT
  contains, and that shape isn't guaranteed across providers.
- Import "up" the layering CLAUDE.md describes (e.g. `models/` importing
  from `controllers/`) — `uv run lint-imports` fails the build on it.
