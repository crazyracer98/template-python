# Bring test coverage to 100%

## Status

Done

## Goal

Both coverage gates (`tests/unit` + `tests/integration` in one process,
`tests/e2e` in its live-subprocess run — see `tests/README.md`) currently
enforce `fail_under = 95` (`pyproject.toml`'s `[tool.coverage.report]`).
A local run of the first gate already measures 99.91% with exactly one
partial branch outstanding; the e2e gate's current number is unknown
from outside the devcontainer (needs the full stack — Postgres, Redis,
RustFS, Keycloak, Selenium — up). This plan closes both to a genuine
100% and raises the enforced floor to match, so any future regression
below full coverage fails CI immediately instead of hiding under the
95% cushion.

## Approach

1. **Close the known unit/integration gap.** `uv run pytest tests/unit
   tests/integration` currently reports 99.91%, with the only miss
   being a partial branch at
   [src/app/repositories/sqlalchemy.py:59](../../src/app/repositories/sqlalchemy.py#L59)
   (`59->38`): the `for` loop's continue-edge after a `FilterOp.REGEX`
   case is never exercised because
   [tests/integration/repositories/test_sqlalchemy.py](../../tests/integration/repositories/test_sqlalchemy.py)'s
   `test_every_filter_op_against_real_postgres` only ever puts `REGEX`
   as the last (or only) clause in a filter list. Add a case there with
   `REGEX` followed by another `FilterClause` in the same list (e.g.
   `[FilterClause("name", FilterOp.REGEX, ...), FilterClause("id",
   FilterOp.IN, ids)]`) so the loop actually continues past it. Rerun
   the suite and confirm `TOTAL` reads 100%.

2. **Get an e2e coverage baseline.** This plan was drafted outside the
   devcontainer, where `docker ps` shows no stack containers running, so
   `uv run pytest tests/e2e` couldn't be run to see its current
   `Missing` column. Inside the devcontainer (or CI, which uses
   `devcontainers/ci`), run `uv run pytest tests/e2e` and capture the
   coverage report's missing lines/branches for `src/app`.

3. **Triage each e2e gap individually.** This codebase already
   distinguishes, per module docstring, which branches are structurally
   unreachable through a real HTTP request in that suite (see the
   existing `# pragma: no cover` justifications in
   [src/app/main.py](../../src/app/main.py) around its `mode ==
   "mock"` branch,
   [src/app/oidc.py](../../src/app/oidc.py) around its mock-mode
   branch,
   [src/app/telemetry.py](../../src/app/telemetry.py)'s OTEL config
   branch, [src/app/problem_details.py](../../src/app/problem_details.py)'s
   unhandled-exception handler, and
   [src/app/health/checks.py](../../src/app/health/checks.py)'s
   failure branches). For each line/branch tests/e2e still misses:
   - If it's reachable through a real HTTP request a client could make,
     add or extend a test for it — prefer extending the existing
     per-role journey test (`tests/e2e/viewer/`, `editor/`,
     `maintainer/`, `security/`, `detective/`) or format-regression file
     (`test_health_e2e.py`, `test_heroes_e2e.py`,
     `test_heroes_xml_e2e.py`, `test_heroes_web_e2e.py`,
     `test_protected_e2e.py`) that already owns that route, rather than
     adding a new file.
   - If it's genuinely unreachable from a live HTTP client in this
     suite (mirrors the mock-mode/OTEL/protocol-stub patterns above),
     mark it `# pragma: no cover` with a comment or docstring addition
     explaining why, following the existing convention exactly (a short
     module-docstring note plus an inline `# pragma: no cover -- see
     module docstring` where more than one line is affected).
   - Don't add a pragma to paper over a gap that a real test could
     reasonably close — the point of this pass is fewer untested
     branches, not fewer visibly-untested ones.

4. **Raise the floor.** Once both suites independently report 100%,
   change `fail_under = 95` to `fail_under = 100` in `pyproject.toml`'s
   `[tool.coverage.report]`, and update the "enforce 95% coverage" line
   in `tests/README.md` to 100%, so both gates hold the line going
   forward.

5. **Re-verify.** Run `uv run pytest tests/unit tests/integration` and
   `uv run pytest tests/e2e` once more against the new threshold to
   confirm both pass clean, then run `mypy src tests` (tests carry full
   annotations per `tests/README.md`) since new/changed test code must
   still type-check.

## Open questions

- What tests/e2e's current coverage gaps actually are — unknown until
  step 2 runs inside an environment with the full stack up. Steps 3-5
  can't be scoped precisely until then; this plan may need a follow-up
  pass once that list exists.
