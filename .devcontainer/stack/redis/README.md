# redis

Redis 7, for caching, background-job queues, or pub/sub.

- Compose file: `compose.yml`
- Image: `redis:7.4.11-alpine`
- Host (from other containers only — see root README's "Don't"): `redis`
- Port (container-internal): `6379`
- Connection URL: `redis://redis:6379/0`
- Data volume: `redis-data` (append-only persistence enabled)

## Do

- Reach this service from a tool running inside the devcontainer network
  rather than publishing the port to the host: the `redis-cli` CLI
  (installed by `scripts/develop.sh` — run `redis-cli -h redis`), or
  Claude's `redis` MCP server (`../../../.mcp.json` — see
  `../../../.claude/README.md`).

## Don't

- Publish this service's port to the host, or reuse these defaults
  anywhere but local dev.

## Removing this service

Delete this directory and remove its compose file entry from
`.devcontainer/compose.yml`'s `include:` list.
