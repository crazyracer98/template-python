# .claude/

Project-scope Claude Code configuration, shared with every collaborator
who opens this repo (see the root `.gitignore`, which does *not* exclude
this directory).

- `settings.json` — enables the official `pyright-lsp` plugin so Claude
  gets type diagnostics and code navigation from pyright directly,
  instead of grep-based exploration; this is what `scripts/develop.sh`
  installs `pyright`/`pyright-langserver` for. Also wires up the
  `PostToolUse` hook below.
- `hooks/self-check.sh` — after Claude edits a file, runs the fast,
  pre-commit-stage hooks from `../.pre-commit-config.yaml` (ruff, trailing
  whitespace, ...) against just that file via `prek`, so issues are
  caught and auto-fixed immediately instead of first at commit time.
  mypy/pytest/`uv lock --check` stay pre-push-only — too slow to run
  after every edit.
- The `PreToolUse` hook on `Bash` runs `snip hook`, the
  [snip](https://github.com/edouard-claude/snip) token-filtering proxy:
  it rewrites supported commands (this repo's stack — `pytest`, `ruff`,
  `mypy`, `uv` — plus `git` and others) to return only their signal
  (failures, diffs, summaries) instead of full output. `snip` itself is
  installed by `scripts/develop.sh`, pinned to `SNIP_VERSION` in the
  Dockerfile, and checksum-verified against its published release
  checksums — see "Single source of truth for versions and config" in
  the root `CLAUDE.md`. Chosen over the more popular
  [rtk](https://github.com/rtk-ai/rtk) because its filters are
  declarative YAML data (auditable, and cover `mypy` — rtk's don't) and
  it fails open (a broken filter passes the command through unfiltered
  rather than blocking it); rtk's larger community and multi-maintainer
  team are the tradeoff, so revisit this choice if `snip` goes
  unmaintained.

## Do

- Keep this file's `enabledPlugins` pinned to specific plugin names —
  don't rely on a whole marketplace being auto-installed.

## Don't

- Add personal preferences here — this file is committed and shared;
  use your own user-scope Claude Code settings for those instead.

## Removing a tool

- **pyright-lsp**: delete `settings.json`'s `enabledPlugins` entry and
  remove the `pyright`/`pyright-langserver` install step from
  `scripts/develop.sh`.
- **snip**: delete the `PreToolUse` hook entry in `settings.json` and the
  `snip` install block (and `SNIP_VERSION` ARG in the Dockerfile) from
  `scripts/develop.sh`.
