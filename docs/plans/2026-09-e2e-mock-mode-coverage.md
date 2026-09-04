# Run the e2e suite against MODE=mock as well as MODE=dev

## Status

Draft

## Goal

`tests/e2e` today only ever drives one live `MODE=dev` process against
real Postgres/Redis/S3/Keycloak — `MODE=mock`
([src/app/README.md](../../src/app/README.md)'s "MODE (dev / mock /
production)" section, [ADR-0006](../adrs/0006-mode-driven-fakes-for-infrastructure-free-testing.md),
[NFR-0022](../nfrs/NFR-0022-mock-mode-zero-infrastructure.md)) is fully
implemented but has no coverage beyond `tests/unit/controllers/test_mock.py`
calling its router in-process. Parametrize the e2e suite so it also runs
against a zero-infrastructure `MODE=mock` app, closing that gap and
exercising `POST /mock/token`/`InMemoryRepository`/`MockHealthCheck`
through real HTTP the way the rest of `tests/e2e` exercises everything
else.

## Approach

1. **Parametrize the app-under-test by mode** —
   [tests/e2e/conftest.py](../../tests/e2e/conftest.py). Replace the
   fixed `base_url`/`_running_app` pair with a session-scoped,
   `params=["dev", "mock"]` fixture (e.g. `app_mode`) and make
   `base_url`/`_running_app` depend on it: each mode gets its own port
   (dev keeps `:8000`; mock gets its own, e.g. `:8001`) and its own
   `uvicorn` subprocess launched with `env={**os.environ, "MODE": mode,
   **({"ALLOW_MOCK_MODE": "1"} if mode == "mock" else {})}`. Keep the
   existing "skip spawning if something already answers `/health/live`"
   and `E2E_BASE_URL` escape hatches, but scope `E2E_BASE_URL` to the
   `dev` param only — mock's whole point is not depending on an
   externally-managed instance. `browser` stays a single session-scoped
   fixture, unaffected by the mode parametrization.

2. **Make `access_token` mode-aware** —
   [tests/e2e/conftest.py](../../tests/e2e/conftest.py). Under `dev`,
   keep the current real password-grant POST to
   `settings.oidc_token_url`. Under `mock`, POST `{base_url}/mock/token`
   with `{"sub": username, "roles": [...]}` instead. The role(s) per
   username must match `.devcontainer/stack/keycloak/realm-export.json`'s
   existing per-user client-role assignments (`viewer`/`editor`/
   `maintainer`/`security`/`detective`, one role per matching username)
   so every test can keep calling `access_token("editor")` unchanged
   regardless of mode — read the mapping out of `realm-export.json` at
   fixture-build time rather than hand-duplicating it, so the two stay
   in sync automatically.

3. **Make mode-sensitive assertions branch on it** —
   [tests/e2e/test_health_e2e.py](../../tests/e2e/test_health_e2e.py) is
   the one file that currently asserts on real per-service health check
   output; under `MODE=mock` that becomes `MockHealthCheck`'s output
   instead (see `src/app/health/checks.py`). Give it an `app_mode`-
   conditional assertion (exact healthy/degraded shape per mode) rather
   than skipping the mock parametrization for that file.

4. **Let the rest of the suite run unchanged under both modes** — the
   format-regression files (`test_heroes_e2e.py`,
   `test_heroes_xml_e2e.py`, `test_heroes_web_e2e.py`, and their `v1`
   siblings), `test_protected_e2e.py`, and the five role-journey files
   under `viewer/`, `editor/`, `maintainer/`, `security/`, `detective/`
   only touch `base_url`/`access_token`, so they pick up both
   parametrizations for free once step 1/2 land — no per-file changes
   expected. Run the full suite once during implementation to confirm
   nothing in them assumes a real Postgres/Keycloak side effect (e.g. an
   ID that must survive across the two mode runs, which it won't under
   `InMemoryRepository`'s fresh-per-process state).

5. **Drop the now-stale "e2e never reaches this" assumptions** —
   [src/app/controllers/mock.py](../../src/app/controllers/mock.py):
   remove the `# pragma: no cover` on `issue_mock_token` and rewrite the
   module docstring's second paragraph (it currently states e2e drives
   only one live `MODE=dev` process that never mounts this router).
   [src/app/README.md](../../src/app/README.md)'s MODE section: update
   "Nothing in this repo sets it today (no compose file/CI job runs
   `MODE=mock`)" now that `tests/e2e/conftest.py` does.
   [docs/nfrs/NFR-0022-mock-mode-zero-infrastructure.md](../nfrs/NFR-0022-mock-mode-zero-infrastructure.md)'s
   "Verification" section: add that `tests/e2e` now also runs one leg
   fully under `MODE=mock` with no Postgres/Redis/S3/Keycloak
   dependency, as a stronger end-to-end verification than the unit
   suite's in-process one.

6. **Update `tests/e2e/README.md`** —
   [tests/e2e/README.md](../../tests/e2e/README.md) currently describes
   a single `uvicorn` process reaching "the live `api` service"; document
   the two-process, two-mode parametrization, and that the mock leg
   needs no `.devcontainer/stack` containers running at all (call this
   out since it changes what "run these from the devcontainer's own
   terminal" requires in practice — mock's app process still needs the
   devcontainer's Python/uv environment, just not the sibling service
   containers).

Run `uv run pytest tests/e2e` after steps 1–4 and confirm both parametrized
legs (`dev`/`mock`) pass and are visibly reported as separate test IDs;
run `ruff` and `mypy --strict` after every step per `CLAUDE.md`'s
verification requirement; run the unit suite too since step 5 touches
`src/app/controllers/mock.py`'s coverage-gate comment (confirm
`tests/unit/controllers/test_mock.py` plus the new e2e coverage together
still clear the 95% floor described in
[tests/README.md](../../tests/README.md)).

## Open questions

- **Two full `uvicorn` processes per e2e run roughly doubles wall-clock
  time** (dev's real Postgres/Keycloak round trips plus a second full
  suite pass under mock). Acceptable given `pytest-e2e` is already
  `pre-push`/`manual`-staged, not on every commit — but worth confirming
  with whoever owns CI runtime budget before landing.
- **Port for the mock leg**: hardcode `:8001` (simple, matches the
  existing hardcoded `:8000` default) or ask the OS for a free port
  dynamically? Hardcoding is simpler and consistent with `base_url`'s
  current style; only revisit if running e2e twice in parallel ever
  becomes a real use case.
