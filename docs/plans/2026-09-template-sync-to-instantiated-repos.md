# Deterministic template sync to instantiated repos

## Status

Draft

## Goal

Repos created from this template ("instances") currently have no way to
pull in fixes/improvements made here afterward, short of a manual diff
and cherry-pick. This plan makes that a scheduled, mostly-automatic
GitHub Actions workflow: an instance periodically diffs itself against
the template's latest tagged release and opens a PR that applies the
changes, with a hard split between files it can blindly overwrite and
files it must leave alone or flag for a human.

This only works if the template itself is restructured to make that
split unambiguous — that restructuring is most of this plan.

## Approach

### 1. Classify every file into exactly one sync tier

Add `.github/template-sync-manifest.yml` to this repo, listing every
tracked path (or glob) under one of three tiers. The sync workflow reads
this manifest **from the template repo's tagged ref being synced to**
(not from the instance) so the classification itself evolves with the
template and instances don't need to keep their own copy current.

- `replace` — template-owned, zero instance-specific content ever
  expected. Synced by overwriting the instance's file byte-for-byte with
  the template's. Candidates: `.devcontainer/`, `.github/workflows/`,
  `.github/scripts/`, `.github/dependabot.yml`, `.vscode/`, `.claude/`,
  `scripts/`, `Dockerfile`, `.pre-commit-config.yaml`, `CLAUDE.md`,
  `alembic/env.py`.
- `ignore` — instance-owned, the template never touches it after
  instantiation. Candidates: `docs/` (product knowledge), `src/app/`
  application code beyond the worked Hero example (see below),
  instance-specific `.secrets/` contents (already gitignored), any
  README section a directory's own convention says holds product/domain
  content.
- `merge` — template-owned *shape* with instance-specific *values*
  interpolated in (a project name, a port, a badge URL). Never
  blind-overwritten; the workflow instead computes a **3-way merge**
  (template's previous synced version → template's new version →
  instance's current version, see step 3) and only falls back to
  flagging the file for manual resolution on a genuine conflict.
  Candidates: root `README.md`, `pyproject.toml` (name/version differ
  per instance), `compose.yml`, `.mcp.json` if instance-scoped servers
  were added.

Every path in the repo must land in exactly one tier — a prek hook (see
step 5) fails CI if a new top-level file/directory is added without a
manifest entry, so the classification can't silently go stale.

### 2. Shrink the `merge` tier as far as possible

A 3-way merge still requires human review whenever it can't auto-resolve
cleanly, and every file in `merge` is a file where "just replace" isn't
true yet. Reduce it now rather than accept it as permanent:

- `pyproject.toml`'s `name = "template-fastapi"` and the self-referential
  extra (`template-fastapi[dev]`) are the main things forcing this file
  into `merge`. No action needed if instances are expected to rename the
  project — this is inherent — but confirm nothing else in this file
  (tool config, dependency pins) needs instance-specific edits; if
  nothing else does, the diff noise on every sync is limited to those
  two lines.
- Root `README.md`'s repo name/description at the top forces it into
  `merge` too. Consider splitting it: keep the project-identity preface
  short and instance-owned, move everything else (Contents, Getting
  started, Checks, Versions and config, Code style) into a file that can
  be tier `replace` (e.g. `docs/TEMPLATE.md`, linked from `README.md`)
  if that content is truly identical across instances. Decide this
  explicitly rather than defaulting to `merge` for the whole file — it's
  the highest-traffic file in the repo, so the smaller its `merge`
  surface, the fewer manual conflicts every sync produces.
- `compose.yml` and `.mcp.json`: audit whether instances are actually
  expected to diverge here. If not, move to `replace`.

### 3. Give the template itself a sync-friendly release history

The sync workflow needs three points to do a 3-way merge on `merge`-tier
files: the template commit an instance last synced to, the template's
new target commit, and the instance's current file. `release.yml`
already tags SemVer releases — reuse those tags as sync points rather
than syncing against a moving `main`:

- The workflow syncs to the latest non-prerelease tag by default (a
  repository variable, e.g. `TEMPLATE_SYNC_CHANNEL`, can opt an instance
  into `alpha`/`beta`/`rc` tags instead).
- An instance records the template tag/commit it's currently synced to
  in a small state file, `.github/template-sync-state.json` (tier
  `ignore` — instance-owned, updated only by the sync workflow itself):
  ```json
  { "template_repo": "owner/template-fastapi", "synced_tag": "v1.4.2" }
  ```
  This file is what makes a from-scratch, no-argument re-run of the
  workflow deterministic — it always knows exactly what the last sync
  point was, with no reliance on PR history or commit messages.

### 4. The sync workflow

Add `.github/workflows/template-sync.yml` to the template (so every new
instance gets it for free, and existing instances get it via their own
first sync once this plan ships). It runs in the **instance** repo, not
the template:

1. **Trigger**: `schedule` (cron) plus `workflow_dispatch` for a manual
   run. GitHub Actions cron can't read a per-repo variable to decide its
   *own* interval, so run weekly unconditionally and make the effective
   cadence a repository variable, `TEMPLATE_SYNC_INTERVAL`
   (`weekly` | `monthly`, default `weekly`): the first step exits
   immediately (no-op, green) on a `monthly`-configured instance unless
   the run date falls in the first cron-scheduled week of the calendar
   month. This keeps "how often" a one-line repo setting instead of a
   workflow edit, at the cost of the workflow still *waking up* weekly.
2. **Check for a new tag**: fetch the template repo's tags (`gh api` or
   `git ls-remote`, using the `template_repo` from the state file), find
   the latest matching the configured channel, and stop (no-op) if it's
   the same as `synced_tag`.
3. **Compute the diff per tier**: `git clone` (or add as a temporary
   remote) the template at both `synced_tag` and the new tag.
   - For `replace`-tier paths: copy the new tag's version of each path
     into the instance working tree, deleting any that were removed
     upstream, overwriting unconditionally.
   - For `merge`-tier paths: run `git merge-file` (or equivalent 3-way
     merge) with the instance's current file as "ours", the old tag's
     version as "base", and the new tag's version as "theirs". Clean
     merges apply directly; conflicts get the standard `<<<<<<<` markers
     left in place in the file, and that path is listed in the PR body
     under "needs manual resolution."
   - `ignore`-tier paths are never touched.
4. **Open a PR** (not a direct push) via `peter-evans/create-pull-request`
   or `gh pr create`, titled e.g. `chore(template-sync): sync to v1.5.0`,
   body listing: the tag range synced, files changed per tier, and any
   `merge` conflicts needing attention. Update
   `.github/template-sync-state.json`'s `synced_tag` as part of this
   same commit, so merging the PR is the only action needed to complete
   the sync — no separate bookkeeping step.
5. **Never auto-merge.** The instance's own `checks.yml` runs on the PR
   like any other; a human merges once CI is green and any conflict
   markers are resolved.

### 5. Guardrails so the manifest can't silently drift

- A prek hook (`.pre-commit-config.yaml`, `manual` stage) diffs
  `git ls-files` against the manifest's path list and fails if anything
  is untracked by it — run at the same cadence as the other manual-stage
  hooks (`uv run prek run --all-files --hook-stage manual`), and also
  add it to `checks.yml` so a PR that adds a new top-level file/directory
  without a manifest entry fails CI in the template repo itself.
- Document the manifest and this workflow in
  `.github/workflows/README.md` (extend its existing per-workflow list)
  and add a short "Template sync" section to the root `README.md`'s
  contents list, per this repo's own convention of documenting
  conventions in the nearest `README.md` rather than here.

### 6. Rollout for already-instantiated repos

Existing instances predate `template-sync-state.json`. Ship a short
one-time bootstrap: a `workflow_dispatch`-only input on
`template-sync.yml` (`initial_sync_tag`) that seeds the state file at a
chosen tag instead of erroring when the state file is missing, so an
existing instance's first run establishes its baseline explicitly rather
than guessing.

## Open questions

- Which tag should an existing instance bootstrap from — the tag
  closest to when it was actually created (accurate baseline, requires
  someone to look it up per instance) or simply the oldest available tag
  (safe but produces one large first-sync diff)? Needs a decision per
  existing instance, not a single repo-wide default.
- Does `.claude/` belong entirely in `replace`, or does any instance
  customize `.claude/settings.json` permissions locally? If the latter
  happens in practice, it needs its own `merge` handling (likely just
  the permissions list) rather than blocking the rest of `.claude/` from
  being tier `replace`.
