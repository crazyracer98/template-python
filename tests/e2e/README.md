# tests/e2e/

Playwright end-to-end tests — the third of `tests/`'s three suites (see
`../README.md`), run from the devcontainer itself against the live `api`
service, with Playwright driving Chromium remotely in the `selenium`
stack container over CDP (see
`.devcontainer/stack/selenium/README.md` and this directory's
`conftest.py`) — not collected by a plain `pytest` run (see
`pyproject.toml`'s pytest `addopts`, which ignores this directory by
default; run it explicitly with `uv run pytest tests/e2e`).

The session-scoped, autouse `_running_app` fixture in `conftest.py` starts
`uvicorn` for the duration of the run and tears it down afterwards, so
this suite doesn't require the app already running in another terminal —
unless something already answers `{base_url}/health` (e.g. the "FastAPI:
api" launch config), in which case it's left alone, or `E2E_BASE_URL` is
set, in which case this suite assumes whatever it points at is managed
elsewhere.

That `uvicorn` process is a subprocess, so pytest-cov can't measure it
directly the way it measures `../unit/` and `../integration/` importing
`app` in-process. `conftest.py` instead points it at `sitecustomize.py`
(via `PYTHONPATH`) and sets `COVERAGE_PROCESS_START`, so `coverage.py`
starts measuring inside that subprocess on launch and saves on shutdown
(`[tool.coverage.run]`'s `sigterm = true`, in `pyproject.toml`, is what
makes that save actually happen — see the comment there for why);
pytest-cov then combines its data with this process's own at session end
to produce one coverage report against the same 95% floor as `../unit/`
+ `../integration/` (see `../README.md`). A route this suite never
exercises through a real HTTP request stays uncovered here even if
`../unit/`/`../integration/` cover it directly.

Besides the format-regression files at this level (`test_health_e2e.py`,
`test_heroes_e2e.py`/`test_heroes_xml_e2e.py`/`test_heroes_web_e2e.py`,
`test_protected_e2e.py`), one subdirectory per Keycloak client role —
`viewer/`, `editor/`, `maintainer/`, `security/`, `detective/` (see
`.devcontainer/stack/keycloak/realm-export.json`) — holds a single journey
test walking through what that role can and can't do end-to-end, using the
shared `access_token` fixture (`conftest.py`) to log in as it.

## Do

- Run these from the devcontainer's own terminal, same as `../unit/` and
  `../integration/`:

  ```bash
  uv run pytest tests/e2e
  ```

- Use the `base_url` fixture (from `conftest.py`) rather than
  hardcoding `http://api:8000`.
- Use the `access_token` fixture (from `conftest.py`) to log in as a
  dev-realm user rather than adding another local
  `_fetch_access_token()`-style helper.
- Reach the real `api` service — that's the point of this directory,
  unlike `../unit/`.

## Don't

- Import from `../unit/` or `../integration/`, or vice versa — keep all
  three suites independent so one can run without another's container.
- Add e2e-only dependencies anywhere but the `dev` optional-dependency
  group in `pyproject.toml`.
