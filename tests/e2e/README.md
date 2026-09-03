# tests/e2e/

Playwright end-to-end tests — the third of `tests/`'s three suites (see
`../README.md`), run from the devcontainer itself against the live `api`
service, with Playwright driving Chromium remotely in the `selenium`
infra-stack container over CDP (see
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

## Do

- Run these from the devcontainer's own terminal, same as `../unit/` and
  `../integration/`:

  ```bash
  uv run pytest tests/e2e
  ```

- Use the `base_url` fixture (from `conftest.py`) rather than
  hardcoding `http://api:8000`.
- Reach the real `api` service — that's the point of this directory,
  unlike `../unit/`.

## Don't

- Import from `../unit/` or `../integration/`, or vice versa — keep all
  three suites independent so one can run without another's container.
- Add e2e-only dependencies anywhere but the `dev` optional-dependency
  group in `pyproject.toml`.
