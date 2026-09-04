# Generic filtering, sorting, and single/bulk actions for the CRUD router factories

## Status

Draft

## Goal

`app/controllers/crud_router.py`'s generated routes currently support only
`skip`/`limit` pagination and path-addressed single-record get/update/delete
(`/{record_id:int}`). Extend the generic factories so every resource built on
them (`heroes.py` and future ones) gets, for free: record addressing via a
query parameter instead of a path segment, per-field filtering (equality,
min/max ranges, substring/regex search, membership) and sorting driven by the
resource's own Pydantic schema, and both single- and bulk-target update/delete
actions — without any resource's controller writing bespoke query logic.

## Why this cuts across more than `crud_router.py`

`crud_router.py` only builds HTTP routes; it has no filtering logic of its
own to extend. The actual capability has to live in the layers it calls
through — `app.crud.base.CRUDLike`/`CRUDInterface`/`CompatCRUD` and
`app.repositories.base.Repository`/`SQLAlchemyRepository`/`InMemoryRepository`
— because that's where "what a filter/sort/bulk-update means against this
storage" is decided. This plan therefore touches all three layers, in the
order below, even though the visible API surface change is entirely in
`app/controllers/`.

`docs/adrs/0001-mvc-layering-with-a-generic-crud-interface.md`'s
"Consequences" section currently says bespoke query/bulk logic belongs in a
resource's own controller, not the shared `CRUDInterface`. This plan
deliberately reverses that guidance for the *generic, schema-driven* case
(a search/bulk endpoint whose shape is derived mechanically from the
resource's own Pydantic fields, not resource-specific business logic). That
reversal is a significant, reversible-at-cost decision and should be written
up as a new ADR (`docs/adrs/0004-...md`) alongside the implementation, not
buried in this plan — see `docs/plans/README.md`.

## Approach

### 1. Storage-agnostic filter/sort vocabulary (`app/repositories/`)

Add `app/repositories/filtering.py`:

- `FilterOp` enum: `EQ`, `NE`, `LT`, `LTE`, `GT`, `GTE`, `IN`, `CONTAINS`
  (case-sensitive substring), `ICONTAINS` (case-insensitive substring),
  `REGEX`.
- `FilterClause` (frozen dataclass): `field: str`, `op: FilterOp`,
  `value: Any`.
- `SortClause` (frozen dataclass): `field: str`, `descending: bool = False`.

These are plain value objects with no SQLAlchemy or Python-eval logic in this
module — each concrete repository interprets them itself, the same way
`Repository` itself stays a `Protocol` with no shared implementation.

Extend `Repository[ModelT]` (`app/repositories/base.py`):

- `list(self, *, skip=0, limit=100, filters: Sequence[FilterClause] = (), sort: Sequence[SortClause] = ())`
- `count(self, *, filters: Sequence[FilterClause] = ()) -> int` — needed both
  to report a bulk action's match count and as a future total-count header.
- `update_many(self, *, filters: Sequence[FilterClause], data: dict[str, Any]) -> Sequence[ModelT]`
- `delete_many(self, *, filters: Sequence[FilterClause]) -> int`

Implement in `SQLAlchemyRepository` via Core `select()`/`update()`/`delete()`
statements with a `_where_clauses()` helper that maps each `FilterClause` to
a SQLAlchemy `ColumnElement` (`EQ`→`==`, `IN`→`.in_()`, `CONTAINS`→`.contains()`,
`ICONTAINS`→`.ilike()`, `REGEX`→`.op("~")()` — Postgres-specific; document
that limitation on the enum member), and a `_order_by()` helper for
`SortClause` (`.asc()`/`.desc()`). Apply the same `FilterClause`/`SortClause`
sequences in `InMemoryRepository` with plain Python predicates/`sorted()`, and
implement `update_many`/`delete_many` there as dict-comprehension equivalents
of the existing single-record `update`/`delete`.

### 2. Pass filters/sort/bulk through the CRUD layer

`app/crud/base.py`: extend `CRUDLike`/`CRUDInterface` with the same
`filters`/`sort` parameters on `list`, and add `update_many`/`delete_many`
that convert the incoming update payload the same way `update` already does
(`data.model_dump(exclude_unset=True)`) and convert results back to the view
via `model_validate` the same way `list` already does — pure passthrough, no
new logic, consistent with `crud/base.py`'s existing "no resource-specific
code" rule.

`app/crud/compat.py`: extend `CompatCRUD` with matching passthroughs
(`list` gains `filters`/`sort`; add `update_many`/`delete_many` using the
existing `from_legacy_update`/`to_legacy` converters) so `/v1/heroes` keeps
working through the same factories once they're extended — same shape as
every other method already there.

### 3. Query-string parsing, driven by the resource's own schema

Add `app/controllers/crud_query.py`: given a Pydantic schema class and a
`starlette.datastructures.QueryParams`, derive the allowed filter operators
per field from that field's annotation —

- numeric/date/datetime fields: exact match (`field=`), range
  (`field__min=`/`field__max=`), membership (`field__in=1,2,3`)
- `str` fields: exact match, `field__contains=`, `field__icontains=`,
  `field__regex=`
- `bool`/`Enum`/`Literal` fields: exact match, `field__in=`

and parse `sort=field,-other_field` (comma-separated, leading `-` =
descending) into `SortClause`s, validating each name against the schema's
own fields. An unrecognized query key or an operator not valid for that
field's type is a 400 (`RequestValidationError`) rather than silently
ignored — see "Open questions" for the exact wire format, which needs to be
settled before writing this module. This is the one new module whose output
(`FilterClause`/`SortClause` sequences) both the plain list route and the
bulk-action routes below consume identically.

### 4. Move record addressing off the path, add single/bulk actions

Split the update/delete route bodies out of `build_json_router` into a new
`app/controllers/crud_actions.py`, called from `crud_router.py` so
`build_json_router`'s own public signature is unchanged for callers like
`heroes.py`. New route shape (JSON router only — see "Open questions" on
scope):

- `GET <prefix>`: if an `id` query parameter is present, single-record
  lookup (404 if missing, response is the resource schema); otherwise the
  existing list behavior, now filtered/sorted via step 3. Kept as one route
  (return type `schema | list[schema]`) rather than two, since both are the
  same underlying `crud.list`/`crud.get` call and FastAPI can't register two
  `GET`s on the same path.
- `PATCH <prefix>` / `DELETE <prefix>`: if `id` is present, today's
  single-record behavior (404 if missing), unchanged except for moving off
  `/{record_id:int}`. Otherwise, the remaining query parameters are parsed
  as filters (step 3) selecting a bulk target set; a request with **no**
  filters and no `id` is rejected (400) unless it explicitly opts in (see
  "Open questions" for the exact opt-in), so an empty query string can never
  bulk-delete/update an entire table by accident. Response is a small
  per-action result view (`app/views/bulk.py`: `BulkUpdateResult`/
  `BulkDeleteResult`) carrying the matched count and, for update, the
  updated records.

Every existing single-record 404/roles/header-forwarding behavior
(`_with_dependency_headers`, `read_roles`/`write_roles`/`delete_roles`) is
preserved for the `id`-present path; it's new only for the bulk branch.

### 5. Views

Add `app/views/bulk.py` with `BulkUpdateResult[SchemaT]`/`BulkDeleteResult`,
following `ORMView`'s existing generic-view conventions.

### 6. Filter/sort metadata endpoint + web-component UI

`crud_query.py`'s per-field-type introspection (step 3) is exactly the
information a generic `<resource>-list>` web component needs to render
filter/sort controls without hardcoding anything resource-specific — so
expose it, rather than leaving the web UI unable to use what the JSON API
now supports:

- `build_web_router` gains a `GET <prefix>/filters` route returning a small
  JSON description derived from the same schema introspection
  `crud_query.py` uses for parsing: one entry per field with its name, kind
  (`"number"`/`"string"`/`"boolean"`/`"enum"`), the operators valid for it
  (mirroring step 3's list — `eq`/`min`/`max`/`in` for numeric,
  `eq`/`contains`/`icontains`/`regex`/`in` for string, etc.), and enum
  choices where applicable. This is metadata only, generated once per
  request from `create_schema`/`schema` the same way `list_fields` already
  is in `build_web_router` today — no new persistence logic.
- `render_crud_component_js` (`app/web_components.py`)'s `<resource>-list>`
  element fetches `${apiBase}/filters` once on `connectedCallback`, renders
  one input per field keyed to its allowed operators (a min/max pair for
  numeric fields, a text input for `contains`/`icontains`/`regex` on string
  fields, a `<select>` for `in`/enum fields) plus a sort `<select>`, and
  builds its `refresh()` fetch's query string from whatever the visitor has
  filled in, using the same `field__op=value`/`sort=` wire format step 3's
  server-side parser expects — one format, defined once, consumed by both
  sides.
- `render_crud_form`'s static zero-JS page doesn't grow filter controls: it
  has no JS to wire dynamic inputs to a fetch call, and a plain HTML
  `<form method="get">` reissuing the page can't express `min`/`max`/regex
  pairs cleanly. It keeps deferring to the `<resource>-list>` web component
  for anything beyond the create form it already renders, same as today.

### 7. Tests

- `tests/unit/repositories/`: `FilterClause`/`SortClause` application for
  both `SQLAlchemyRepository` (or its existing integration coverage, if unit
  tests there run against sqlite/mocks — check current pattern) and
  `InMemoryRepository`, one case per `FilterOp`.
- `tests/unit/controllers/`: `crud_query.py` parsing — valid query strings
  per field type, invalid operator-for-type combinations, unknown field
  names, sort parsing (ascending/descending/multiple fields/unknown field).
- `tests/unit/crud/`: `CRUDInterface`/`CompatCRUD` passthrough for the new
  parameters/methods.
- `tests/integration/controllers/`: `heroes.py` end-to-end against real
  Postgres — filter combinations, sorting, single action via `?id=`, bulk
  update/delete via filters, the no-filter-no-id rejection.
- `tests/unit`: `render_crud_component_js`'s new filter-control rendering
  and `GET <prefix>/filters` metadata shape, mirroring `test_web_components.py`'s
  existing coverage style.
- `tests/e2e`: extend the existing Hero smoke coverage with at least one
  filtered/sorted list call, one bulk action, and one Playwright pass using
  the rendered `<hero-list>` filter controls end-to-end.
- Keep the ≥95% coverage gate green for both the default suite and
  `tests/e2e` (see root `README.md`'s "Checks").

### 8. Documentation, after implementation lands

Update `app/controllers/README.md`'s "Generic CRUD router factories"
section, `app/repositories/README.md`, `app/crud/README.md`, and the root
`README.md`'s worked `curl` examples to reflect the new query shape. Write
`docs/adrs/0004-...md` per the "Why this cuts across more than
`crud_router.py`" section above. Per `docs/plans/README.md`, this plan file
is removed once that's done, not left in place as a record.

## Open questions

- **Exact filter query-param syntax** (`field__min`/`field__gte`,
  `field[gte]`, or something else) — needs to be picked before
  `crud_query.py` is written; affects every resource's public API.
- **Bulk-action safety opt-in**: reject any bulk request with zero filters
  outright, or allow an explicit `all=true` escape hatch to intentionally
  target every record? Affects `crud_actions.py`'s guard clause.
- **Bulk update response size**: return every updated record, or only a
  count, for a match that could be large? Affects `BulkUpdateResult`'s
  shape and whether a max-bulk-size limit is needed.
- **Scope for v1**: filtering/sorting/single-query-param-id/bulk *actions*
  land on `build_json_router` only; `build_web_router` gets read-side
  filtering/sorting (the `/filters` metadata endpoint + web-component UI,
  step 6) but not bulk update/delete controls, and `build_xml_router` stays
  on today's `/{record_id:int}` shape entirely. Confirm this split is
  acceptable, or whether XML needs the same treatment from the start too.
- **`id` vs `record_id`** as the query parameter name for single-record
  addressing — `controllers/README.md` currently documents every path param
  as `record_id` for OpenAPI consistency regardless of a resource's own
  id-field name; decide whether that convention carries over to the query
  param or whether `id` (matching the schema's actual field name) reads
  better now that it's not a path template.
