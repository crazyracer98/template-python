# app/repositories/

Storage-agnostic CRUD access that `app.interfaces`'s generic interface talks
to, parameterized by a model type rather than one class per resource.

- `base.py` — `Repository[ModelT]`, the `Protocol` `app.interfaces.base.
  CRUDInterface` is written against: `get`/`list`/`create`/`update`/
  `delete`/`count`/`update_many`/`delete_many`/`restore`/`restore_many`,
  all storage-agnostic. `list`/`update_many`/`delete_many` take
  `filters`/`sort` sequences from `filtering.py`. Also `RecordLockedError`,
  raised by `update`/`update_many`/`delete`/`delete_many` for a
  `Lockable` (see `../models/README.md`'s `mixins.py`) record whose
  `is_locked` is `True` — except a call whose own `data` itself sets
  `is_locked=False`, which is always let through, so unlocking is a plain
  `update`, never a separate bypass path.
- `filtering.py` — `FilterOp` (the comparison operators a filter can use:
  `EQ`/`NE`/`LT`/`LTE`/`GT`/`GTE`/`IN`/`CONTAINS`/`ICONTAINS`/`REGEX`),
  `FilterClause` (one field/op/value comparison), and `SortClause` (one
  field to sort by). Plain value objects with no SQLAlchemy or
  Python-eval logic — each concrete repository below interprets them
  itself, the same way `Repository` stays a `Protocol` with no shared
  implementation. `app.controllers.crud_query` is the only place that
  turns an HTTP query string into these (see its own module docstring for
  the wire format); a repository never parses a query string itself.
- `sqlalchemy.py` — `SQLAlchemyRepository[ModelT]`, the default concrete
  implementation: bound to an `AsyncSession` and an `app.models.base.
  IdentifiedBase` subclass in its constructor, not hardcoded to one
  resource. Translates `FilterClause`/`SortClause` into SQLAlchemy Core
  `where()`/`order_by()` terms via its private `_where_clauses`/
  `_order_by` helpers.
- `memory.py` — `InMemoryRepository[ModelT]`, a dict-backed implementation
  used when `MODE=mock` (see `app.crud_1.heroes.get_hero_crud`) so the
  app needs no database to boot. Matches `sqlalchemy.py`'s shape, but also
  sets `created_at`/`updated_at` itself since there's no server to supply
  them via `server_default`/`onupdate` — as naive UTC datetimes, matching
  the naive `TIMESTAMP` columns Postgres stores them as, so a datetime
  filter compares correctly against either backend. Translates
  `FilterClause`/`SortClause` into plain Python predicates/`sorted()`
  instead.

## Record-lifecycle mixins

`get`/`list`/`count` accept `include_archived`/`include_unpublished` (both
default `False`); `SQLAlchemyRepository`/`InMemoryRepository` detect a
bound model's `../models/README.md`'s `mixins.py` mixins via `hasattr`
(the same pattern already used for `created_at`/`updated_at`) and, when
present:

- `Archivable`: `delete`/`delete_many` set `archived_at` instead of
  issuing a real delete (and, for a single `delete`/`update`, treat an
  already-archived row as not found — `False`/`None` — same as one that
  never existed); `restore`/`restore_many` clear it back to `None`;
  `list`/`get`/`count` exclude a row with `archived_at` set unless
  `include_archived=True`. `update_many`/`delete_many` apply this same
  archived-exclusion by default too — a bulk action's filters shouldn't
  silently reach a record a normal read can't see.
- `Schedulable`: `list`/`get`/`count` exclude a row outside its
  `publish_at`/`unpublish_at` window (computed from `datetime.now(UTC)`
  at query time, never a stored boolean) unless `include_unpublished=True`.
  Unlike `Archivable`, `update_many`/`delete_many` do *not* apply this
  exclusion — a not-yet-or-no-longer-published row isn't deleted, just not
  currently visible, and an editor must still be able to correct a
  scheduled record (single `update`/`delete` also stay reachable, for the
  same reason) before it goes live.
- `Lockable`: see `base.py`'s `RecordLockedError`, above.

A model without a given mixin is completely unaffected by all of the
above — no behavior change for a resource that doesn't opt in.

## Do

- Add a new concrete `Repository` implementation here (e.g. for a
  non-SQLAlchemy store) as its own module, matching `sqlalchemy.py`'s
  shape: one class, generic over `ModelT`, taking whatever connection/
  client it needs plus the model/collection type in its constructor.
  Detect record-lifecycle mixins the same `hasattr` way `sqlalchemy.py`/
  `memory.py` already do, rather than requiring every mixin to be
  present.

## Don't

- Import from `app.interfaces`, `app.health`, or `app.controllers` — see
  `../README.md`'s "Layering" section. `app.models` is fine
  (`SQLAlchemyRepository` is generic over `IdentifiedBase`).
- Give `SQLAlchemyRepository` resource-specific logic — anything a
  particular resource needs belongs in `app.interfaces` or the controller
  calling it, not here.
