# Add architecture and system design documents

## Status

Draft

## Goal

The app currently has no single diagram-backed document showing how the
devcontainer stack's services fit together, nor one showing the
application's own internal design end-to-end — that knowledge is
scattered across each directory's `README.md`. Add two docs under
`docs/`: an architecture document (infrastructure/deployment view, with
a Mermaid diagram of the stack services and how they connect) and a
system design document (application-level view: layering, request
flow, key design decisions), and wire maintenance reminders into the
two directories whose changes are most likely to make either doc stale.

## Approach

1. **`docs/architecture.md`** — infrastructure/deployment view of the
   system: the `api` service plus each `.devcontainer/stack/` service
   (Postgres, RustFS/S3, Redis, Keycloak, Selenium), how they connect
   (network, healthchecks/`depends_on`, which ports are host-forwarded
   vs. container-only), and how this differs between the devcontainer
   and the `compose.yml` runner-image smoke test at the repo root.
   Include a Mermaid `graph` diagram (same style as the one in
   [src/app/README.md](../../src/app/README.md)'s "Layering" section)
   showing `api` and each stack service as nodes, with edges for
   `depends_on: condition: service_healthy`. Base the content on
   [.devcontainer/stack/README.md](../../.devcontainer/stack/README.md),
   [.devcontainer/compose.yml](../../.devcontainer/compose.yml), and each
   service's own `README.md`.

2. **`docs/system-design.md`** — application-level view: the MVC-ish
   layering from [src/README.md](../../src/README.md)/
   [src/app/README.md](../../src/app/README.md) (models → views →
   repositories → crud → controllers → main), the multi-format
   sibling-router pattern (JSON/XML/HTML form), auth (OIDC + `MODE`-
   driven fakes per [ADR 0006](../adrs/0006-mode-driven-fakes-for-infrastructure-free-testing.md)),
   and a request-flow Mermaid `sequenceDiagram` (client → controller →
   crud → repository → model, and back). Link out to the relevant ADRs
   in `docs/adrs/` instead of restating their reasoning, per that
   directory's own convention. Base the content on
   [src/app/README.md](../../src/app/README.md) and its subpackage
   `README.md`s.

3. **Add a maintenance note to `.devcontainer/stack/README.md`** — a
   short line (fits under its existing "Do" list, or a new one-line
   note near the top) stating that adding, removing, or changing how a
   stack service connects (new service, changed `depends_on`/
   healthcheck, forwarded port) requires updating
   [docs/architecture.md](../../docs/architecture.md)'s diagram to
   match.

4. **Add a maintenance note to `src/README.md`** — a short line stating
   that a change to the general system design (new subpackage, changed
   layering/import order, a new cross-cutting flat module) requires
   updating [docs/system-design.md](../../docs/system-design.md) to
   match. (`src/app/README.md` already owns the authoritative layering
   list and its own Mermaid diagram; `docs/system-design.md` is the
   higher-level summary that must stay consistent with it — the note
   belongs on `src/README.md` since that's the level the task called
   out, not duplicated onto `src/app/README.md` too.)

5. Add both new docs to [docs/README.md](../../docs/README.md)'s
   bullet list, alongside `adrs/`, `plans/`, etc.

No code changes, so no `ruff`/`mypy`/`pytest` run is needed — verify by
checking the Mermaid diagrams render (e.g. via a Markdown previewer) and
that every relative link in the new docs resolves.

## Open questions

None.
