# app/interfaces/

The generic CRUD interface: feed it a view (`app.views`) and a
repository (`app.repositories`) to persist it through, and it exposes
`get`/`list`/`create`/`update`/`delete`/`count`/`update_many`/
`delete_many` in terms of that view — a new resource never needs its own
CRUD class, only a model, a view, and a router that wires the two through
`CRUDInterface`.

- `base.py` — `CRUDInterface[SchemaT, ModelT]`, and the `CRUDLike[SchemaT]`
  `Protocol` describing its full method shape. `CRUDInterface` converts to/
  from the backing ORM model entirely via the view's own `from_attributes`
  support (see `app.views.base.ORMView`) — this module has no
  resource-specific code and imports nothing from `app.views` or
  `app.repositories` beyond their base types. `list`/`update_many`/
  `delete_many`/`count` take `filters`/`sort` sequences from
  `app.repositories.filtering`, passed straight through to the repository —
  see `app.controllers.crud_query` for where those come from on an actual
  request. `CompatCRUD` (below) satisfies `CRUDLike` too, structurally —
  `../controllers/crud_router.py`'s router factories are written against
  `CRUDLike` rather than concretely against `CRUDInterface`, specifically so
  the same factory builds both a current-version router and a deprecated
  one. `base.py` also has `OwnerScope`, an opt-in per-user/per-tenant
  scoping hook: pass `CRUDInterface(..., owner=OwnerScope(field, value))` and
  `update`/`delete`/`update_many`/`delete_many` are restricted to records
  where `field == value`, `create` stamps `field` with `value` rather than
  trusting it from the input view, and `get`/`list`/`count` are restricted
  too *unless* `read_scoped=False` is also passed, in which case every
  caller reads every record but can still only write their own.
  `owner=None` (the default) changes nothing — a resource that never passes
  it is unaffected. Resolve `value` from the caller's claims (typically
  `claims["sub"]`) the same way `get_hero_crud` resolves its repository: as
  a `Depends(get_current_claims)` parameter of the resource's own
  `get_<resource>_crud`, not a new mechanism — see `app.crud_1.heroes.
  heroes_v2.get_hero_crud` for the worked example (Hero uses
  `read_scoped=False`: every caller reads every hero, same as before this
  was added, but can only update/delete their own),
  `docs/adrs/0011-owner-scoped-crud-example-resource.md` for the full
  rationale, and `tests/unit/interfaces/test_base.py`'s `test_owner_*`/
  `test_read_scoped_*` tests for the scoped, unscoped, and open-read paths.
- `compat.py` — `CompatCRUD`, a generic wrapper that adapts a current
  `CRUDInterface` to speak in terms of an older (deprecated) API
  version's view, via caller-supplied converter functions. The building
  block for a resource that's grown a deprecated version — see
  `../controllers/README.md`'s "API and model versioning" and
  `docs/adrs/0002-api-and-model-versioning.md`.
- `dependency.py` — `build_repository_provider(model)`, the one genuinely
  duplicated fragment of a resource's `get_<resource>_crud`: choosing an
  `InMemoryRepository` (MODE=mock, built once and shared across requests)
  vs. a request-scoped `SQLAlchemyRepository`. Returns a
  `Callable[[AsyncSession], Repository[ModelT]]` a controller calls with
  its request's session — see `app.crud_1.heroes` for the pattern.
  The route-level factories built on top of `CRUDInterface`/`CompatCRUD`
  (`build_json_router`/`build_xml_router`/`build_web_router`) live in
  `../controllers/crud_router.py`, one layer up — see `../controllers/
  README.md`'s "Generic CRUD router factories".

## Do

- Build one `CRUDInterface` per request, in the controller, from the
  concrete view and `build_repository_provider(Model)(session)` — see
  `app.crud_1.heroes.get_hero_crud` for the pattern.

## Don't

- Import from `app.health` or `app.controllers` — see `../README.md`'s
  "Layering" section.
- Add a resource-specific method to `CRUDInterface` — if a resource
  needs behavior beyond the five generic operations, add it in that
  resource's controller instead, calling `CRUDInterface`/the repository
  it wraps directly.
