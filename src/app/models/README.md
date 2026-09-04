# app/models/

The Model layer: SQLAlchemy ORM. Lowest layer in `src/app/`'s import
order besides `config`/`oidc` — never imports from any other `app/`
subpackage.

- `base.py` — `Base` (the declarative base every model inherits from),
  `IdentifiedBase` (adds the single-column integer `id` primary key
  `app.repositories`/`app.crud`'s generics are bound to), the async
  `engine`/`async_session_factory`, `get_db` (the FastAPI dependency
  that yields a request-scoped `AsyncSession`, committed on success), and
  `DBSession` (the `Annotated` alias that depends on it at
  `scope="function"`). Depend on `DBSession`, never on `Depends(get_db)`
  directly: at `Depends()`'s default `scope="request"` the commit runs
  after the response is sent, so a client acting on a write's own
  response can fail to see its own write — see the comment on the alias.
- `hero.py` — the example `Hero` model; see `../README.md`'s "Example
  CRUD resource: Hero".

## Do

- Subclass `IdentifiedBase`, not `Base` directly, unless a model
  genuinely doesn't have a single-column integer `id` primary key.
- Add a migration after adding or changing a model: `uv run alembic
  revision --autogenerate -m "..."` — see `../../../alembic/README.md`.

## Don't

- Import from `app.views`, `app.repositories`, `app.crud`,
  `app.health`, or `app.controllers` — see `../README.md`'s "Layering"
  section.
