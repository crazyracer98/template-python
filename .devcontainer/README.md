# .devcontainer/

- `devcontainer.json` — merges every compose file below and configures
  the devcontainer (features, forwarded ports, editor settings).
- `compose.yml` — the app service (`api`), built from the top-level
  `Dockerfile`'s `develop` stage.
- `infra-stack/` — one subdirectory per supporting service (Postgres,
  RustFS, Redis, Keycloak, Selenium); see its own `README.md`.
- `.env` — credential/config values shared between `compose.yml` and
  `infra-stack/*/compose.yml` via Compose's own variable interpolation
  (`${VAR}`) — not an application dotenv; see the file's own header
  comment and `CLAUDE.md`'s "Configuration" section.

## Do

- Add a new compose fragment's path to `dockerComposeFile` in
  `devcontainer.json` the same time you add the fragment — an
  unreferenced file starts nothing.
- Keep service credentials and connection settings in the compose files'
  `environment:` blocks, so opening the devcontainer is the only setup
  step. A value one fragment owns and another needs (e.g. Postgres's
  password) goes in `.env` once, referenced from both, rather than
  hardcoded a second time.
- Write a bind-mount source path as relative to this directory, even in
  a fragment several levels under `infra-stack/` — see `CLAUDE.md`'s
  "Devcontainer stack pattern" section for why.

## Don't

- Bind- or volume-mount the venv, or anything else you don't want a host
  antivirus/DLP tool scanning or syncing — the venv lives purely in the
  container's writable layer instead. (`claude-config` is a deliberate,
  narrow exception — see `compose.yml`'s comment on that volume.)
- Add a `ports:` mapping or a `networks:` block anywhere here — see
  `CLAUDE.md`'s "Devcontainer stack pattern" section.
- Pin a feature or image version as `latest` — pin the exact version so
  Renovate/Dependabot can bump it deliberately.
