# Top-level compose.yml + CI smoke test for the runner image

## Status

Draft

## Goal

Right now the `runner` stage (the production image built by
`Dockerfile`, see its "runner" comment and `.github/workflows/release.yml`)
is never actually started anywhere in CI — `checks.yml` only exercises the
`develop` stage via the devcontainer. Add a root-level `compose.yml` that
runs the built `runner` image against the same backing services as the
devcontainer (Postgres, RustFS, Redis, Keycloak), and a GitHub Actions
workflow that brings that stack up and confirms `/health/live` and
`/health/ready` both return 200 — catching a runner-stage regression
(missing env var, broken migration, bad entrypoint) before a release ships.

## Approach

### Root `compose.yml`

New file at the repo root (sibling to `Dockerfile`, distinct from
`.devcontainer/compose.yml`), used only for this smoke test — not
referenced by `devcontainer.json`. `include:`s the same four stack
fragments that hold the runner's actual runtime dependencies:

```yaml
include:
  - ./.devcontainer/stack/postgres/compose.yml
  - ./.devcontainer/stack/s3/compose.yml
  - ./.devcontainer/stack/keycloak/compose.yml
  - ./.devcontainer/stack/redis/compose.yml
```

`selenium` is deliberately left out — it's only there for the e2e suite's
browser driving (`tests/e2e/README.md`), not for anything `/health/ready`
checks, and pulling it in would slow the smoke test for no signal.

The new `api` service:

- `build: { context: ., dockerfile: Dockerfile, target: runner }` — the
  actual image `release.yml` builds and ships, not `develop`.
- `env_file:` the same three per-service files
  `.devcontainer/compose.yml` uses (`./.devcontainer/stack/postgres/postgres.env`,
  `./.devcontainer/stack/s3/s3.env`, `./.devcontainer/stack/keycloak/keycloak.env`)
  — never re-pin those values a second time (CLAUDE.md's "Configuration"
  section).
- `environment:` the same fixed in-network hostnames/ports
  `.devcontainer/compose.yml` sets literally (`POSTGRES_HOST: postgres`,
  `POSTGRES_PORT: "5432"`, `S3_ENDPOINT_URL: http://s3:9000`,
  `REDIS_URL: redis://redis:6379/0`). No `MODE` override: the runner
  stage's own `ENV MODE=production` default (Dockerfile) is exactly what
  this smoke test wants to exercise — real dependencies, not
  `MODE=mock`'s in-memory fakes.
- `depends_on:` `postgres`, `s3`, `redis`, `keycloak`, each
  `condition: service_healthy` — same pattern as
  `.devcontainer/compose.yml`, minus `selenium`.
- Its own `healthcheck:`, polling `/health/ready` from inside the
  container so `docker compose up --wait` (see workflow below) can gate on
  it the same way it gates on every stack service. The runner image has
  neither `curl` nor `wget` (slim base, nothing installed beyond the venv
  — see `scripts/runner-setup.sh`), so the check shells out to the venv's
  own Python instead:
  `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=3)"`
  — a non-2xx (503 while a dependency is still down) raises
  `HTTPError`, which is a nonzero exit, which is exactly what a
  healthcheck needs. Give it a `start_period` long enough to cover
  Alembic migrations + Keycloak/JVM startup (Keycloak's own healthcheck
  already budgets ~2 minutes worst case — see `stack/keycloak/compose.yml`).
- `ports: ["8000:8000"]` — the one deliberate deviation from
  `.devcontainer/stack/README.md`'s "no `ports:`" rule, which applies to
  fragments under `.devcontainer/` reached only from sibling containers.
  This file lives outside `.devcontainer/` and its whole purpose is to be
  curled from the GitHub Actions runner (host), so it needs a published
  port. Say so in a comment next to the `ports:` entry so it doesn't read
  as a copy-paste mistake.

No top-level `volumes:` needed beyond what each included fragment already
declares for itself (`postgres-data`, `s3-data`, `redis-data`) — same as
`.devcontainer/compose.yml`.

Give the file the usual one-line header comment (CLAUDE.md's "File
headers") explaining it's the runner-image smoke-test stack, distinct
from `.devcontainer/compose.yml`.

### GitHub Actions workflow

New `.github/workflows/smoke.yml`, triggers matching `checks.yml`
(`push: branches: [main]`, `pull_request`, `workflow_dispatch`),
`permissions: contents: read`, `runs-on: ${{ vars.CI_RUNNER || 'ubuntu-latest' }}`.
Unlike `checks.yml`, this doesn't need `devcontainers/ci` — there's no
devcontainer involved, just plain `docker compose` against the new root
file:

1. Check out the repo.
2. Set a unique `COMPOSE_PROJECT_NAME` (same reasoning as `checks.yml`:
   concurrent runs must not collide on container/volume/network names) —
   e.g. `smoke-${{ github.run_id }}-${{ github.run_attempt }}`.
3. `docker compose -f compose.yml up -d --build --wait --wait-timeout 300`
   — builds the `runner` image, starts the whole stack, and blocks until
   every service (including `api`'s own healthcheck) reports healthy or
   the timeout is hit.
4. Explicit liveness/readiness confirmation, printed to the log rather
   than left implicit in step 3's `--wait` gate:
   ```bash
   curl -fsS http://localhost:8000/health/live
   curl -fsS http://localhost:8000/health/ready
   ```
5. `if: failure()` — dump `docker compose -f compose.yml logs` for
   diagnosis before teardown.
6. `if: always()` — tear down:
   `docker compose -f compose.yml -p $COMPOSE_PROJECT_NAME down --volumes --remove-orphans`
   (mirrors `checks.yml`'s teardown step).

Keep the curl/log/teardown commands inline in the workflow YAML (each is
a couple of lines) rather than a new `.github/scripts/` file — that
directory's own README reserves itself for logic longer than a few
lines.

### Documentation updates

- Root `README.md`'s "Contents" list: add a line for the new `compose.yml`
  (distinct from `.devcontainer/compose.yml`, which already has its own
  entry).
- `.github/workflows/README.md`: add a bullet for `smoke.yml` alongside
  the existing `checks.yml`/`release.yml` bullets.

## Open questions

- `--wait-timeout 300` for step 3 is a guess based on Keycloak's own
  healthcheck budget (~2 minutes worst case) plus migration time; adjust
  once a real CI run shows the actual startup time.
