# app/repositories/

Storage-agnostic CRUD access that `app.crud`'s generic interface talks
to, parameterized by a model type rather than one class per resource.

- `base.py` — `Repository[ModelT]`, the `Protocol` `app.crud.base.
  CRUDInterface` is written against: `get`/`list`/`create`/`update`/
  `delete`/`count`/`update_many`/`delete_many`, all storage-agnostic.
  `list`/`update_many`/`delete_many` take `filters`/`sort` sequences from
  `filtering.py`.
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
  used when `MODE=mock` (see `app.controllers.heroes.get_hero_crud`) so the
  app needs no database to boot. Matches `sqlalchemy.py`'s shape, but also
  sets `created_at`/`updated_at` itself since there's no server to supply
  them via `server_default`/`onupdate` — as naive UTC datetimes, matching
  the naive `TIMESTAMP` columns Postgres stores them as, so a datetime
  filter compares correctly against either backend. Translates
  `FilterClause`/`SortClause` into plain Python predicates/`sorted()`
  instead.

## Do

- Add a new concrete `Repository` implementation here (e.g. for a
  non-SQLAlchemy store) as its own module, matching `sqlalchemy.py`'s
  shape: one class, generic over `ModelT`, taking whatever connection/
  client it needs plus the model/collection type in its constructor.

## Don't

- Import from `app.crud`, `app.health`, or `app.controllers` — see
  `../README.md`'s "Layering" section. `app.models` is fine
  (`SQLAlchemyRepository` is generic over `IdentifiedBase`).
- Give `SQLAlchemyRepository` resource-specific logic — anything a
  particular resource needs belongs in `app.crud` or the controller
  calling it, not here.
