# scripts/

- `compute_next_version.py` — pure-stdlib script that reads existing git
  tags and prints the next `tag=` / `version=` / `prerelease=` for
  `../workflows/release.yml`, given a release channel and a SemVer 2
  bump.

## Do

- Keep scripts here dependency-free (stdlib only) — they run before
  `uv sync` in the release workflow.
- Add a test in `../../tests/` for any new logic here that isn't trivial.

## Don't

- Have a script here push a tag or create a release directly — that
  stays in the workflow YAML (via `gh`), so the workflow log shows the
  actual side effect.
