# .devcontainer/

- `devcontainer.json` — references `compose.yml` as the devcontainer's
  sole `dockerComposeFile`, and configures the devcontainer itself
  (features, forwarded ports, editor settings).
- `compose.yml` — the app service (`api`), built from the top-level
  `Dockerfile`'s `develop` stage, and an `include:` list that pulls in
  every supporting service's own compose fragment below.
- `stack/` — one subdirectory per supporting service (Postgres,
  RustFS, Redis, Keycloak, Selenium); see its own `README.md`.
- `.env` — credential/config values shared between `compose.yml` and
  `stack/*/compose.yml` via Compose's own variable interpolation
  (`${VAR}`) — not an application dotenv; see the file's own header
  comment and `stack/README.md`'s "Configuration" section.

## Docker-in-Docker vs. the host's Docker

This devcontainer has its own isolated Docker-in-Docker daemon (the
`docker-in-docker` feature in `devcontainer.json`). It is **not** the
same daemon running this project's own compose stack (`api`, `postgres`,
the rest of `stack/`) — that stack is started by whatever invoked
"Reopen in Container" against the *host's* Docker. So `docker`/`docker
compose` run from inside the devcontainer can build and run throwaway
containers of their own, but can never see or `exec` into this project's
sibling containers (e.g. `selenium`) — only a `docker compose` invoked
on the host can. See `stack/selenium/README.md` for the concrete case
this affects.

## SSH agent forwarding

`devcontainer.json`'s `mounts` bind-mounts the host's SSH agent socket
(`${localEnv:SSH_AUTH_SOCK}`) to `/ssh-agent`, and `remoteEnv` points
`SSH_AUTH_SOCK` at it, so `git push` over SSH inside the container
authenticates against the same agent and keys already loaded on the
host — no key material is ever copied into the container. This requires
an agent to actually be running on the host with `SSH_AUTH_SOCK` set
*in the process VS Code itself launches from* (e.g. running `code .`
from the same shell that started the agent) before connecting, and a
full "Rebuild Container" (mounts don't apply to an already-running
container) after this file changes. If `SSH_AUTH_SOCK` is unset when
the container is created (true for `devcontainers/ci` in
`.github/workflows/checks.yml` — GitHub Actions runners have no agent),
`@devcontainers/cli` drops the empty source and the mount degrades to a
plain anonymous volume at `/ssh-agent` instead of erroring — `ssh`/`git`
inside the container then fall back to failing the way they did before
this was added, which is harmless there since CI never pushes.

## Do

- Add a new compose fragment's path to `compose.yml`'s own `include:`
  list the same time you add the fragment — an unreferenced file starts
  nothing.
- Keep service credentials and connection settings in the compose files'
  `environment:` blocks, so opening the devcontainer is the only setup
  step. A value one fragment owns and another needs (e.g. Postgres's
  password) goes in `.env` once, referenced from both, rather than
  hardcoded a second time.
- Write a bind-mount source path in a fragment under `stack/` as
  relative to that fragment's own directory, the same as if it were the
  only Compose file in play — see `stack/README.md`'s "Devcontainer stack
  pattern" section for why. `compose.yml` itself is the exception: since
  it reaches *into* a fragment's directory (its own `env_file:` list,
  `stack/postgres/postgres.env` and friends), those paths are written in
  — and so resolve against — this directory, and need the full
  `./stack/<name>/<file>` form instead.

## Don't

- Bind- or volume-mount the venv, or anything else you don't want a host
  antivirus/DLP tool scanning or syncing — the venv lives purely in the
  container's writable layer instead. (`claude-config` is a deliberate,
  narrow exception — see `compose.yml`'s comment on that volume.)
- Add a `ports:` mapping or a `networks:` block anywhere here — see
  `stack/README.md`'s "Devcontainer stack pattern" section.
- Pin a feature or image version as `latest` — pin the exact version so
  Renovate/Dependabot can bump it deliberately.
