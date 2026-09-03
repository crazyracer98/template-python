# redis

Redis 7, for caching, background-job queues, or pub/sub.

- Compose file: `compose.yml`
- Image: `redis:7.4.11-alpine`
- Host (from other containers only — see root README's "Don't"): `redis`
- Port (container-internal): `6379`
- Connection URL: `redis://redis:6379/0`
- Data volume: `redis-data` (append-only persistence enabled)

## Do

- Use these default credentials for local development only.

## Don't

- Publish this service's port to the host, or reuse these defaults
  anywhere but local dev.

## Removing this service

Delete this directory and remove its compose file from the
`dockerComposeFile` array in `.devcontainer/devcontainer.json`.
