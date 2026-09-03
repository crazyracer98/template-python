# infra-stack/

One subdirectory per supporting service (database, object storage,
cache, identity provider, e2e test runner, ...). Each contains:

- `compose.yml` — the Compose fragment for that service.
- `README.md` — what it is, connection details, and how to remove it.
- `<service>.env` — that service's local-dev-only default credentials,
  loaded via `env_file:` in this fragment's `compose.yml` (and, where
  `api` needs the same values, listed again under its own `env_file:` in
  `../compose.yml` — see CLAUDE.md's "Configuration" section) — only
  present when the service actually has credentials to hold (redis and
  playwright don't).

Every fragment here is listed in `dockerComposeFile` in
`../devcontainer.json`, so all of them start together. Because
`../compose.yml` (the app service) is always first in that array, any
relative bind-mount or `env_file:` path in a fragment here — like
keycloak's `realm-export.json` or `keycloak.env` — is resolved relative
to `.devcontainer/`, not to the fragment's own directory; see each
fragment's own header comment.

## Do

- Give a new service its own subdirectory following this same
  `compose.yml` + `README.md` pattern, plus a `<service>.env` if it has
  credentials or other config values to hold.
- Let it join the default network compose generates for this project —
  don't declare a `networks:` block; every service reaches every other
  one by its service name already.
- If host-browser access to the service is genuinely needed (as with
  keycloak's login UI), add its port to `forwardPorts`/`portsAttributes`
  in `../devcontainer.json` — never to a `ports:` mapping here.
- Pin an image tag to the app version only (`postgres:16.15-alpine`),
  not the OS sub-patch a multi-part tag like `postgres:16.15-alpine3.24`
  adds on top — Renovate/Dependabot still bumps the app version fine
  either way, and the extra digits just add unrelated diffs. A tag
  segment that names a genuinely different build variant (`-glibc` vs.
  the default, `-noble` vs. another base OS) isn't this kind of
  precision and stays.

## Don't

- Add a `ports:` entry to any fragment here. These are backend services
  reached only from other containers on the docker network; publishing a
  host port defeats that isolation. See the root README's "Don't".
- Reuse another service's volume or hostname.
- Put real credentials in a fragment here — these are local-dev-only
  defaults; production configuration is a deployment concern, not this
  template's.
