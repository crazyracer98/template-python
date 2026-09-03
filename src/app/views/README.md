# app/views/

The View layer: Pydantic schemas returned by and accepted from
`app.controllers`' routes.

- `base.py` — `ORMView`, the base every view inherits from
  (`model_config = ConfigDict(from_attributes=True)`, which is what lets
  `app.crud.base.CRUDInterface` build one straight from a SQLAlchemy
  model instance via `model_validate`).
- `hero.py` — the example Hero views; see `../README.md`'s "Example CRUD
  resource: Hero".

## Do

- Subclass `ORMView`, not `pydantic.BaseModel` directly, for any view
  `app.crud.base.CRUDInterface` will build from an ORM instance.
- Give a resource three views following `hero.py`'s shape: `*Create`
  (fields accepted on create), `*Update` (the same fields, all
  `| None = None`, for partial updates), and the plain name (the full
  read view, with `id`).

## Don't

- Import from `app.models`, `app.repositories`, `app.crud`,
  `app.health`, or `app.controllers` — see the root `CLAUDE.md`'s
  "src/app/ layering" section. A view converts to/from an ORM instance
  structurally (`from_attributes`), never by importing the model class.
