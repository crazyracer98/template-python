# template-python

A template repository for FastAPI projects, built around a devcontainer
setup composed from independent, swappable pieces.

## Contents

- `.devcontainer/` — the devcontainer setup; see its `README.md`.
- `.github/` — CI and release workflows; see its `CONTENTS.md`.
- `.vscode/` — editor settings, tasks, launch config; see its `README.md`.
- `.claude/` — Claude Code CLI project config; see its `README.md`.
- `.mcp.json` — project-scope MCP servers not covered by a
  `.claude/settings.json` plugin; see `.claude/README.md`.
- `src/` — the application source; see its `README.md`.
- `tests/` — automated tests, split into `unit/`, `integration/`, and
  `e2e/` (Playwright) suites; see its `README.md`.
- `scripts/` — the Dockerfile's per-stage setup scripts; see its
  `README.md`.
- `docs/` — knowledge about what the app does.
- `.secrets/` — local secret files, never committed; see its `README.md`.
- `Dockerfile` — three build stages: `develop`, `builder`, `runner`.
- `pyproject.toml` / `uv.lock` — dependencies, managed with `uv`, pinned
  to exact patch versions.
- `.pre-commit-config.yaml` — git hooks, run by `prek` or `pre-commit`.
- `CLAUDE.md` — conventions for working in this repository.

## Getting started

1. Open this folder in a devcontainer (VS Code: "Reopen in Container" —
   `.vscode/extensions.json` recommends the extension that offers this —
   or any tool that reads `.devcontainer/devcontainer.json`). This starts
   the app alongside Postgres, RustFS (S3), Redis, Keycloak (OIDC), and a
   Selenium container Playwright drives remotely for e2e tests; installs
   dependencies; and installs the git hooks, all via `postCreateCommand`.
2. Run the app: `uvicorn app.main:app --reload --host 0.0.0.0`, or use
   the "FastAPI: api" launch config to run it under the debugger.
3. Health check: `curl localhost:8000/health`. `/protected` needs a
   bearer token from Keycloak — see
   `.devcontainer/stack/keycloak/README.md`.

Without a devcontainer: install [`uv`](https://docs.astral.sh/uv/), export
your own `DATABASE_URL` / `S3_ENDPOINT_URL` / `S3_ACCESS_KEY` /
`S3_SECRET_KEY` / `REDIS_URL` / `OIDC_ISSUER_URL` / `OIDC_AUTHORIZATION_URL` /
`OIDC_TOKEN_URL` / `OIDC_CLIENT_ID` (see `src/app/config.py` for the
defaults), then
`uv sync --extra dev` and run uvicorn the same way. Run
`uv run prek install` once to enable the git hooks.

## Checks

`ruff` (lint + format), `mypy --strict`, and `pytest` are all configured
to fail on any violation — see `pyproject.toml`. `pytest` also fails
below 95% coverage of `src/app`, for both the default run
(`tests/unit` + `tests/integration`) and `uv run pytest tests/e2e`. Run
everything at once with:

```bash
uv run prek run --all-files --hook-stage manual
```

Commit messages are checked separately, against
[Conventional Commits](https://www.conventionalcommits.org/), at commit
time — see `CLAUDE.md`'s "Conventional commits" section.

CI (`.github/workflows/checks.yml`) runs the same `--hook-stage manual`
command, inside the devcontainer itself, on every push and pull request.
`.github/workflows/release.yml` is triggered manually to cut an
alpha/beta/rc/full release with an auto-generated changelog and the
built image attached (and optionally pushed to an OCI registry) — see
`.github/workflows/README.md`.

## Do

- Read `CLAUDE.md` and the `README.md` of every directory on the path to
  whatever you're changing before you change it.
- Open this repo in the devcontainer rather than assembling the
  toolchain by hand — it's the one environment this template guarantees.

## Don't

- Add a dependency, base image, Action, or hook revision without pinning
  it to an exact patch version.
- Commit a `.env` file, or read one from application code — configuration
  lives in the compose files; secrets live in `.secrets/`.
- Add a `ports:` mapping or a `networks:` block to any file under
  `.devcontainer/` — see `CLAUDE.md`'s "Devcontainer stack pattern"
  section for how host access and inter-service networking are handled
  instead.
