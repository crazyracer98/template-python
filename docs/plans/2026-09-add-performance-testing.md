# Add performance testing

## Status

Draft

## Goal

This repo has unit/integration/e2e coverage (`tests/README.md`) but no
signal on latency or throughput under load — `NFR-0016` even calls out
`NullPool`'s connection-reuse trade-off as verified only "by code review
... no automated performance check exists today." Add a fourth,
independent test suite (`tests/perf/`) that drives the real `runner`
image against its full backing-service stack and fails when response
time/error-rate thresholds are breached, plus the NFR/ADR/CI wiring to
make that check meaningful and repeatable rather than a one-off script.

## Approach

1. **Pick and add the load-generation tool.** Use
   [Locust](https://locust.io/): pure Python (fits `pyproject.toml`'s
   existing `uv`-managed, single `dev`-group convention — no new
   language runtime the way k6 would need), scriptable per-endpoint
   weighted task sets, and a headless mode
   (`--headless --csv=... --exit-code-on-error`) that CI can gate on.
   Add `locust==<pinned>` to the `dev` optional-dependency group in
   `pyproject.toml` via `uv add --optional dev locust`, not by hand —
   see the root `README.md`'s "Versions and config".
2. **Record the decision as an ADR.** `docs/adrs/0010-locust-for-load-
   testing.md` (next sequential number — confirm against
   `docs/adrs/` at execution time): context (no perf signal today,
   `NullPool` trade-off unverified), decision (Locust, headless, against
   the `runner` image + real stack, not `MODE=mock`), consequences
   (a new CI job's runtime cost; Python-only so it stays in the same
   toolchain; load only exercises what's scripted, so it doesn't replace
   the NFR's own code-review gate for unscripted paths).
3. **Add `tests/perf/`, a fourth independent suite,** alongside
   `unit/`/`integration/`/`e2e/`:
   - `tests/perf/README.md` documenting the suite the same way
     `tests/e2e/README.md` does: what it hits, how to run it locally,
     why it's separate from the other three (real infra, not
     `TestClient`; not driven by `pytest` at all — Locust has its own
     runner, so it's *not* collected by a plain `pytest` run or added to
     `--cov`; see `tests/README.md`'s "Do"/"Don't" and update that file
     to mention the fourth suite).
   - `tests/perf/locustfile.py` (plus per-resource task files if it
     grows) scripting the existing worked example
     (`/crud/v1/heroes/v2/json` list/create/get/update/delete, weighted
     toward reads) and `/health/live`, using a login task against
     `POST /mock/token` or a real Keycloak grant for authenticated
     routes — reuse `tests/e2e/conftest.py`'s `access_token` pattern
     rather than re-deriving token logic.
   - Targets the `runner`-stage image over the real stack (`compose.yml`,
     the same one `smoke.yml` builds), not the devcontainer's `dev`
     `uvicorn --reload` process — profiling a reload-enabled, debugpy-
     attached process would misrepresent production latency.
4. **Define the NFR the suite verifies against.**
   `docs/nfrs/NFR-0024-api-latency-and-throughput-targets.md`: measurable
   targets (e.g. p95 latency and error-rate ceilings per endpoint class —
   set initial numbers from a baseline run rather than guessing) and
   "Verification" pointing at `tests/perf/` plus the new CI job. Link it
   from `NFR-0016` (no connection pooling) since a pool-related
   regression is exactly what this suite would catch.
5. **Add a CI workflow**, `.github/workflows/perf.yml`, following
   `smoke.yml`'s pattern (unique `COMPOSE_PROJECT_NAME`, build+`--wait`
   the `runner` stack, dump logs and tear down on failure) but:
   - Triggered by `workflow_dispatch` only (plus optionally a weekly
     `schedule`) — **not** on every push/PR like `checks.yml`/`smoke.yml`,
     since a load test's runtime and shared-runner noise make it a poor
     fit for the per-PR gate; document that choice in the ADR from step 2.
   - Runs `uv run locust -f tests/perf/locustfile.py --headless
     --host http://localhost:8000 --exit-code-on-error ...` after the
     stack is healthy, failing the job on threshold breach.
   - Uploads Locust's CSV/HTML report as a build artifact so a run's
     numbers are inspectable after the fact.
6. **Update surrounding docs** touched by adding a fourth suite: root
   `README.md`'s `tests/` bullet ("split into `unit/`, `integration/`,
   `e2e/` (Playwright), and `perf/` (Locust)"), `tests/README.md`'s
   suite list and coverage-gate wording (perf isn't part of the 100%
   coverage gate — say so explicitly, same as e2e already does), and
   `.github/workflows/README.md`'s workflow list.

## Open questions

- Concrete latency/throughput numbers for `NFR-0024` — needs a baseline
  run against the real stack before picking thresholds; don't invent
  numbers, measure first and record what was measured.
- Whether `perf.yml` should also run automatically on a release tag
  (alongside `release.yml`) once thresholds are trustworthy, or stay
  manual-only indefinitely.
