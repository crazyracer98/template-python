# scripts/

Setup logic for each `Dockerfile` RUN step — every RUN in the Dockerfile
calls exactly one of these, never a binary directly:

- `develop.sh` — the `develop` stage: apt packages, `uv`, the Claude Code
  CLI, and `pyright` (for the `pyright-lsp` plugin — see
  `.claude/README.md`).
- `builder.sh` — the `builder` stage's tooling setup (apt packages, `uv`).
- `builder-sync-deps.sh` / `builder-sync-app.sh` — the `builder` stage's
  two `uv sync` steps, split so a source-only change doesn't invalidate
  the dependency-install layer.
- `runner-setup.sh` — the `runner` stage's user/permission setup.
- `runner.sh` — the `runner` stage's entrypoint (starts the app).

## Do

- Keep each script runnable and idempotent on its own (`bash
  scripts/develop.sh <args>`) so you can debug a stage without a full
  build.
- Take a version as a script argument (see `develop.sh`) rather than
  hardcoding it, when the Dockerfile already defines it as an `ARG` —
  keeps that `ARG` the single source of truth.
- Clean up apt lists / caches at the end of a script that installs
  packages, to keep the resulting layer small.

## Don't

- Invoke a binary directly from a Dockerfile `RUN` — add or extend a
  script here instead.
- Install tooling a different stage needs — `runner.sh` in particular
  should stay a plain entrypoint, not a setup script.
