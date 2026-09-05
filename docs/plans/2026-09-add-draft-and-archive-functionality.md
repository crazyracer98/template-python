# Add draft and archive functionality

## Status

Draft

## Goal

Add a set of generic, opt-in record-lifecycle behaviors to the CRUD
framework, following the precedent set by `OwnerScope`
(`src/app/interfaces/base.py`) and the ownership-scoping plan: additive
machinery in `app.models`/`app.repositories`/`app.interfaces`/
`app.controllers`, demonstrated end-to-end on the `Hero` example
resource, that a future resource opts into rather than something baked
into one resource's own router. Each behavior below is independent —
adopting one mixin never requires adopting another.

- **Archive**: `DELETE` no longer removes the row; it's marked
  archived and excluded from normal reads, with a way to list/restore
  it (single record or in bulk).
- **Draft**: a record can be created with every attribute optional,
  then later completed/published once all required fields are filled
  in.
- **Scheduled publish/unpublish**: a record becomes visible or stops
  being visible at a specific time, with no job needed to flip it.
- **Scheduled purge**: archived rows past a configured age are
  hard-deleted by an out-of-request-path job.
- **Duplicate/clone**: copy an existing record into a new one.
- **Lock/read-only**: block further edits/deletes on a record without
  archiving or deleting it.
- **Revision history**: an append-only log of who changed what on a
  record and when.

## Approach

### Archive (soft-delete via a marker column, not a second table)

Reuse the row in place, in the same table, rather than moving it to a
separate archive table:

- A second table would need its own SQLAlchemy model per archivable
  resource, breaking `Repository[ModelT]`'s single-model-per-table
  genericity (see `repositories/README.md`) — every generic method
  (`list`/`filter`/`sort`/bulk actions) would need a matching
  implementation against the archive table too.
- A marker column keeps every existing generic mechanism (filtering,
  sorting, bulk actions, pagination) working against archived rows for
  free — "list archived records created last week" is just
  `?archived=true&created_at__gte=...`, no new query surface.
- The tradeoff (an archived row still costs table/index space, still
  collides on unique constraints) is real but cheaper than duplicating
  the generic layer; note it in the ADR (see step 5) so it's a
  recorded decision, not an accident.

Steps:

1. Add an `Archivable` mixin in `models/base.py` (or a new
   `models/mixins.py`, following `crud_1/README.md`'s "package once it
   grows" convention if more than one mixin accumulates):
   `archived_at: Mapped[datetime | None] = mapped_column(default=None)`.
   Opt-in per model — `Hero(IdentifiedBase, Archivable)`.
2. `repositories/base.py`'s `Repository` Protocol gains `restore
   (record_id) -> ModelT | None`, alongside the existing `delete`.
   `SQLAlchemyRepository`/`InMemoryRepository`: for a model carrying
   `archived_at` (checked via `hasattr`, mirroring how `memory.py`
   already special-cases `created_at`/`updated_at`), `delete`/
   `delete_many` set `archived_at=now()` instead of issuing a real
   `DELETE`, and `restore` clears it back to `None`. A model without
   the column keeps today's hard-delete behavior unchanged — no
   behavior change for a resource that doesn't opt in.
3. `list`/`get`/`count` exclude archived rows by default for an
   archivable model; add `include_archived: bool` alongside the
   existing `filters`/`sort` parameters (repository → `CRUDInterface`
   → `crud_router.py`) rather than forcing a caller to know to write
   `archived_at__is=null` by hand. Wire it in
   `app.controllers.crud_query` as a `?include_archived=true` query
   flag, next to the existing `field__op=value`/`sort=` parsing —
   see its module docstring for the wire-format convention to match.
4. Restore mirrors delete's own id-or-filters shape exactly, single and
   bulk together, rather than being a separate bulk feature bolted on
   later:
   - `repositories/base.py`'s `Repository` Protocol also gains
     `restore_many(*, filters) -> Sequence[ModelT]`, alongside the new
     `restore` above — the same pairing `delete`/`delete_many` already
     has. Both concrete repositories implement it as clearing
     `archived_at` on every matching row.
   - `interfaces/base.py`'s `CRUDInterface` gains `restore`/
     `restore_many`, copied from `delete`/`delete_many`'s own bodies
     (owner-scoped branch included) with `restore`/`restore_many`
     substituted for `delete`/`delete_many`.
   - `controllers/crud_actions.py` gains `resolve_restore`, copied from
     `resolve_delete`'s own body the same way, logging `"Bulk restore:
     ..."` and returning `BulkUpdateResult` (matched + ids) — restore's
     bulk response shape is identical to update's, so no new view is
     needed in `views/bulk.py`.
   - `crud_router.py`'s `build_json_router`/`build_xml_router` add one
     `POST <prefix>/restore` route (generated only when the bound model
     is archivable) that calls `resolve_restore` — `?id=` restores one
     record, filters with no `id` restore in bulk, no filters and no
     `id` is rejected, exactly like the existing delete route. Apply
     the same `@limiter.limit(settings.rate_limit_bulk_action)` /
     `exempt_single_record_action` treatment `app/README.md`'s "Rate
     limiting" section describes for the existing bulk routes.
5. Write `docs/adrs/00NN-soft-delete-via-marker-column.md` once this
   lands, capturing the "marker column vs. second table" decision above
   — this is exactly the kind of significant, reversible-at-cost choice
   `docs/plans/README.md` says belongs in an ADR, not left in this plan
   file.

### Draft (every attribute optional until published)

A draft is a record accepted through the same all-optional shape the
`*Update` view already uses for partial updates — no new "every field
optional" schema needs inventing:

1. Add a `Draftable` mixin (same file as `Archivable`):
   `is_draft: Mapped[bool] = mapped_column(default=True)`. Because it's
   a plain column, it's filterable/sortable through the existing
   generic query machinery with no new wire-format work
   (`?is_draft=false` already works once `crud_query.py` sees the
   field) — unlike archive, draft doesn't need default-exclusion logic;
   whether drafts show up in a plain, unfiltered list is a product call
   (see "Open questions").
2. `views/hero_v2.py`'s existing `HeroV2Update` shape (all fields
   `| None = None`) is what a draft create/update body validates
   against — no new Pydantic model. `build_resource_router` needs a
   second, optional `draft_schema` argument (defaults to `None`) a
   draftable resource passes its `*Update` view into, generating
   `POST <prefix>/draft` (accepts the update-shaped body, persists with
   `is_draft=True`, `id` and any omitted fields taking their column
   defaults — every column an eventual draft needs therefore must
   itself be nullable at the DB level, not just optional in the create
   view; check this against `Hero.name`/`Hero.powers`'s current
   `nullable=False` before adopting on Hero itself).
3. Add `POST <prefix>/publish?id=` (generated alongside `/draft`,
   conditional on `draft_schema` being set): re-validates the full
   record against the resource's normal `*Create` view (catching any
   field still missing/None) and flips `is_draft=False` on success,
   422 on failure with the missing fields named.
4. `CRUDInterface`/`Repository` need no changes for draft — it's a
   plain column read/written through the existing `create`/`update`
   path; all the new logic is in the controller-layer routes above.

### Scheduled publish/unpublish

Visibility computed live at read time from two timestamp columns,
rather than a job flipping a flag — avoids needing any scheduler/worker
infrastructure at all, unlike purge below:

1. Add a `Schedulable` mixin: `publish_at: Mapped[datetime | None]`,
   `unpublish_at: Mapped[datetime | None]`, both defaulting to `None`
   (no scheduling — always visible, subject to draft/archive rules).
2. `repositories/filtering.py` already has `FilterOp.LT`/`LTE`/`GT`/
   `GTE`; the default-exclusion logic added for archive (step 3 above)
   extends, for a `Schedulable` model, to also exclude rows where
   `publish_at > now()` or (`unpublish_at` is set and `unpublish_at <=
   now()`) — expressed as ordinary `FilterClause`s built with
   `datetime.now(UTC)` at query time, not a stored boolean, so no
   background process ever needs to touch the row. `include_archived`'s
   query-flag precedent (step 3) extends the same way, e.g.
   `include_unpublished=true`, for a caller (an editor previewing a
   scheduled post) that needs to see it before it goes live.
3. No new routes — a record becomes visible or stops being visible
   purely by wall-clock time passing; setting the two columns is just a
   normal `update`.

### Scheduled purge of archived rows

The one piece here that's a genuine background job rather than
request-path code, since it permanently deletes data — this app's
devcontainer stack has no scheduler/worker service today (see
`compose.yml`), and adding one would be new shared infrastructure, not
a request-path change, so this stays a script invoked externally
(host/k8s cron) rather than something the app schedules itself:

1. Add a flat module — `app/maintenance.py` (not `scripts/`, which
   `scripts/README.md` reserves for Dockerfile `RUN` steps only) —
   exposing an `async def purge_archived(session, *, older_than:
   datetime) -> int` that iterates SQLAlchemy's own mapper registry
   (`Base.registry.mappers`) for models carrying `archived_at`, so it
   needs no per-resource wiring the way the request-path code above
   does, and deletes rows with `archived_at <= older_than`.
2. Add `archive_purge_after_days: int | None` to `config.py`'s
   `Settings` (default `None` — disabled), following the "Do" in
   `app/README.md` for adding settings.
3. A thin `if __name__ == "__main__":` entrypoint in `maintenance.py`
   (`python -m app.maintenance`) a host/k8s `CronJob` invokes on its own
   schedule — no new compose service, no in-process scheduler
   dependency added to `main.py`.

### Duplicate/clone

Fully generic — no mixin required, every resource gets this once
`build_json_router` adds it:

1. `crud_router.py` adds `POST <prefix>/clone?id=`: `record =
   await crud.get(id)`, 404 if missing, then build the resource's
   `create_schema` from `record.model_dump(exclude={"id", "created_at",
   "updated_at"})` and call `crud.create(...)` — the same `create_schema`
   the factory already takes for `POST <prefix>`, no new parameter
   needed.
2. A clone of a `Draftable` record is always created with
   `is_draft=True` regardless of the source's own state (cloning a
   published record shouldn't silently publish an identical duplicate);
   a clone of an `Archivable`/`Schedulable` record never carries over
   `archived_at`/`publish_at`/`unpublish_at` — all three are
   server-assigned/excluded from `create_schema` already, so this falls
   out of step 1 rather than needing special-casing.

### Lock/read-only

1. Add a `Lockable` mixin: `is_locked: Mapped[bool] =
   mapped_column(default=False)`.
2. Enforcement lives in the repository layer, not the controller,
   since it must be atomic with the mutation itself: `SQLAlchemyRepository`/
   `InMemoryRepository`'s `update`/`update_many`/`delete`/`delete_many`,
   for a `Lockable` model, refuse (raise a new `RecordLockedError`) when
   the existing row's `is_locked` is `True` — with one explicit escape
   hatch: an `update` call whose own `data` sets `is_locked=False` is
   always allowed through, so unlocking a record is just a normal
   update, never a separate bypass path. `crud_actions.py` catches
   `RecordLockedError` and raises `HTTPException(status.
   HTTP_423_LOCKED, ...)`.
3. No dedicated `/lock`/`/unlock` routes needed — both are just
   `PATCH <prefix>?id=` with `{"is_locked": true|false}` in the body,
   reusing the existing update route and view field.

### Revision history

The one place a second table is the right shape rather than the
anti-pattern archive's ADR argues against — a revision is a distinct,
many-per-record entity, not the same record relocated, and it needs no
generic `list`/`filter`/`sort` machinery of its own:

1. Add one shared `Revision` model (`models/revision.py`, not
   per-resource): `id`, `resource: str`, `record_id: int`, `action: str`
   (`"create"`/`"update"`/`"delete"`), `snapshot: Mapped[dict]`
   (`postgresql.JSONB`), `actor: str`, `created_at`. One table for every
   resource, keyed by `resource`+`record_id`, rather than a table per
   resource — matches `Archivable`/`Draftable`'s "purely additive,
   nothing resource-specific" shape.
2. `interfaces/base.py`'s `CRUDInterface` gains an optional
   `revisions: RevisionSink | None = None` constructor parameter
   (parallel to the existing `owner: OwnerScope | None`) — a small
   `Protocol` with `async def record(self, *, resource: str, record_id:
   int, action: str, snapshot: dict, actor: str) -> None`. Every
   `create`/`update`/`update_many`/`delete`/`delete_many` calls it after
   a successful mutation when set; `revisions=None` (the default)
   changes nothing, same opt-in shape as `owner`.
3. Actor needs to reach `CRUDInterface`, which today only sees requests
   through the controller layer — reuse `crud_actions.py`'s existing
   `_actor(request)` helper, threaded down to the CRUD-dependency
   builder the way `heroes_v2.get_hero_crud` already resolves
   `OwnerScope`'s value from claims per request (see
   `interfaces/README.md`'s "Do").
4. Add `GET <prefix>/revisions?id=` (conditional on the resource having
   opted in) returning that record's revisions, newest first — a plain
   query against the shared `Revision` table filtered by `resource`/
   `record_id`, not routed through `CRUDLike` at all since it's reading
   a different model entirely.
5. Build this one last, once archive/draft/clone/lock are in place and
   demonstrated on Hero — it's the most invasive change (a new
   cross-cutting constructor parameter every call site touches) and
   benefits most from a stable pattern to copy.

### Demonstrate on Hero

Adopt every mixin on `Hero` as the worked example (`models/README.md`'s
"Add a migration after adding or changing a model" applies —
`uv run alembic revision --autogenerate`), relaxing `name`/`powers` to
nullable to support drafts, and add the new routes (`/draft`,
`/publish`, `/restore`, `/clone`, plus `?include_archived=`/
`?include_unpublished=` on the existing list; lock/unlock reuse the
existing update route; revisions build last, per its own step 5 above)
to `heroes_v2.py` only (not the deprecated `v1` sibling, matching how
bulk actions were rolled out as a v2-only capability per
`docs/adrs/0008-...md`). Build and demonstrate in the order the
subsections above are written — archive and draft first (cheapest,
highest-reuse), then scheduled publish/purge/clone/lock, revisions
last.

### Tests

- Unit: `tests/unit/repositories/test_memory.py`-style per-method
  coverage for `restore`/`restore_many`, and for `delete`/`list`/
  `count`'s archived branch, against both `InMemoryRepository` and
  `SQLAlchemyRepository`.
- Unit: draft create with a partial body, then publish (success and
  422-missing-fields cases).
- Unit: `Schedulable` filtering — a record with a future `publish_at`
  excluded by default and visible with `include_unpublished`; same for
  a past `unpublish_at`.
- Unit: `app.maintenance.purge_archived` against a fixture session,
  asserting only rows past `older_than` are removed and unarchived
  rows are untouched.
- Unit: `/clone` preserves fields but resets `id`/timestamps and (for a
  `Draftable` model) forces `is_draft=True` regardless of the source.
- Unit: a locked record's update/delete raises `RecordLockedError` /
  surfaces as 423, except an update that itself sets
  `is_locked=False`.
- Unit: `RevisionSink` receives one call per successful mutation, with
  `revisions=None` (the default) leaving `CRUDInterface` unchanged.
- Integration/e2e: one full lifecycle test — create draft → publish →
  lock → attempt (and fail) an edit → unlock → archive → list (excluded)
  → list with `include_archived` → restore → clone → check
  `/revisions` reflects the sequence — against `/crud/v1/heroes/v2/json`.

## Open questions

- Should a plain, unfiltered `GET <prefix>` include drafts by default,
  or exclude them the way archived rows are excluded? Archive's
  exclude-by-default has a clear rationale (a deleted-looking record
  shouldn't reappear in a normal list); draft is less obvious — a
  content-management use case usually still wants an editor to see
  their own drafts in the main list. Resolve this against whichever
  real (non-Hero) resource first needs draft, following the same
  "decide once a real caller exists" reasoning
  `docs/adrs/0011-owner-scoped-crud-example-resource.md` used for
  ownership scoping — Hero's demo can default to "include," documented
  as provisional.
- Interaction with `OwnerScope`/row-level scoping (`src/app/interfaces/
  base.py`, built — see `docs/adrs/0011-owner-scoped-crud-example-
  resource.md`): does a caller's own drafts stay visible to them
  specifically, independent of the include/exclude default above? Note
  carries no draft concept yet, so this is still open against whichever
  resource adopts both.
- Purge (step 2 of "Scheduled purge of archived rows") introduces the
  first operational dependency on an external scheduler (host/k8s
  cron) this devcontainer-only stack doesn't otherwise have — confirm
  that's acceptable, or whether purge should instead be a manually
  invoked script with no assumed schedule at all until a real
  deployment target needs automation.
- Revision history's storage growth is unbounded by this plan (every
  mutation adds a row, forever) — worth a retention policy (folded into
  the purge job once it exists) before this ships against a
  high-write-volume resource, but not blocking for the Hero demo.
- Lock's "an update setting `is_locked=False` is always allowed through
  while locked" escape hatch also lets that same call change every
  other field in the same payload (a `PATCH` with `{"is_locked": false,
  "name": "new name"}` unlocks and edits in one request) — confirm
  that's the intended behavior, or whether unlocking should be a
  dedicated request that touches no other field.
