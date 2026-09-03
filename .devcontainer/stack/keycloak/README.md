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
- Test users / password (same as username): `viewer`, `editor`, `security`,
  `maintainer`, `detective` — all with the same `offline_access` /
  `uma_authorization` realm roles; see `realm-export.json` for names/emails
- Issuer URL (from other containers): `http://keycloak:8080/realms/template-python`
- Admin credentials and the `OIDC_*` URLs: defined in `keycloak.env`, next to this file

Unlike the other infra-stack services, Keycloak's port is listed in
`forwardPorts` in `.devcontainer/devcontainer.json` so you can reach the
login and admin UI from your host browser at `http://localhost:8080`. Since
Keycloak runs in a sibling container rather than the primary `api` one, that
entry must use the `"keycloak:8080"` (`serviceName:port`) form, not a bare
`8080` — a bare port number only forwards from the primary container. That
still isn't a compose `ports:` mapping — see the root README's "Don't" for
why the two are different.

From inside the devcontainer, `kcadm` (installed by `scripts/develop.sh`) is
a thin curl wrapper around the Admin REST API — a lighter alternative to the
official `kcadm.sh`, which ships only inside Keycloak's full server
distribution and needs a JVM neither this stage nor the app otherwise
requires. It logs in as `KEYCLOAK_ADMIN`/`KEYCLOAK_ADMIN_PASSWORD` (from
`keycloak.env`, already in the devcontainer's environment) and takes an
HTTP method, an Admin REST API path, and an optional JSON body:

```bash
kcadm GET /admin/realms/template-python/users
kcadm PUT /admin/realms/template-python/users/<id> '{"firstName": "Dev"}'
```

## Do

- Use the test users or `admin` for local development only.
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
`"keycloak:8080"` from `forwardPorts`/`portsAttributes` there too.
