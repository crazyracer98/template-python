# playwright

A container with Playwright's browsers preinstalled, for running the
end-to-end tests in `tests/e2e/` against the `api` service over the
docker network. On start it installs the project's `e2e`
optional-dependency group from `pyproject.toml` — the single place those
versions are defined — then idles; you run tests in it on demand.

- Compose file: `compose.yml`
- Image: `mcr.microsoft.com/playwright/python:v1.62.0-noble`
- Target under test: `http://api:8000` (via `E2E_BASE_URL`)
- The `playwright` package version pinned in `pyproject.toml`'s `e2e`
  group must match this image's tag (`1.62.0` ↔ `v1.62.0-noble`) so the
  reinstall on start is a no-op against the browsers already baked into
  the image; bump both together.

## Do

- Run tests from a terminal **on your host machine** (not the
  devcontainer's integrated terminal — see "Don't" below), from the repo
  root:

  ```bash
  docker compose \
    -f .devcontainer/compose.yml \
    -f .devcontainer/infra-stack/postgres/compose.yml \
    -f .devcontainer/infra-stack/s3/compose.yml \
    -f .devcontainer/infra-stack/redis/compose.yml \
    -f .devcontainer/infra-stack/keycloak/compose.yml \
    -f .devcontainer/infra-stack/playwright/compose.yml \
    exec playwright pytest tests/e2e
  ```

- Keep e2e-only dependencies in the `e2e` optional-dependency group in
  `pyproject.toml`, not the main dependency list, and not pinned again
  here.

## Don't

- Run `docker compose exec playwright ...` from *inside* the devcontainer
  (e.g. its integrated terminal, or a VS Code task). The devcontainer has
  its own isolated Docker-in-Docker daemon (see `devcontainer.json`'s
  `features`); from there, `docker`/`docker compose` talks to that inner
  daemon, which has never heard of this project's sibling containers.
  Only a `docker compose` invoked on the host, against the host's own
  daemon, can see and `exec` into them.
- Install browsers with `playwright install` inside the `api` container —
  that's what this separate container is for.
- Point `E2E_BASE_URL` at anything other than the `api` service's
  in-network address.
- Pin package versions in this file's `command:` — bump them in
  `pyproject.toml` instead.

## Removing this service

Delete this directory, its compose file entry in
`.devcontainer/devcontainer.json`, the `e2e` optional-dependency group in
`pyproject.toml`, and `tests/e2e/`.
