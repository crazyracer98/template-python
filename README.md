# template-fastapi

> [!NOTE]
> This repository is vibe coded with [Claude](https://claude.com/product/claude-code).

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
- `alembic/` / `alembic.ini` — database migrations; see
  `alembic/README.md`.
- `tests/` — automated tests, split into `unit/`, `integration/`, and
  `e2e/` (Playwright) suites; see its `README.md`.
- `scripts/` — the Dockerfile's per-stage setup scripts; see its
  `README.md`.
- `docs/` — knowledge about what the app does.
- `.secrets/` — local secret files, never committed; see its `README.md`.
- `Dockerfile` — three build stages: `develop`, `builder`, `runner`.
- `compose.yml` — runner-image smoke-test stack (distinct from
  `.devcontainer/compose.yml`); see `.github/workflows/README.md`'s
  `smoke.yml` entry.
- `pyproject.toml` / `uv.lock` — dependencies, managed with `uv`, pinned
  to exact patch versions.
- `.pre-commit-config.yaml` — git hooks, run by `prek` or `pre-commit`.
- `CLAUDE.md` — the AI-assisted coding workflow Claude Code follows in
  this repository; general conventions live in this file and each
  directory's own `README.md` instead.

## Getting started

1. Open this folder in a devcontainer (VS Code: "Reopen in Container" —
   `.vscode/extensions.json` recommends the extension that offers this —
   or any tool that reads `.devcontainer/devcontainer.json`). This starts
   the app alongside Postgres, RustFS (S3), Redis, Keycloak (OIDC), and a
   Selenium container Playwright drives remotely for e2e tests; installs
   dependencies; and installs the git hooks, all via `postCreateCommand`.
2. Run the app: `uvicorn app.main:app --reload --host 0.0.0.0`, or use
   the "FastAPI: api" launch config to run it under the debugger. Startup
   applies any pending Alembic migrations automatically — see
   `src/app/README.md`'s "Alembic migrations".
3. Health check: `curl localhost:8000/health/live` (liveness) or
   `curl localhost:8000/health/ready` (readiness — checks Postgres,
   Redis, S3, and the OIDC provider). `curl localhost:8000/crud/v1/heroes/v2/json`
   is a worked example CRUD resource (see `src/app/README.md`'s "Example
   CRUD resource: Hero"). `/protected` needs a bearer token from Keycloak —
   see `.devcontainer/stack/keycloak/README.md`.

Without a devcontainer: install [`uv`](https://docs.astral.sh/uv/), export
your own `DATABASE_URL` / `S3_ENDPOINT_URL` / `S3_ACCESS_KEY` /
`S3_SECRET_KEY` / `REDIS_URL` / `OIDC_ISSUER_URL` / `OIDC_AUTHORIZATION_URL` /
`OIDC_TOKEN_URL` / `OIDC_CLIENT_ID` (see `src/app/config.py` for the
defaults), then
`uv sync --extra dev` and run uvicorn the same way. Run
`uv run prek install` once to enable the git hooks.

## Checks

`ruff` (lint + format), `mypy --strict`, `pytest`, and `pip-audit`
(dependency vulnerabilities, run against exactly what `uv.lock` resolves)
are all configured to fail on any violation — see `pyproject.toml`.
`pytest` also fails below 100% coverage of `src/app`, for both the
default run (`tests/unit` + `tests/integration`) and `uv run pytest
tests/e2e`. `.github/dependabot.yml` opens a weekly update PR for Python
dependencies, GitHub Actions, and the Dockerfile's base images. Run
everything at once with:

```bash
uv run prek run --all-files --hook-stage manual
```

If a rule produces a false positive, silence that one line with a
justified `# noqa: <code>` rather than loosening the project-wide
configuration. Every function (including tests, `__init__`, and dunder
methods) gets a one-line docstring stating what it does — ruff's
`D100`–`D107` enforce this; see "Code style" below for what the
docstring should actually say.

Hooks are defined once in `.pre-commit-config.yaml` and run by
[`prek`](https://prek.j178.dev/) (a faster, drop-in-compatible
reimplementation of `pre-commit`, already a `dev` dependency — the
classic `pre-commit` CLI reads the same config file if you prefer it).
Fast, basic checks run on commit; slower, extensive checks (mypy,
pytest, `uv lock --check`) run on push. Every hook except the
commit-message check also carries the `manual` stage, so the command
above runs everything else at once. `.vscode/settings.json`'s
`git.commandsToLog` surfaces a failing hook's output in VS Code's Git
output channel immediately, instead of only on request.

Commit messages are checked separately: every commit message must
follow [Conventional Commits](https://www.conventionalcommits.org/),
enforced by the `conventional-pre-commit` git hook at the `commit-msg`
stage — an improperly formatted message is rejected before the commit
is created. This can't be run via the `manual` stage like the other
hooks (see the comment in `.pre-commit-config.yaml`); the only way to
check it is to actually commit.

CI (`.github/workflows/checks.yml`) runs the same `--hook-stage manual`
command, inside the devcontainer itself, on every push and pull request.
`.github/workflows/release.yml` is triggered manually to cut an
alpha/beta/rc/full release with an auto-generated changelog and the
built image attached (and optionally pushed to an OCI registry) — see
`.github/workflows/README.md`.

## Versions and config

Every version and config value is defined in exactly one place; nothing
duplicates or re-pins it elsewhere:

- Python/Debian base image versions: the `PYTHON_VERSION`/`DEBIAN_VERSION`
  `ARG` defaults at the top of the `Dockerfile`. `.devcontainer/compose.yml`
  does **not** pass matching `args:` — the Dockerfile's own defaults are
  authoritative because it's the file closer to where they're used. To
  change them, edit the `Dockerfile`, not the compose file.
- Python package versions: `pyproject.toml` / `uv.lock`. Dependencies are
  managed with `uv` — use `uv add <package>` / `uv sync` rather than
  editing the dependency lists by hand or invoking `pip` directly.
  All development-only tooling — linters, type checker, test runners,
  Playwright — lives in the single `dev` optional-dependencies group
  rather than split across several groups, since it's all
  development-related; if a future group needs another group's packages,
  reference it as a self-referential extra (e.g. `"template-fastapi[dev]"`,
  per PEP 621) instead of re-pinning the same package a second time.
- Everything else pinned (base images, Actions, hook revisions): pinned
  once, at its single point of use, to an exact patch version — never a
  floating range or `latest` — so Renovate/Dependabot can bump them one
  at a time and the diff shows exactly what changed. The one exception is
  the Dockerfile's `PYTHON_VERSION` `ARG`: it's pinned to minor only,
  because `mcr.microsoft.com/devcontainers/python` (the `develop` stage's
  base image) doesn't publish patch-granularity tags — there is no patch
  version to pin to. See the comment at that `ARG` in the `Dockerfile`.

`ruff`, `mypy`, and `pytest` all point their cache dirs at
`/home/vscode/.cache/<tool>` (set once each, in `pyproject.toml`'s
`[tool.ruff]`/`[tool.mypy]`/`[tool.pytest.ini_options]`) instead of the
project root. Same reasoning as not bind-mounting the venv (see
`.devcontainer/README.md`'s "Don't" section): a cache inside the
bind-mounted `/workspace` gets scanned file-by-file by host
antivirus/malware tools on Windows and is painfully slow to write to. A
new tool with its own on-disk cache follows the same pattern.

## Code style

Every file gets a brief header stating what the file *is for* — one
line, sometimes two: a leading comment for most formats, a module
docstring for Python (also required by ruff's `D100`). Never describe
the file's contents in the header; that's what reading the file is for.
Markdown files' own title/opening line already serves this purpose. A
format with no comment syntax (`.json`) documents itself via the
directory's `README.md` instead.

A comment earns its place by saying something the code/config next to
it can't: *why* it's written this way, a non-obvious consequence, or a
constraint that isn't visible locally. Don't add a comment that just
restates what the following line already says in code — if removing a
comment loses no information, remove it. Every existing comment in this
repository follows this rule; keep new ones held to the same bar.

## Do

- Read `CLAUDE.md` and the `README.md` of every directory on the path to
  whatever you're changing before you change it.
- Open this repo in the devcontainer rather than assembling the
  toolchain by hand — it's the one environment this template guarantees.

## Don't

- Commit a `.env` file, or read one from application code — configuration
  lives in the compose files; secrets live in `.secrets/`.
- Add a `ports:` mapping or a `networks:` block to any file under
  `.devcontainer/` — see `.devcontainer/stack/README.md`'s "Devcontainer
  stack pattern" section for how host access and inter-service
  networking are handled instead.
