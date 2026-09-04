# app/repositories/

Storage-agnostic CRUD access that `app.crud`'s generic interface talks
to, parameterized by a model type rather than one class per resource.

- `base.py` — `Repository[ModelT]`, the `Protocol` `app.crud.base.
  CRUDInterface` is written against: `get`/`list`/`create`/`update`/
  `delete`, all storage-agnostic.
- `sqlalchemy.py` — `SQLAlchemyRepository[ModelT]`, the default concrete
  implementation: bound to an `AsyncSession` and an `app.models.base.
  IdentifiedBase` subclass in its constructor, not hardcoded to one
  resource.
- `memory.py` — `InMemoryRepository[ModelT]`, a dict-backed implementation
  used when `MODE=mock` (see `app.controllers.heroes.get_hero_crud`) so the
  app needs no database to boot. Matches `sqlalchemy.py`'s shape, but also
  sets `created_at`/`updated_at` itself since there's no server to supply
  them via `server_default`/`onupdate`.

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
