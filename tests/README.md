# tests/

Pytest tests, split into three independent suites:

- `unit/` — no external services; mirrors `src/app/`'s structure.
- `integration/` — reaches the real stack containers (already
  running under the devcontainer, and under CI via `devcontainers/ci`) —
  no mocks.
- `e2e/` — Playwright tests against the live `api` service, driving a
  browser in the `selenium` stack container remotely; see its own
  `README.md`.

A plain `pytest` run collects `unit/` and `integration/` (both work
inside the devcontainer / CI as-is) and ignores `e2e/` (see
`pyproject.toml`'s `addopts`).

Both that run and `uv run pytest tests/e2e` independently enforce 95%
coverage of `src/app` (see `[tool.coverage.report]` in `pyproject.toml`)
— e2e's coverage comes from the live `api` subprocess, not from the test
process itself; see `e2e/README.md`.

## Do

- Name a test file after the module or integration point it covers
  (`src/app/config.py` → `tests/unit/test_config.py`) so coverage is easy
  to eyeball.
- Let `assert` and bare literal comparisons stand — `S101` and `PLR2004`
  are disabled for all three suites precisely so tests can look like
  tests.

## Don't

- Depend on test execution order, or leave state (files, env vars) for a
  later test to pick up.
- Import across suites (`unit/` ↔ `integration/` ↔ `e2e/`) — each stays
  independently runnable.
