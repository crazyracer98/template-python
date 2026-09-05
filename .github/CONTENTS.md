# .github/

- `workflows/` — GitHub Actions; see its own `README.md`.
- `scripts/` — helper scripts used by the workflows; see its own
  `README.md`.
- `dependabot.yml` — weekly update PRs for Python deps (`uv`), GitHub
  Actions, and the Dockerfile's base images.
- `ISSUE_TEMPLATE/` — issue forms (bug report, feature request) shown
  when opening a new issue.
- `PULL_REQUEST_TEMPLATE.md` — prefills the description box for new PRs.

## Do

- Keep workflow logic that's longer than a few lines in `scripts/` and
  call it from the workflow YAML, rather than growing a shell script
  inline in `run:`.

## Don't

- Pin an Action to a floating tag like `@v7` or `@main` — pin the exact
  patch version (see the root `README.md`'s "Versions and config"
  section).
