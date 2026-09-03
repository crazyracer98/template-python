# keycloak

Keycloak, the OIDC identity provider the API authenticates against (see
`src/app/oidc.py`, which validates against any PKCE-capable OIDC provider,
not just Keycloak). Starts in dev mode and
auto-imports `realm-export.json`, so a working realm, client, and test user
exist immediately — no manual admin-console setup required.

- Compose file: `compose.yml`
- Image: `quay.io/keycloak/keycloak:26.7.3`
- Host (from other containers): `keycloak`
- Port (container-internal): `8080`
- Realm: `template-python`
- Client ID: `api` (public client, no client secret)
- Admin console user / password: `admin` / `admin`
- Test user / password: `devuser` / `devuser`
- Issuer URL (from other containers): `http://keycloak:8080/realms/template-python`
- Admin credentials and the `OIDC_*` URLs: defined in `keycloak.env`, next to this file

Unlike the other infra-stack services, Keycloak's port is listed in
`forwardPorts` in `.devcontainer/devcontainer.json` so you can reach the
login and admin UI from your host browser at `http://localhost:8080`. That
still isn't a compose `ports:` mapping — see the root README's "Don't" for
why the two are different.

## Do

- Use `devuser` / `admin` for local development only.
- Edit `realm-export.json` and recreate the container (`docker compose up -d
  --force-recreate keycloak`, or rebuild the devcontainer) to change the
  realm, add clients, or add users — it's re-imported on every start.

## Don't

- Add a `ports:` entry to this file; use `forwardPorts` in
  `devcontainer.json` instead (see above).
- Reuse these defaults, or `realm-export.json` as written, anywhere but
  local dev.

## Removing this service

Delete this directory, remove its compose file from the
`dockerComposeFile` array in `.devcontainer/devcontainer.json`, and remove
`8080` from `forwardPorts`/`portsAttributes` there too.
