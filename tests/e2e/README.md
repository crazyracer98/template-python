# tests/e2e/

Playwright end-to-end tests — the third of `tests/`'s three suites (see
`../README.md`), run inside the `playwright` infra-stack container
against the live `api` service — not collected by a plain `pytest` run
in the `api` container (see `pyproject.toml`'s pytest `addopts`, which
ignores this directory by default).

## Do

- Run these from your **host machine's** terminal, per
  `.devcontainer/infra-stack/playwright/README.md` — not from the
  devcontainer's integrated terminal, which can't reach the `playwright`
  container (see that README's "Don't" for why).
- Use the `base_url` fixture (from `conftest.py`) rather than
  hardcoding `http://api:8000`.
- Reach the real `api` service — that's the point of this directory,
  unlike `../unit/`.

## Don't

- Import from `../unit/` or `../integration/`, or vice versa — keep all
  three suites independent so one can run without another's container.
- Add e2e-only dependencies anywhere but the `e2e` optional-dependency
  group in `pyproject.toml`.
