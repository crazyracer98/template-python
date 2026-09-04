# app/

The FastAPI application package (`app.main:app`), laid out as an MVC-ish
split across subpackages, each with its own `README.md`:

- `models/` — the Model layer: SQLAlchemy ORM.
- `views/` — the View layer: Pydantic schemas.
- `controllers/` — the Controller layer: FastAPI routers.
- `repositories/` — storage-agnostic CRUD access, backing `crud/`.
- `crud/` — the generic CRUD interface built from a view + a repository.
- `health/` — the health check interface and registry.

`config.py`/`main.py`/`oidc.py`/`telemetry.py`/`problem_details.py`/
`http_headers.py`/`xml_codec.py`/`web_components.py` stay flat, outside
any subpackage — a flat module has no resource-specific code and no
state of its own beyond what it's explicitly passed or reads from
`app.config`.

- `config.py` — settings, read from environment variables; see
  "Configuration" and "MODE" below.
- `main.py` — FastAPI app instance, router wiring, and the lifespan hook
  that applies pending Alembic migrations on startup; see "Alembic
  migrations" below.
- `oidc.py` — provider-agnostic OIDC bearer-token validation (PKCE-
  compatible; not Keycloak-specific); see "OIDC / auth" below.
- `telemetry.py` — structured JSON logging setup; see "Structured
  logging / OTEL" below.
- `problem_details.py` — RFC 9457 error responses; see below.
- `http_headers.py` — the `Sunset`/`Deprecation` header dependency; see
  "Sunset/Deprecation headers" below.
- `xml_codec.py` / `web_components.py` — the generic XML and HTML-form
  rendering pieces a resource's sibling routers reuse; see
  `controllers/README.md`'s "Multi-format CRUD" section for the pattern.

## Layering

Import order between all of the above is strict and one-directional —
lower layers never import from higher ones (`config` → `telemetry` →
`problem_details` → `oidc` → `models` → `views` → `repositories` →
`crud` → `health` → `web_components` → `xml_codec` → `http_headers` →
`controllers` → `main`) — enforced by `import-linter`'s `layers`
contract in `../../pyproject.toml`'s `[tool.importlinter]`, run via `uv
run lint-imports` (wired into `../../.pre-commit-config.yaml`'s
manual/pre-push stage, same as mypy). A new subpackage or flat module
gets added to that `layers` list at the point matching its real
dependencies, not appended blindly to one end.

## Configuration

No application `.env` file: `config.py` reads settings from the process
environment only, which the compose files populate — see
`../../.devcontainer/stack/README.md`'s "Configuration" section for
where those values come from. `config.py` assembles any composed
connection string (`DATABASE_URL`) or renames a raw value to its own
generic field (`s3_access_key` from `RUSTFS_ACCESS_KEY`) at runtime,
since Compose can't interpolate a value from one env file into another
compose file's own env var. Values that are already a full, opaque,
provider-shaped string (the `OIDC_*` URLs) are written that way directly
in the owning service's env file instead, so `config.py` never has to
know a specific provider's URL scheme. Fixed in-network hostnames/ports
are not credentials and stay as plain literals in the consuming compose
file (e.g. `api`'s `POSTGRES_HOST: postgres`), not in an env file.

## Alembic migrations

Pending migrations apply automatically: `main.py`'s FastAPI `lifespan`
runs `alembic upgrade head` (off the event loop, via `asyncio.to_thread`
— Alembic's async recipe in `../../alembic/env.py` runs its own
`asyncio.run` internally, which can't nest inside one already running)
before the app starts serving. That only fires for a real ASGI startup
(`uvicorn`, the `runner` image, `tests/e2e`) — a bare `TestClient(app)`
in `tests/unit`/`tests/integration` never triggers lifespan, so those
suites need the schema already migrated; the devcontainer's own
`postCreateCommand` runs `uv run alembic upgrade head` once up front for
exactly that reason. `../../alembic.ini`/`../../alembic/` are resolved
relative to the current working directory (plain
`Config("alembic.ini")`), which is the repo root under the
devcontainer/pytest and `/app` in the `runner` image (see the
Dockerfile's `runner` stage, which `COPY`s both there) — never hardcode
a different path. See `../../alembic/README.md` for how migrations
themselves are authored.

`../../scripts/runner.sh` stays a plain entrypoint — migrations run from
Python, in `main.py`'s lifespan, never from the shell script.

## OIDC / auth

`../../.devcontainer/stack/keycloak/` runs Keycloak with dev-mode realm
auto-import; see its own `README.md` for the realm/client/test-user
details. `oidc.py` validates bearer tokens against it via generic OIDC
discovery + JWKS (`PyJWKClient`), with no Keycloak-specific code — any
Authorization Code + PKCE provider works by pointing
`OIDC_ISSUER_URL`/`OIDC_AUTHORIZATION_URL`/`OIDC_TOKEN_URL` elsewhere.
Add auth to a route with `Depends(get_current_claims)`; routes that
don't take that dependency stay public.

### RBAC

Each Keycloak test user carries one client role on the `api` client
matching that user's name (`viewer`/`editor`/`maintainer`/`security`/
`detective` — see `../../.devcontainer/stack/keycloak/README.md`).
`oidc.py`'s `require_roles(*roles)` builds a dependency reading
`claims["resource_access"][oidc_client_id]["roles"]` — Keycloak's
client-role claim shape specifically, not something assumed present on
every provider's token (unlike `get_current_claims`, which stays
provider-agnostic). Add a role requirement to a route with
`dependencies=[Depends(require_roles("editor", "maintainer"))]` — see
`controllers/README.md` for the reusable-constant pattern. A new
resource's routes pick their own role names/mapping; there's no fixed
role list beyond what `realm-export.json` defines.

## MODE (dev / mock / production)

`config.py`'s `Settings.mode` (env var `MODE`) is `"dev"`, `"mock"`, or
`"production"`, read once at import time everywhere it's used (the same
pattern as `get_settings()` generally) — it's a startup-time setting,
not a per-request one.

- `dev` (the default): `main.py` starts `debugpy` listening on `:5678`
  for a remote attach (non-blocking — never `wait_for_client()`) and sets
  FastAPI's `debug=True`. `../../.devcontainer/compose.yml` sets
  `MODE: dev`.
- `mock`: every external service is replaced with a local fake, so the
  app needs zero containers to boot — `repositories.memory.
  InMemoryRepository` instead of `SQLAlchemyRepository` (Alembic
  migrations are skipped entirely), `health.checks.MockHealthCheck`
  instead of the real per-service checks, and `oidc.
  decode_bearer_token` skips JWKS/network and trusts the token's claims
  as-is. `POST /mock/token` (`controllers.mock`, mounted only in this
  mode) issues a token shaped like a real Keycloak one (same
  `resource_access.<client>.roles` claim), so RBAC is exercisable
  without Keycloak too.
- `production`: no debugger. The `../../Dockerfile`'s `runner` stage
  sets `ENV MODE=production` as the single source of truth for that
  default.

A resource that wants `MODE=mock` support adds its own
`InMemoryRepository`-backed branch the way `controllers.heroes.
get_hero_crud` does — keep the dependency's signature identical across
modes (an unused `AsyncSession`'s `commit()` never opens a connection, so
depending on `get_db` unconditionally and branching on `settings.mode`
inside the function body is both simpler and satisfies mypy's
identical-conditional-signature check, versus two differently-signatured
functions).

## Structured logging / OTEL

`telemetry.py`'s `configure_logging()` (called once from `main.py`, at
import time) attaches a JSON-formatting handler to the root logger
unconditionally — every log call (including uvicorn's own) prints one
structured JSON line to stdout. If `OTEL_EXPORTER_OTLP_ENDPOINT` is set,
it additionally bridges the root logger to an OTLP log exporter. Logs
only, deliberately — no tracing/metrics instrumentation. OTEL's own env
vars (endpoint, headers, protocol, compression, certificate) are read
directly by `OTLPLogExporter()` itself, never re-modeled as `Settings`
fields — OTEL's env-var convention is already the single source of
truth for those.

## RFC 9457 error responses

`problem_details.py`'s `register_problem_handlers(app)` (called once
from `main.py`) turns every `HTTPException` (raised anywhere, e.g.
`controllers/heroes.py`'s `raise HTTPException(status.
HTTP_404_NOT_FOUND, ...)`, unchanged), FastAPI's request validation
errors, and any other unhandled exception into a single consistent
`application/problem+json` body — no route needs to build this itself.
A route that wants a specific `detail` message just raises
`HTTPException` normally.

## Sunset/Deprecation headers

`http_headers.py`'s `sunset(at, link=...)` is a reusable dependency
(`Depends(sunset(...))`) that sets RFC 8594's `Sunset` header (an
HTTP-date, not ISO 8601/IXDTF) plus a `Deprecation` header on a route —
see `controllers/protected.py` for the applied example. See
`views/README.md`'s `IXDTFDatetime` for how read views serialize their
own timestamps.

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

- Read from a `.env` file, or add one back — see the root `README.md`'s
  "Don't" section.
- Hardcode a real secret's value here — real secrets belong in
  `.secrets/`, referenced from a compose file.
- Assume a claim beyond `sub` is present on every provider's tokens —
  `decode_bearer_token`'s return value is whatever the provider's JWT
  contains, and that shape isn't guaranteed across providers.
- Import "up" the layering described above (e.g. `models/` importing
  from `controllers/`) — `uv run lint-imports` fails the build on it.
