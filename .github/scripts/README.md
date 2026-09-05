# scripts/

- `compute_next_version.py` — pure-stdlib script that reads existing git
  tags and prints the next `tag=` / `version=` / `prerelease=` for
  `../workflows/release.yml`, given a release channel and a SemVer 2
  bump.
- `template_sync_manifest.py` — parses `../template-sync-manifest.yml`
  and checks that every git-tracked path matches exactly one tier;
  backs both the `template-sync-manifest` prek hook and
  `../workflows/template-sync.yml`'s own use of the manifest.
- `template_sync.py` — the diff/apply/state-file logic behind
  `../workflows/template-sync.yml`: picks the latest tag for a channel,
  applies the `replace`/`merge` tiers between two template checkouts and
  the instance working tree, and reads/writes
  `../template-sync-state.json`.

## Do

- Keep scripts here dependency-free (stdlib only) — they run before
  `uv sync` in the release workflow.
- Add a test in `../../tests/` for any new logic here that isn't trivial.

## Don't

- Have a script here push a tag or create a release directly — that
  stays in the workflow YAML (via `gh`), so the workflow log shows the
  actual side effect.
