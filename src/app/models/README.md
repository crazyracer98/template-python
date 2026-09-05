# app/models/

The Model layer: SQLAlchemy ORM. Lowest layer in `src/app/`'s import
order besides `config`/`oidc` — never imports from any other `app/`
subpackage.

- `base.py` — `Base` (the declarative base every model inherits from),
  `IdentifiedBase` (adds the single-column integer `id` primary key
  `app.repositories`/`app.interfaces`'s generics are bound to), the async
  `engine`/`async_session_factory`, `get_db` (the FastAPI dependency
  that yields a request-scoped `AsyncSession`, committed on success), and
  `DBSession` (the `Annotated` alias that depends on it at
  `scope="function"`). Depend on `DBSession`, never on `Depends(get_db)`
  directly: at `Depends()`'s default `scope="request"` the commit runs
  after the response is sent, so a client acting on a write's own
  response can fail to see its own write — see the comment on the alias.
- `hero.py` — the example `Hero` model; see `../README.md`'s "Example
  CRUD resource: Hero".
- `mixins.py` — opt-in record-lifecycle mixins (`Archivable`/`Draftable`/
  `Schedulable`/`Lockable`), each adding one plain column; a model opts in
  with plain multiple inheritance (`class Hero(IdentifiedBase, Archivable,
  ...)`). See `../repositories/README.md` for how `SQLAlchemyRepository`/
  `InMemoryRepository` detect and act on these, and
  `docs/adrs/0012-soft-delete-via-marker-column.md` for why `Archivable`
  reuses the same row/table rather than a second archive table.
- `revision.py` — `Revision`, the one shared (not per-resource) table
  backing revision history; see `../interfaces/README.md`'s
  `RevisionSink` paragraph.

## Do

- Subclass `IdentifiedBase`, not `Base` directly, unless a model
  genuinely doesn't have a single-column integer `id` primary key.
- Add a migration after adding or changing a model: `uv run alembic
  revision --autogenerate -m "..."` — see `../../../alembic/README.md`.

## Don't

- Import from `app.views`, `app.repositories`, `app.interfaces`,
  `app.health`, or `app.controllers` — see `../README.md`'s "Layering"
  section.
