# app/crud/

The generic CRUD interface: feed it a view (`app.views`) and a
repository (`app.repositories`) to persist it through, and it exposes
`get`/`list`/`create`/`update`/`delete` in terms of that view — a new
resource never needs its own CRUD class, only a model, a view, and a
router that wires the two through `CRUDInterface`.

- `base.py` — `CRUDInterface[SchemaT, ModelT]`. Converts to/from the
  backing ORM model entirely via the view's own `from_attributes`
  support (see `app.views.base.ORMView`) — this module has no
  resource-specific code and imports nothing from `app.views` or
  `app.repositories` beyond their base types.

## Do

- Build one per request, in the controller, from the concrete view and
  a `SQLAlchemyRepository` bound to that request's session — see
  `app.controllers.heroes.get_hero_crud` for the pattern.

## Don't

- Import from `app.health` or `app.controllers` — see `../README.md`'s
  "Layering" section.
- Add a resource-specific method to `CRUDInterface` — if a resource
  needs behavior beyond the five generic operations, add it in that
  resource's controller instead, calling `CRUDInterface`/the repository
  it wraps directly.
