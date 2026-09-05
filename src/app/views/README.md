# app/views/

The View layer: Pydantic schemas returned by and accepted from
`app.controllers`' routes.

- `base.py` — `ORMView`, the base every view inherits from
  (`model_config = ConfigDict(from_attributes=True)`, which is what lets
  `app.interfaces.base.CRUDInterface` build one straight from a SQLAlchemy
  model instance via `model_validate`), and `IXDTFDatetime` (see below).
- `hero_v2.py` — the current (v2) Hero views; see `../README.md`'s
  "Example CRUD resource: Hero".
- `hero_v1.py` — the deprecated `/crud/v1/heroes/v1` shape and its
  converter functions to/from `hero_v2.py`'s current shape; see the
  `*_vN.py` pattern below.
- `bulk.py` — `BulkUpdateResult`/`BulkDeleteResult`, the response shape
  for a bulk update/delete action (matched count plus the ids affected).
  Plain `BaseModel` subclasses, not `ORMView`: they wrap an already-
  validated result the controller assembles itself, not a raw ORM
  instance `CRUDInterface` builds one of via `from_attributes`.

## IXDTF timestamps

`base.py`'s `IXDTFDatetime` (a `datetime` `Annotated` type) serializes
as an RFC 9557 IXDTF string (`...Z[UTC]` — every stored timestamp is
UTC, see `app.models.base.IdentifiedBase`'s `created_at`/`updated_at`);
use it on any read view field carrying a timestamp. See
`../README.md`'s "Sunset/Deprecation headers" for the related, but
HTTP-date-formatted, `Sunset` header.

## Do

- Subclass `ORMView`, not `pydantic.BaseModel` directly, for any view
  `app.interfaces.base.CRUDInterface` will build from an ORM instance.
- Give a resource three views following `hero_v2.py`'s shape: `*Create`
  (fields accepted on create), `*Update` (the same fields, all
  `| None = None`, for partial updates), and the plain name (the full
  read view, with `id`).
- For a deprecated API version, add a `*_vN.py` module following
  `hero_v1.py`'s shape: that version's own `*Base`/`*Create`/`*Update`/
  plain-name views, plus pure converter functions to/from the current
  version's views (no I/O — see `../controllers/README.md`'s "API and
  model versioning"). A deprecated version's converters go in `views/`,
  not `crud/`, so they stay trivially unit-testable in isolation from
  the HTTP layer.

## Don't

- Import from `app.models`, `app.repositories`, `app.interfaces`,
  `app.health`, or `app.controllers` — see `../README.md`'s "Layering"
  section. A view converts to/from an ORM instance structurally
  (`from_attributes`), never by importing the model class.
