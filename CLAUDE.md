# CLAUDE.md

Conventions for working in this repository.

## Before writing anything

Read every `README.md` on the path from the repo root down to the
directory you're about to change, in order (e.g. before touching
`src/app/`, read the root `README.md`, then `src/README.md`, then
`src/app/README.md`). A directory's rules build on its parents'; a change
that's fine at the root can still violate a rule set closer to the file.

The one exception is `.github/`: its directory doc is named
`CONTENTS.md`, not `README.md`. GitHub renders `.github/README.md` as
the repository's homepage in place of the root `README.md` if one
exists there, which would bury the actual project overview — naming it
`CONTENTS.md` keeps the per-directory doc without triggering that.

## Keeping this file current

When a prompt establishes a new method or convention for this repository
— not a one-off task, and not product/domain knowledge (that belongs in
`docs/`) — add it to this file so it keeps applying afterwards.

## AI-assisted coding workflow

Practices below are distilled from Anthropic's own Claude Code guidance
(https://code.claude.com/docs/en/best-practices), applied to this repo:

- **Explore, then plan, then implement.** For anything touching more
  than one file, or where the approach isn't obvious, read the
  relevant code and this file's directory-level `README.md`s (see
  "Before writing anything" above) and write a plan before editing.
  Skip planning for a change you could describe as a one-sentence diff.
- **Verify before calling it done.** A change isn't finished until
  something has produced a pass/fail signal against it — `ruff`,
  `mypy --strict`, `pytest`, or (for e2e work) the Playwright suite —
  and you've shown the actual output, not just asserted success.
  "Looks done" is not a verification step.
- **Address root causes.** Fix the underlying issue a failing check
  reports, not the check itself — don't silence a `ruff`/`mypy` error
  with a broad `# noqa`/`# type: ignore` just to make output green; see
  "Linting, typing, tests" below for the narrow, justified exception.
- **Scope investigations.** When exploring the codebase to answer a
  question, read only what's needed to answer it, and prefer a
  subagent for anything that would otherwise pull many files into the
  main context.
- **Course-correct early.** If the same correction has to be made
  twice on one approach, stop and reconsider the approach itself
  rather than trying a third variation.

`.claude/hooks/self-check.sh` automates the fast tier of this (see
"Claude Code" below) but doesn't replace running `mypy`/`pytest`/the
Playwright suite yourself before considering a change finished.

## Token efficiency

- **Read once, edit surgically.** Don't re-read a file already in
  context unless it changed since; prefer a targeted edit over a
  full-file rewrite.
- **No filler.** Skip restating the question and unsolicited closing
  summaries — state what changed and stop.
- **Clear, don't let it accumulate.** Between unrelated tasks, start a
  fresh session rather than carrying stale context forward; see
  "Compact instructions" below for what to keep when compacting instead.

## Single source of truth for versions and config

Every version and config value is defined in exactly one place; nothing
duplicates or re-pins it elsewhere:

- Python/Debian base image versions: the `PYTHON_VERSION`/`DEBIAN_VERSION`
  `ARG` defaults at the top of the `Dockerfile`. `.devcontainer/compose.yml`
  does **not** pass matching `args:` — the Dockerfile's own defaults are
  authoritative because it's the file closer to where they're used. To
  change them, edit the `Dockerfile`, not the compose file.
- Python package versions: `pyproject.toml` (see "Dependency management"
  below). All development-only tooling — linters, type checker, test
  runners, Playwright — lives in the single `dev` optional-dependencies
  group rather than split across several groups, since it's all
  development-related; if a future group needs another group's packages,
  reference it as a self-referential extra (e.g. `"template-python[dev]"`,
  per PEP 621) instead of re-pinning the same package a second time.
- Everything else pinned (base images, Actions, hook revisions): pinned
  once, at its single point of use.

## Dependency management

Python dependencies are managed with `uv` and `pyproject.toml` / `uv.lock`.
Use `uv add <package>` / `uv sync` rather than editing the dependency
lists by hand or invoking `pip` directly. Pin every dependency, base
image, Action, and hook revision to an exact patch version — never a
floating range or `latest` — so Renovate/Dependabot can bump them one at
a time and the diff shows exactly what changed.

The one exception is the Dockerfile's `PYTHON_VERSION` `ARG`: it's pinned
to minor only, because `mcr.microsoft.com/devcontainers/python` (the
`develop` stage's base image) doesn't publish patch-granularity tags —
there is no patch version to pin to. See the comment at that `ARG` in
the `Dockerfile`.

## File headers

Every file gets a brief header stating what the file *is for* — one
line, sometimes two: a leading comment for most formats, a module
docstring for Python (also required by ruff's `D100`; see "Linting,
typing, tests" below). Never describe the file's contents in the
header; that's what reading the file is for. Markdown files' own
title/opening line already serves this purpose. A format with no
comment syntax (`.json`) documents itself via the directory's
`README.md` instead.

## Comments

A comment earns its place by saying something the code/config next to
it can't: *why* it's written this way, a non-obvious consequence, or a
constraint that isn't visible locally (e.g. "resolves relative to a
different file — see CLAUDE.md's ..."). Don't add a comment that just
restates what the following line already says in code — if removing a
comment loses no information, remove it. Every existing comment in this
repository follows this rule; keep new ones held to the same bar.

## Devcontainer stack pattern

`.devcontainer/compose.yml` defines the app service and pulls every
supporting service in via its own `include:` list — not the
`dockerComposeFile` array in `devcontainer.json`, which only ever names
this one file. Supporting services (databases, object storage, caches,
an OIDC provider, an e2e test runner, ...) live under
`.devcontainer/stack/<name>/`, each with exactly two files: a
`compose.yml` fragment and a `README.md` describing it. A new service
follows this same pattern and gets added to `.devcontainer/compose.yml`'s
`include:` list.

Compose resolves each included fragment's own relative paths (bind
mounts, `env_file:`) against *that fragment's own directory*, not
`.devcontainer/` — so a fragment under `stack/<name>/` writes its paths
as plain `./file`, the same as if it were the only Compose file in play;
see `stack/keycloak/compose.yml`'s `env_file:`/bind-mount for an example.
Only `.devcontainer/compose.yml` itself, reaching into a fragment's
directory (its own `env_file:` list, `stack/postgres/postgres.env` and
friends), needs the `./stack/<name>/<file>` form, since those paths are
written in — and so resolve against — `.devcontainer/` itself.

No fragment (including the app service's own `compose.yml`) declares a
`ports:` mapping or a `networks:` block:

- **No `networks:`** — every service already reaches every other one by
  its service name on the default network Compose generates for this
  project; a named network here would only add a place for that to drift.
- **No `ports:`** — these are backend services meant to be reached only
  from other containers. If a service genuinely needs a host-browser-
  reachable port (Keycloak's login UI is the one example here), that
  port goes in `forwardPorts`/`portsAttributes` in `devcontainer.json`
  instead — the Dev Containers spec forwards a container's port directly
  from its network namespace, so this doesn't require publishing it via
  Compose at all. This keeps "what's reachable from the host" defined in
  exactly one place instead of scattered `ports:` blocks.

Every stack fragment's service also defines a `healthcheck:`, and
`.devcontainer/compose.yml`'s `api` service lists a matching `depends_on:
<service>: condition: service_healthy` entry for it. Compose won't start
`api` until every dependency reports healthy, so `docker compose up` (and
therefore `devcontainers/ci`'s `runCmd`, and a fresh `postCreateCommand`)
never runs a check or a test against a stack service that's still
starting — e.g. Keycloak, a JVM app doing `start-dev --import-realm`,
takes far longer to accept requests than Postgres/Redis/RustFS do. Pick
each healthcheck from what the image actually ships — verify with
`docker run`/`docker compose up` against the real pinned image rather
than assuming a tool (`curl`, `wget`) is present; `stack/keycloak/
compose.yml`'s healthcheck uses bash's `/dev/tcp` instead of `curl`
because the official Keycloak image ships neither `curl` nor `wget`.

## Dockerfile

The top-level `Dockerfile` has three stages — `develop`, `builder`,
`runner` — each with its own setup script under `scripts/`. Keep stage
layers minimal; put new stage-specific setup logic in that stage's
script, not inline in the Dockerfile.

## Cache directories

`ruff`, `mypy`, and `pytest` all point their cache dirs at
`/home/vscode/.cache/<tool>` (set once each, in `pyproject.toml`'s
`[tool.ruff]`/`[tool.mypy]`/`[tool.pytest.ini_options]`) instead of the
project root. Same reasoning as the Dockerfile's `.venv` placement: a
cache inside the bind-mounted `/workspace` gets scanned file-by-file by
host antivirus/malware tools on Windows and is painfully slow to write
to. A new tool with its own on-disk cache follows the same pattern.

## Configuration

No application `.env` file: `src/app/config.py` reads settings from the
process environment only, which the compose files populate (see below).
No real secrets exist in this template yet — when one is needed, it goes
in `.secrets/` and is referenced from a compose file, never hardcoded.

Every stack service's own local-dev-only default credentials
(Postgres, RustFS, Keycloak's admin/test users, ...) live in a
`<service>.env` file inside that service's own `stack/<service>/`
directory — the single source of truth for that service's values,
tracked in git since these are dev-only defaults, not real secrets (each
service's `README.md` says so). That fragment's own `compose.yml` loads
its file via `env_file:` directly into the service's container. Where
`api` needs those same values (`.devcontainer/compose.yml`), it lists the
same per-service files under its own `env_file:` — never re-pins the
values a second time — and `src/app/config.py` assembles any composed
connection string (`DATABASE_URL`) or renames a raw value to the app's
own generic field (`s3_access_key` from `RUSTFS_ACCESS_KEY`) at runtime.
Values that are already a full, opaque, provider-shaped string (the
`OIDC_*` URLs) are written that way directly in the owning service's env
file instead, so `src/app/config.py` never has to know a specific
provider's URL scheme. Fixed in-network hostnames/ports are not
credentials and stay as plain literals in the consuming compose file
(e.g. `api`'s `POSTGRES_HOST: postgres`), not in an env file.

## Docker-in-Docker vs. the host's Docker

The devcontainer has its own isolated Docker-in-Docker daemon (the
`docker-in-docker` feature in `devcontainer.json`). It is **not** the
same daemon running this project's own compose stack (`api`, `postgres`,
the rest of `stack/`) — that stack is started by whatever invoked
"Reopen in Container" against the *host's* Docker. So `docker`/`docker
compose` run from inside the devcontainer can build and run throwaway
containers of their own, but can never see or `exec` into this project's
sibling containers (e.g. `selenium`) — only a `docker compose` invoked
on the host can. See `.devcontainer/stack/selenium/README.md`
for the concrete case this affects.

## OIDC / Keycloak

`.devcontainer/stack/keycloak/` runs Keycloak with dev-mode realm
auto-import (`realm-export.json`: realm `template-python`, public client
`api`, test users `viewer`/`editor`/`security`/`maintainer`/`detective`,
each with a password matching its username). `src/app/oidc.py` validates
bearer tokens against it via generic OIDC discovery + JWKS
(`PyJWKClient`), with no Keycloak-specific code — any Authorization Code
+ PKCE provider works by pointing
`OIDC_ISSUER_URL`/`OIDC_AUTHORIZATION_URL`/`OIDC_TOKEN_URL` elsewhere. Add
auth to a route with `Depends(get_current_claims)`; routes
that don't take that dependency stay public. See `src/app/README.md` for
the route-level convention.

## Three test suites

`tests/` splits into `unit/` (no external services), `integration/`
(the real stack containers, no mocks — see
`tests/integration/README.md`), and `e2e/` (Playwright, against the
real `api` service). Unlike the other stack services, `e2e/`
doesn't exec into a sibling container from the host: Playwright runs as
a `dev`-group package inside the devcontainer itself and drives a
browser in the `selenium` stack container remotely, over CDP — see
`tests/e2e/conftest.py` and
`.devcontainer/stack/selenium/README.md`. The three suites never
import from one another. A plain `pytest` run collects `unit/` and
`integration/`; `e2e/` is ignored by default (see `pyproject.toml`) and
run explicitly with `uv run pytest tests/e2e`.

## VS Code

`.vscode/` (tasks, launch config, settings, extension recommendations)
and `devcontainer.json`'s `customizations.vscode` split responsibility:
anything that only makes sense *inside* the container (interpreter path,
extensions the app needs) lives in `devcontainer.json`; anything that
should also apply to the host-side window before you've reopened in the
container (like recommending the Dev Containers extension itself) lives
in `.vscode/`. See `.vscode/README.md`.

## Claude Code

`.claude/settings.json` enables the official `pyright-lsp` plugin so
Claude gets diagnostics and navigation from pyright directly instead of
grep-based exploration. It requires the `pyright-langserver` binary,
which `scripts/develop.sh` installs as an isolated `uv tool` — keep that
install and the plugin declaration in sync if either changes.

The same file wires up a `PostToolUse` hook (`.claude/hooks/self-check.sh`)
that runs the fast, pre-commit-stage hooks from `.pre-commit-config.yaml`
against a file right after Claude edits it, and a `PreToolUse` hook that
runs `snip hook` (installed by `scripts/develop.sh`, pinned via
`SNIP_VERSION`) to filter noisy Bash output — `pytest`, `ruff`, `mypy`,
`uv`, and more — down to its signal before it enters context. See
`.claude/README.md` for what each hook does and doesn't cover, and why
`snip` over the alternatives.

## Compact instructions

When compacting, preserve which files have been edited and their
current state, the most recent `ruff`/`mypy`/`pytest`/Playwright output
verbatim (pass or fail, with any error text), and unresolved plan/TODO
items. Summarize away exploratory reads that didn't lead to a change.

## Linting, typing, tests

`ruff` (lint + format), `mypy --strict`, and `pytest` are all configured
to fail hard: every selected rule/check is an error, not a warning (see
`pyproject.toml`). If a rule produces a false positive, silence that one
line with a justified `# noqa: <code>` rather than loosening the
project-wide configuration. Every function (including tests, `__init__`,
and dunder methods) gets a one-line docstring stating what it does —
ruff's `D100`–`D107` enforce this; the same "Comments" bar above applies
to what the docstring actually says.

## Conventional commits

Every commit message must follow
[Conventional Commits](https://www.conventionalcommits.org/), enforced by
the `conventional-pre-commit` git hook at the `commit-msg` stage — an
improperly formatted message is rejected before the commit is created.
This can't be run via the `manual` stage like the other hooks (see the
comment in `.pre-commit-config.yaml`); the only way to check it is to
actually commit.

## Git hooks

Hooks are defined once in `.pre-commit-config.yaml` and run by
[`prek`](https://prek.j178.dev/) (a faster, drop-in-compatible
reimplementation of `pre-commit`, already a `dev` dependency — the
classic `pre-commit` CLI reads the same config file if you prefer it).
Fast, basic checks run on commit; slower, extensive checks (mypy, pytest,
`uv lock --check`) run on push. Every hook except the commit-message
check also carries the `manual` stage, so
`uv run prek run --all-files --hook-stage manual` runs everything else at
once. CI (`.github/workflows/checks.yml`) runs that same command inside
the devcontainer itself (via `devcontainers/ci`), not a hand-rolled
CI-only equivalent. `.vscode/settings.json`'s `git.commandsToLog`
surfaces a failing hook's output in VS Code's Git output channel
immediately, instead of only on request.

## Releases

Trigger `.github/workflows/release.yml` manually. It takes a release
channel (`alpha`/`beta`/`rc`/`full`) and which SemVer 2 part to increase
(`major`/`minor`/`patch`/`none`), computes the next tag
(`.github/scripts/compute_next_version.py`), builds the Dockerfile's
`runner` stage, and creates a GitHub release with auto-generated notes
and that image attached as an OCI tarball. See
`.github/workflows/README.md`'s "OCI registry" section for the optional
registry push and the variables/secrets it reads.

## Documentation split

- `CLAUDE.md` (this file) — methods and conventions only, no product
  knowledge.
- `docs/` — knowledge about what the app does, including
  `docs/adrs/` (why a significant, app-specific decision was made —
  see its `README.md`) and `docs/plans/` (in-progress/upcoming work).
- A directory's own `README.md` — the structure and syntax of that
  directory's own contents only, not the wider repo.
