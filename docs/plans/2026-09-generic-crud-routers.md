# Genericize the Hero JSON/XML/web-component/version controllers into router factories

## Status

Draft

## Goal

`app/controllers/heroes.py`, `heroes_xml.py`, `heroes_web.py`,
`heroes_v1.py`, `heroes_v1_xml.py`, `heroes_v1_web.py` each hand-write
the same shape of route (list/create/get/update/delete, or
form/components.js) against `CRUDInterface`/`CompatCRUD` — ~13
near-identical route functions per resource, doubled again for every
deprecated version. `app.crud.base.CRUDInterface`,
`app.crud.compat.CompatCRUD`, `app.xml_codec`, and `app.web_components`
are already generic (parameterized by view/model, not by "Hero"
specifically); the router wiring itself is the one piece still
hand-copied. This plan factors that wiring into three reusable router
factories — `build_json_router`/`build_xml_router`/`build_web_router` —
taking a resource's Pydantic views and an already-built CRUD dependency
as input, so Hero's six controller modules shrink to declarative
one-call wiring, and the *next* resource (or the *next* deprecated
version of Hero) costs a views module + a handful of factory-call
arguments, never new route functions.

## Approach

### Design decision: fully dynamic factories

Confirmed with the repo owner: the factories generate their route
functions internally (closures over `schema`/`create_schema`/
`update_schema`/`crud_dependency` etc.), rather than each resource
still hand-declaring thin per-route functions that call into shared
helpers. This means each generated route's `crud`/`record` parameter is
annotated with a `TypeVar`-bound runtime value (e.g. `create_schema`,
a `type[CreateT]` parameter of the enclosing factory) — mypy cannot
resolve that statically, so each such line needs a narrowly-scoped
`# type: ignore[valid-type]` with a one-line comment explaining why.
The factories' own public signatures (every parameter, and `-> APIRouter`)
stay fully strict-typed via PEP 695 generics, so a caller like
`heroes.py` gets normal type-checking on its `build_json_router(...)`
call — only the ~12 internal nested-function annotations are ignored,
which is the "narrow, justified" carve-out `README.md`'s "Checks"
section allows. Confirm during implementation that this is in fact the
only source of strict-mode fallout (see "Open questions").

The per-request CRUD *dependency* builder (`get_hero_crud`/`HeroCRUD`)
is deliberately **not** folded into the same dynamic machinery: `HeroCRUD`
must stay a literal module-level `Annotated[CRUDInterface[Hero, HeroModel],
Depends(get_hero_crud)]` assignment, because `heroes_v1.py`'s
`get_hero_v1_crud(crud: HeroCRUD) -> CompatCRUD[...]` uses it as a real,
statically-checked parameter annotation — mypy only recognizes a
directly-assigned `Annotated[...]` expression as an implicit type alias,
not one returned from a generic function call. Only the mock-vs-SQLAlchemy
repository selection inside it is worth factoring out (see below); the
4-line `get_hero_crud`/`HeroCRUD` declaration stays per-resource, same as
today.

### 1. `CRUDLike` protocol — `app/crud/base.py`

Add alongside `CRUDInterface`, so the router factories can depend on
"anything with these five async methods" rather than concretely on
`CRUDInterface` — `CompatCRUD` (used by every deprecated version)
already has this exact shape, and this is what lets the *same* three
factories build both the current and deprecated routers:

```python
from typing import Protocol


class CRUDLike[SchemaT: BaseModel](Protocol):
    """Structural shape both CRUDInterface and CompatCRUD satisfy."""

    async def get(self, record_id: int) -> SchemaT | None: ...
    async def list(self, *, skip: int = 0, limit: int = 100) -> list[SchemaT]: ...
    async def create(self, data: BaseModel) -> SchemaT: ...
    async def update(self, record_id: int, data: BaseModel) -> SchemaT | None: ...
    async def delete(self, record_id: int) -> bool: ...
```

### 2. `build_repository_provider` — `app/crud/dependency.py`

New module, same `crud` import-linter layer (imports only
`repositories`/`models`/`config`, all already-lower layers). Factors
out the one genuinely-duplicated fragment of `get_hero_crud`: choosing
an `InMemoryRepository` (MODE=mock, built once at import time and
shared across requests) vs. a request-scoped `SQLAlchemyRepository`:

```python
"""Generic MODE-aware Repository selection, shared by every resource's CRUD dependency."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.base import IdentifiedBase
from app.repositories.base import Repository
from app.repositories.memory import InMemoryRepository
from app.repositories.sqlalchemy import SQLAlchemyRepository

settings = get_settings()


def build_repository_provider[ModelT: IdentifiedBase](
    model: type[ModelT],
) -> Callable[[AsyncSession], Repository[ModelT]]:
    """Return a per-request Repository[ModelT] provider: shared in-memory under
    MODE=mock, a fresh SQLAlchemyRepository bound to the request's session otherwise.
    """
    mock_repository: Repository[ModelT] = InMemoryRepository(model)

    def provider(session: AsyncSession) -> Repository[ModelT]:
        return mock_repository if settings.mode == "mock" else SQLAlchemyRepository(session, model)

    return provider
```

`heroes.py` then becomes:

```python
_hero_repository = build_repository_provider(HeroModel)


def get_hero_crud(session: Annotated[AsyncSession, Depends(get_db)]) -> CRUDInterface[Hero, HeroModel]:
    return CRUDInterface(schema=Hero, repository=_hero_repository(session))


HeroCRUD = Annotated[CRUDInterface[Hero, HeroModel], Depends(get_hero_crud)]
```

### 3. `is_list_annotation` — export from `app/xml_codec.py`

Rename the existing `_is_list_annotation` to public `is_list_annotation`
(same body). `build_web_router` (below) reuses it to derive which of a
create schema's fields are lists, instead of each resource passing a
separate `list_fields` tuple that has to be kept in sync by hand.

### 4. `app/controllers/crud_router.py` — the three factories

New module in the `controllers` layer (imports `crud.base.CRUDLike`,
`xml_codec`, `web_components` — all already-lower layers, same
direction `heroes_xml.py`/`heroes_web.py` import today; no new
import-linter layer entries needed).

```python
"""Generic FastAPI router factories for a resource's CRUD endpoints.

Parameterized by a resource's Pydantic views and an already-built CRUD
dependency (app.crud.base.CRUDLike) -- covers both a current version
(CRUDInterface) and a deprecated one (CompatCRUD) identically, since
both satisfy CRUDLike structurally. Each factory builds its route
functions internally as closures over its arguments: the generated
functions' `crud`/`record` parameters are annotated with a TypeVar-bound
runtime type, which mypy cannot verify statically -- each such line
carries a narrow `# type: ignore[valid-type]`. This factory's own
signature (every parameter, `-> APIRouter`) stays fully strict-typed,
so a caller gets real type-checking on the call itself.
"""

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from app.web_components import render_crud_component_js, render_crud_form
from app.xml_codec import from_xml, is_list_annotation, to_xml


def build_json_router[SchemaT: BaseModel, CreateT: BaseModel, UpdateT: BaseModel](
    *,
    prefix: str,
    tags: Sequence[str],
    resource_label: str,
    schema: type[SchemaT],
    create_schema: type[CreateT],
    update_schema: type[UpdateT],
    crud_dependency: Any,  # Annotated[CRUDLike[SchemaT], Depends(...)]
    read_roles: Any,       # a Depends(...) object, e.g. heroes.ReadRoles
    write_roles: Any,
    delete_roles: Any,
    router_dependencies: Sequence[Any] = (),
) -> APIRouter:
    """Build the standard list/create/get/update/delete JSON router for one resource."""
    router = APIRouter(prefix=prefix, tags=list(tags), dependencies=list(router_dependencies))
    not_found = f"{resource_label} not found"

    @router.get("", dependencies=[read_roles])
    async def list_records(crud: crud_dependency, skip: int = 0, limit: int = 100) -> list[schema]:  # type: ignore[valid-type]
        return await crud.list(skip=skip, limit=limit)

    @router.post("", status_code=status.HTTP_201_CREATED, dependencies=[write_roles])
    async def create_record(record: create_schema, crud: crud_dependency) -> schema:  # type: ignore[valid-type]
        return await crud.create(record)

    @router.get("/{record_id:int}", dependencies=[read_roles])
    async def get_record(record_id: int, crud: crud_dependency) -> schema:  # type: ignore[valid-type]
        record = await crud.get(record_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)
        return record

    @router.patch("/{record_id:int}", dependencies=[write_roles])
    async def update_record(record_id: int, record: update_schema, crud: crud_dependency) -> schema:  # type: ignore[valid-type]
        updated = await crud.update(record_id, record)
        if updated is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)
        return updated

    @router.delete("/{record_id:int}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[delete_roles])
    async def delete_record(record_id: int, crud: crud_dependency) -> None:  # type: ignore[valid-type]
        if not await crud.delete(record_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)

    return router


def build_xml_router[SchemaT: BaseModel, CreateT: BaseModel, UpdateT: BaseModel](
    *,
    prefix: str,
    tags: Sequence[str],
    resource_label: str,
    item_tag: str,
    list_tag: str,
    create_schema: type[CreateT],
    update_schema: type[UpdateT],
    crud_dependency: Any,
    read_roles: Any,
    write_roles: Any,
    delete_roles: Any,
    router_dependencies: Sequence[Any] = (),
) -> APIRouter:
    """Build the XML-flavored sibling of build_json_router's five routes."""
    router = APIRouter(prefix=prefix, tags=list(tags), dependencies=list(router_dependencies))
    not_found = f"{resource_label} not found"
    xml_media_type = "application/xml"

    @router.get("", dependencies=[read_roles])
    async def list_records_xml(crud: crud_dependency, skip: int = 0, limit: int = 100) -> Response:  # type: ignore[valid-type]
        records = await crud.list(skip=skip, limit=limit)
        body = f"<{list_tag}>" + "".join(to_xml(r, item_tag) for r in records) + f"</{list_tag}>"
        return Response(content=body, media_type=xml_media_type)

    @router.post("", status_code=status.HTTP_201_CREATED, dependencies=[write_roles])
    async def create_record_xml(crud: crud_dependency, request: Request) -> Response:  # type: ignore[valid-type]
        record = from_xml(await request.body(), create_schema)
        created = await crud.create(record)
        return Response(
            content=to_xml(created, item_tag), media_type=xml_media_type, status_code=status.HTTP_201_CREATED
        )

    @router.get("/{record_id:int}", dependencies=[read_roles])
    async def get_record_xml(record_id: int, crud: crud_dependency) -> Response:  # type: ignore[valid-type]
        record = await crud.get(record_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)
        return Response(content=to_xml(record, item_tag), media_type=xml_media_type)

    @router.patch("/{record_id:int}", dependencies=[write_roles])
    async def update_record_xml(record_id: int, crud: crud_dependency, request: Request) -> Response:  # type: ignore[valid-type]
        record = from_xml(await request.body(), update_schema)
        updated = await crud.update(record_id, record)
        if updated is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)
        return Response(content=to_xml(updated, item_tag), media_type=xml_media_type)

    @router.delete("/{record_id:int}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[delete_roles])
    async def delete_record_xml(record_id: int, crud: crud_dependency) -> None:  # type: ignore[valid-type]
        if not await crud.delete(record_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, not_found)

    return router


def build_web_router[CreateT: BaseModel](
    *,
    prefix: str,
    tags: Sequence[str],
    resource: str,
    api_base: str,
    fields: Sequence[str],
    create_schema: type[CreateT],
    crud_dependency: Any,
    read_roles: Any,
    write_roles: Any,
    router_dependencies: Sequence[Any] = (),
) -> APIRouter:
    """Build the zero-JS-form + web-component-JS sibling router for one resource.

    `list_fields` (which of `fields` are arrays, for comma-split parsing and
    ", "-joined display) is derived from `create_schema`'s own annotations via
    `is_list_annotation`, rather than passed separately -- one less value for a
    caller to keep in sync with its own view module.
    """
    router = APIRouter(prefix=prefix, tags=list(tags), dependencies=list(router_dependencies))
    list_fields = tuple(
        f for f in fields if is_list_annotation(create_schema.model_fields[f].annotation)
    )

    @router.get("/form", dependencies=[read_roles])
    async def form_page() -> Response:
        return Response(content=render_crud_form(resource, fields, api_base), media_type="text/html")

    @router.post("/form", status_code=status.HTTP_303_SEE_OTHER, dependencies=[write_roles])
    async def submit_form(request: Request, crud: crud_dependency) -> RedirectResponse:  # type: ignore[valid-type]
        form = await request.form()
        data: dict[str, str | list[str]] = {}
        for field in fields:
            raw = str(form.get(field, ""))
            data[field] = (
                [v.strip() for v in raw.split(",") if v.strip()] if field in list_fields else raw
            )
        await crud.create(create_schema.model_validate(data))
        return RedirectResponse(f"{api_base}/form", status_code=status.HTTP_303_SEE_OTHER)

    @router.get("/components.js")
    async def components_js() -> Response:
        return Response(
            content=render_crud_component_js(resource, api_base, fields, list_fields=list_fields),
            media_type="application/javascript",
        )

    return router
```

Note the web form's create route trades away FastAPI's typed-`Form()`
per-field OpenAPI documentation (today's `submit_hero_form` declares
`name: Annotated[str, Form()]` etc., so Swagger shows real form-field
docs) for generic `Request.form()` parsing — Swagger UI will show this
route with an undocumented body instead. This is a deliberate,
necessary trade-off of genericizing the endpoint (see "Open questions"
— flag for confirmation, since it's a real, visible behavior change,
not just an internal refactor).

### 5. Rewrite `heroes.py` / `heroes_xml.py` / `heroes_web.py`

`heroes.py` keeps `get_hero_crud`/`HeroCRUD`/`ReadRoles`/`WriteRoles`/
`DeleteRoles` exactly as today (module-level names other modules and
tests import/override), but the five hand-written routes are replaced
by one call:

```python
router = build_json_router(
    prefix="/heroes",
    tags=["heroes"],
    resource_label="Hero",
    schema=Hero,
    create_schema=HeroCreate,
    update_schema=HeroUpdate,
    crud_dependency=HeroCRUD,
    read_roles=ReadRoles,
    write_roles=WriteRoles,
    delete_roles=DeleteRoles,
)
```

`heroes_xml.py` and `heroes_web.py` shrink the same way, importing
`HeroCRUD`/`ReadRoles`/`WriteRoles`/`DeleteRoles` from `heroes.py`
exactly as they do today (unchanged import lines), replacing their
route bodies with one `build_xml_router(...)` / `build_web_router(...)`
call each (`item_tag="hero"`, `list_tag="heroes"`,
`fields=("name", "powers")`, `api_base="/v2/heroes"`). `main.py` is
untouched — it still does `app.include_router(heroes.router, prefix="/v2")`
etc. against the same module-level `.router` names.

### 6. Rewrite `heroes_v1.py` / `heroes_v1_xml.py` / `heroes_v1_web.py`

Same treatment. `heroes_v1.py` keeps its bespoke
`get_hero_v1_crud(crud: HeroCRUD) -> CompatCRUD[...]` / `HeroV1CRUD`
(the version-compatibility wiring is genuinely per-version, not
boilerplate `build_json_router` should own) and the `sunset(...)`
router dependency, then calls `build_json_router(..., crud_dependency=HeroV1CRUD,
router_dependencies=[Depends(sunset(_SUNSET_AT, link="/v2/heroes"))])`.
`heroes_v1_xml.py`/`heroes_v1_web.py` mirror `heroes_xml.py`/
`heroes_web.py` exactly, importing from `heroes_v1` instead of `heroes`,
with `fields=("name", "superpower")`, `api_base="/v1/heroes"`.

**Existing gap to preserve, not silently fix**: today only
`heroes_v1.py` (JSON) applies `sunset(...)` as a router dependency —
`heroes_v1_xml.py`/`heroes_v1_web.py` don't, so their responses lack
`Sunset`/`Deprecation`/`Link` headers unlike the JSON v1 routes. The
factories should reproduce this bug-for-bug by default (pass
`router_dependencies=[Depends(sunset(...))]` only where the current
code does, i.e. nowhere for xml/web) — see "Open questions" for whether
to fix this gap as part of this plan or file it separately.

### Tests

- New `tests/unit/controllers/test_crud_router.py`: exercise
  `build_json_router`/`build_xml_router`/`build_web_router` directly
  against a minimal fake schema/model pair (not Hero-specific — mirrors
  how `tests/unit/crud/test_compat.py` tests `CompatCRUD` generically),
  covering the list/create/get/update/delete lifecycle, 404 handling,
  and (for the web router) list-field comma-splitting.
- `tests/unit/controllers/test_heroes*.py`,
  `tests/integration/controllers/test_heroes.py`,
  `tests/e2e/test_heroes*_e2e.py`: no path or behavior changes expected
  (same routes, same request/response shapes) — rerun as regression
  checks; update only if the `Form()`-docs trade-off (above) or the
  `hero_id` → `record_id` path-param rename (cosmetic, OpenAPI-only —
  see "Open questions") turns out to break an assertion.
- `tests/unit/crud/test_dependency.py`: `build_repository_provider`
  returns the shared in-memory instance under MODE=mock and a fresh
  `SQLAlchemyRepository` per call otherwise.

### Docs

- `src/app/controllers/README.md`: rewrite "Multi-format CRUD" and "API
  and model versioning" to describe the three factories in
  `crud_router.py` as the mechanism (replacing "reuse the JSON router's
  dependency directly" with "call `build_xml_router`/`build_web_router`
  with the same dependency"); update "Do" to say a new resource calls
  the factories rather than hand-writing routes.
- `src/app/crud/README.md`: document `CRUDLike`, `build_repository_provider`,
  and note `crud_router.py` (in `controllers/`) as where the route-level
  factories built on top of them live.
- `src/app/views/README.md`: no change expected (views layer is
  untouched by this plan).

### Import-linter

No new layer entries: `crud/dependency.py` stays in the `crud` layer,
`controllers/crud_router.py` stays in the `controllers` layer. Run
`uv run lint-imports` to confirm.

## Open questions

- **Web form OpenAPI docs**: confirm the loss of per-field `Form()`
  documentation on `POST /heroes/form` (and `/v1/heroes/form`) in
  Swagger UI is acceptable, or whether `build_web_router` should attach
  hand-written `openapi_extra` describing `fields` to compensate.
- **`hero_id` → `record_id` path param rename**: `build_json_router`/
  `build_xml_router` use a uniform `/{record_id:int}` rather than each
  resource's own `/{hero_id:int}`. Purely cosmetic (visible only in
  generated OpenAPI docs/Swagger UI, not in the URL itself), but
  confirm that's fine before implementing.
- **v1 xml/web sunset-header gap**: fix it (add `sunset(...)` to
  `heroes_v1_xml.py`/`heroes_v1_web.py` too) as part of this plan, or
  leave the bug-for-bug behavior and file it separately?
- **mypy --strict fallout**: confirm during implementation that the
  `# type: ignore[valid-type]` comments sketched above are sufficient —
  it's possible FastAPI's own `Depends`/response-model handling surfaces
  additional strict-mode complaints once these functions are built
  dynamically (e.g. around `response_model` inference); if so, decide
  whether to pass `response_model=schema` explicitly on each route
  decorator rather than relying on return-annotation inference.

## Verification

Run and show actual output for:
```
uv run ruff check
uv run ruff format --check
uv run mypy --strict
uv run lint-imports
uv run pytest
uv run pytest tests/e2e
```
Manual smoke check (curl or Swagger UI):
- `/v2/heroes`, `/v2/heroes/xml`, `/v2/heroes/form` behave identically
  to before the refactor (full CRUD lifecycle, 404s, XML round-trip,
  form submission with a comma-separated `powers` field).
- `/v1/heroes*` unchanged: still sunset-headers-on-JSON-only (per the
  gap above), still converts `superpower` <-> `powers[0]` correctly.
- Swagger UI (`/docs`) renders both version groups with sane-looking
  operation IDs/parameter names (check the `record_id` rename doesn't
  produce anything confusing).
