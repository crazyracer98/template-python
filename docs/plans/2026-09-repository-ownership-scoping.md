# Repository ownership/row-level scoping hook

## Status

Draft

## Goal

`docs/adrs/0008-generic-schema-driven-query-and-bulk-actions.md`'s CRUD/
repository layer has no per-user (row-level) scoping hook: any
authenticated caller with the right role can list, filter, or
bulk-update/delete any record of a resource, regardless of who created
it. Not a problem for the single-tenant Hero example (nothing in this
app is "owned" by a specific user today), but a future resource with
per-user data (e.g. a user's own draft posts, a tenant's own records)
would silently inherit this — nothing in `app.repositories`/`app.interfaces`
stops a broader-than-intended query, and there's no established pattern
to reach for. This plan exists so that decision gets made deliberately,
against a real resource, rather than retrofitted under pressure once one
exists.

Deferred out of `docs/plans/2026-09-owasp-top-ten-hardening.md`'s A01
findings: no current resource needs this, so building it speculatively
risked guessing the wrong shape.

## Approach

Do this the next time a resource with per-user or per-tenant data is
added, not before:

1. Decide where the scoping filter is injected. Two candidate points:
   - `app.repositories.base.Repository`: add an optional
     `owner_filter: FilterClause | None` (or a small sequence of them)
     threaded through `list`/`count`/`update_many`/`delete_many`,
     applied by `SQLAlchemyRepository`/`InMemoryRepository` alongside
     the caller-supplied filters from `app.controllers.crud_query`.
   - `app.interfaces.base.CRUDInterface`: wrap construction so a resource
     opts in by passing an `owner_field`/`owner_value` (or a
     `Callable[[claims], FilterClause]`) at CRUD-dependency-build time
     (see `app.controllers.heroes.get_hero_crud` for the current
     per-request build pattern) — keeps `app.repositories` itself
     unaware of "ownership" as a concept, which may fit this app's
     layering better (repositories are storage-agnostic, not
     claims-aware).
2. Whichever point is chosen, the hook must be **opt-in per resource**
   (a `None`/absent value changes nothing) so Hero and any other
   shared/non-owned resource are unaffected — see
   `app.controllers.README.md`'s "Generic CRUD router factories" for
   the existing precedent of new generic behavior being additive.
3. Wire the actual owner value from `app.oidc`'s claims (typically
   `claims["sub"]`) at the router layer, the same way
   `app.controllers.crud_actions._actor` now reads
   `request.state.claims` for audit logging (added in the OWASP
   hardening pass above) — reuse that mechanism rather than inventing a
   second way to reach the caller's identity from a route.
4. Add unit tests exercising both the scoped and unscoped paths
   directly (mirroring `tests/unit/repositories/test_memory.py`'s
   per-method coverage), plus one integration/e2e test against the
   first real resource that uses it, proving a caller can't reach
   another owner's records via list, get-by-id, or bulk
   update/delete.

## Open questions

- Repository-level vs. CRUD-level injection (see step 1) — likely
  resolved once there's a concrete resource to build it against; revisit
  then rather than guessing now.
