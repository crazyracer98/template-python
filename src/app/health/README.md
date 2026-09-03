# app/health/

The health check interface: a registry of checks against every external
service the app depends on, backing `app.controllers.health`'s
`/health/live` (liveness — no dependency checks) and `/health/ready`
(readiness — runs every registered check) routes.

- `base.py` — `HealthCheck`, the `Protocol` every check implements
  (a `name` and an async `check() -> HealthCheckResult`), and
  `HealthCheckResult` itself.
- `registry.py` — `HealthRegistry` (`register`/`run_all`, the latter
  running every check concurrently via `asyncio.gather`) and
  `get_health_registry`, an `lru_cache`d factory (matching
  `app.config.get_settings`'s pattern) that registers one check per
  external service.
- `checks.py` — the concrete checks: `DatabaseHealthCheck` (Postgres,
  via the app's own async engine), `RedisHealthCheck`, `S3HealthCheck`
  (boto3, run in a thread via `asyncio.to_thread` — no async S3 client
  dependency needed for one lightweight `ListBuckets` call), and
  `OIDCHealthCheck` (fetches the provider's discovery document).

## Do

- Register a new external service's check in `registry.py`'s
  `get_health_registry`, as its own `HealthCheck` in `checks.py` —
  catch that service's own client library's narrow exception type
  (e.g. `RedisError`, not bare `Exception`) so a real bug elsewhere
  doesn't get silently reported as "service unhealthy".

## Don't

- Import from `app.controllers` — see the root `CLAUDE.md`'s
  "src/app/ layering" section. `app.models`/`app.oidc`/`app.config` are
  fine (`DatabaseHealthCheck` takes the app's own engine;
  `OIDCHealthCheck` reimplements just the discovery-URL fetch, not a
  full import of `app.oidc`, to stay a plain HTTP reachability check).
- Let one check's failure raise out of `HealthRegistry.run_all` — every
  concrete check catches its own service's exceptions and returns an
  unhealthy `HealthCheckResult` instead, so one down dependency doesn't
  take the whole readiness response down with it.
