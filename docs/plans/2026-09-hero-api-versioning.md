# Path-prefixed API/model versioning for Hero (`/v1` deprecated, `/v2` current)

## Status

Draft

## Goal

Introduce path-prefixed `/v1/heroes*` (deprecated) and `/v2/heroes*`
(current) for the Hero resource, backed by a new generic
backward-compatibility CRUD wrapper (`CompatCRUD`) so `/v1` stays backed by
the *same* repository/data as `/v2` instead of duplicating persistence.
This establishes the repo-wide versioning convention — recorded in
`CLAUDE.md` and an ADR — that future resources copy: a `*_vN.py` views
module + converter functions, a `CompatCRUD`-wrapped sibling controller
set, and a router-level `sunset()` dependency.

## Depends on

`2026-09-hero-v2-powers-field.md` must already be merged — this plan wraps
that plan's `powers: list[str]` shape as the "v2"/current version, and its
`/v1` compatibility layer converts back down to the pre-that-plan single
`superpower: str` shape. Do not start this plan until that one's
verification steps are green.

## Approach

### Versioning scheme

- `/v2/heroes`, `/v2/heroes/xml`, `/v2/heroes/form`,
  `/v2/heroes/components.js` — the current shape (`powers: list[str]`).
  `heroes.py`/`heroes_xml.py`/`heroes_web.py` themselves are unchanged by
  *this* plan (already updated by the prior plan); only their *mount* in
  `main.py` gains `prefix="/v2"`.
- `/v1/heroes*` — new sibling routers, deprecated, backed by the same
  `HeroCRUD` dependency from `heroes.py`, wrapped in `CompatCRUD`.
- No bare unversioned `/heroes` alias — callers must pick a version
  explicitly. `/health`, `/protected`, `/audit`, `/mock/token` stay
  unprefixed: this versioning scheme applies to the Hero resource's CRUD
  endpoints only, not infrastructure endpoints.

### `crud/compat.py` — generic backward-compatibility wrapper

New module, `src/app/crud/`, same import-linter layer as `crud/base.py`
(imports only `crud.base` + pydantic — no new layer entry needed):

```python
"""Generic backward-compatibility wrapper around CRUDInterface.

Wraps a current-version CRUDInterface and exposes the same CRUD operations
in terms of an older (deprecated) view, converting responses down to the
legacy shape and incoming payloads up to the current shape via
caller-supplied converter functions -- so a deprecated API version keeps
working against the same repository/current model as the version that
superseded it, without its own duplicated CRUD wiring.
"""

from collections.abc import Callable

from pydantic import BaseModel

from app.crud.base import CRUDInterface


class CompatCRUD[LegacySchemaT: BaseModel, SchemaT: BaseModel, ModelT]:
    """CRUD operations shaped like an older API version, backed by the current CRUDInterface."""

    def __init__(
        self,
        crud: CRUDInterface[SchemaT, ModelT],
        *,
        to_legacy: Callable[[SchemaT], LegacySchemaT],
        from_legacy_create: Callable[[BaseModel], BaseModel],
        from_legacy_update: Callable[[BaseModel], BaseModel],
    ) -> None:
        """Bind this wrapper to the current CRUD it delegates to and its conversion functions."""
        self._crud = crud
        self._to_legacy = to_legacy
        self._from_legacy_create = from_legacy_create
        self._from_legacy_update = from_legacy_update

    async def get(self, record_id: int) -> LegacySchemaT | None:
        """Return the record with the given id in the legacy shape, or None."""
        current = await self._crud.get(record_id)
        return self._to_legacy(current) if current is not None else None

    async def list(self, *, skip: int = 0, limit: int = 100) -> list[LegacySchemaT]:
        """Return up to `limit` records in the legacy shape, skipping the first `skip`."""
        return [self._to_legacy(item) for item in await self._crud.list(skip=skip, limit=limit)]

    async def create(self, data: BaseModel) -> LegacySchemaT:
        """Create a record from a legacy-shaped payload and return it in the legacy shape."""
        created = await self._crud.create(self._from_legacy_create(data))
        return self._to_legacy(created)

    async def update(self, record_id: int, data: BaseModel) -> LegacySchemaT | None:
        """Apply a legacy-shaped partial update, returning the result in the legacy shape."""
        updated = await self._crud.update(record_id, self._from_legacy_update(data))
        return self._to_legacy(updated) if updated is not None else None

    async def delete(self, record_id: int) -> bool:
        """Delete the record with the given id; return whether it existed."""
        return await self._crud.delete(record_id)
```

Not Hero-specific — this is the reusable piece any future deprecated
version wraps its current `CRUDInterface` in. Add a short mention to
`src/app/crud/README.md` alongside the existing `CRUDInterface` docs.

### `views/hero_v1.py` — legacy shape + converters

New file, `src/app/views/hero_v1.py`. Shaped like Hero's *pre-versioning*
views (`superpower: str`), plus three converter functions (views-layer,
pure, no I/O; imports `views/hero.py`, an intra-layer import same as
`heroes_xml.py` importing from `heroes.py`):

```python
"""Deprecated v1 Hero view (single superpower) and its converters to/from v2."""

from pydantic import Field

from app.views.base import IXDTFDatetime, ORMView
from app.views.hero import Hero, HeroCreate, HeroUpdate


class HeroV1Base(ORMView):
    """Fields shared by every v1 Hero view."""

    name: str = Field(min_length=1, max_length=200)
    superpower: str = Field(min_length=1, max_length=200)


class HeroV1Create(HeroV1Base):
    """Fields accepted when creating a Hero via the deprecated v1 shape."""


class HeroV1Update(ORMView):
    """Fields accepted when partially updating a Hero via the deprecated v1 shape."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    superpower: str | None = Field(default=None, min_length=1, max_length=200)


class HeroV1(HeroV1Base):
    """A Hero as returned by the deprecated v1 API."""

    id: int
    created_at: IXDTFDatetime
    updated_at: IXDTFDatetime


def hero_to_v1(hero: Hero) -> HeroV1:
    """Convert a current (v2) Hero down to the deprecated v1 shape.

    v1 can only represent one power; the first entry in `powers` is treated
    as the primary power. Lossy but deliberate: v1 clients keep working,
    but never see more than one power even if v2 has several.
    """
    return HeroV1(
        id=hero.id,
        name=hero.name,
        superpower=hero.powers[0],
        created_at=hero.created_at,
        updated_at=hero.updated_at,
    )


def hero_v1_create_to_v2(payload: HeroV1Create) -> HeroCreate:
    """Convert a v1 create payload up to the current (v2) shape."""
    return HeroCreate(name=payload.name, powers=[payload.superpower])


def hero_v1_update_to_v2(payload: HeroV1Update) -> HeroUpdate:
    """Convert a v1 update payload up to the current (v2) shape.

    Only maps `superpower` -> `powers` when it was actually supplied -- an
    unset v1 field must stay unset in v2, not overwrite existing powers
    with a single-element list.
    """
    data = payload.model_dump(exclude_unset=True)
    if "superpower" in data:
        data["powers"] = [data.pop("superpower")]
    return HeroUpdate.model_validate(data)
```

### `controllers/heroes_v1.py` — v1 JSON router

New file, mirroring `heroes.py`:

```python
"""HTTP routes for /v1/heroes -- the deprecated single-power Hero shape.

Deprecated in favor of /v2/heroes (app.controllers.heroes), which supports
multiple powers per hero. Wraps the same CRUD app.controllers.heroes
already builds via app.crud.compat.CompatCRUD, converting to/from the v1
view with app.views.hero_v1's converter functions -- no new persistence
code, only the version-compatibility shape.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.controllers.heroes import DeleteRoles, HeroCRUD, ReadRoles, WriteRoles
from app.crud.compat import CompatCRUD
from app.http_headers import sunset
from app.models.hero import Hero as HeroModel
from app.views.hero import Hero
from app.views.hero_v1 import (
    HeroV1,
    HeroV1Create,
    HeroV1Update,
    hero_to_v1,
    hero_v1_create_to_v2,
    hero_v1_update_to_v2,
)

_SUNSET_AT = datetime(2027, 1, 1, tzinfo=UTC)

router = APIRouter(
    prefix="/heroes",
    tags=["heroes"],
    dependencies=[Depends(sunset(_SUNSET_AT, link="/v2/heroes"))],
)


def get_hero_v1_crud(crud: HeroCRUD) -> CompatCRUD[HeroV1, Hero, HeroModel]:
    """Build a v1-shaped CRUD interface backed by the current (v2) Hero CRUD."""
    return CompatCRUD(
        crud,
        to_legacy=hero_to_v1,
        from_legacy_create=hero_v1_create_to_v2,
        from_legacy_update=hero_v1_update_to_v2,
    )


HeroV1CRUD = Annotated[CompatCRUD[HeroV1, Hero, HeroModel], Depends(get_hero_v1_crud)]


@router.get("", dependencies=[ReadRoles])
async def list_heroes_v1(crud: HeroV1CRUD, skip: int = 0, limit: int = 100) -> list[HeroV1]:
    """List heroes in the deprecated v1 shape."""
    return await crud.list(skip=skip, limit=limit)


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[WriteRoles])
async def create_hero_v1(hero: HeroV1Create, crud: HeroV1CRUD) -> HeroV1:
    """Create a hero from a v1-shaped payload."""
    return await crud.create(hero)


@router.get("/{hero_id:int}", dependencies=[ReadRoles])
async def get_hero_v1(hero_id: int, crud: HeroV1CRUD) -> HeroV1:
    """Get a hero by id, in the deprecated v1 shape."""
    hero = await crud.get(hero_id)
    if hero is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return hero


@router.patch("/{hero_id:int}", dependencies=[WriteRoles])
async def update_hero_v1(hero_id: int, hero: HeroV1Update, crud: HeroV1CRUD) -> HeroV1:
    """Partially update a hero via a v1-shaped payload."""
    updated = await crud.update(hero_id, hero)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
    return updated


@router.delete("/{hero_id:int}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[DeleteRoles])
async def delete_hero_v1(hero_id: int, crud: HeroV1CRUD) -> None:
    """Delete a hero."""
    deleted = await crud.delete(hero_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hero not found")
```

### `controllers/heroes_v1_xml.py` and `heroes_v1_web.py`

Mirror `heroes_xml.py`/`heroes_web.py` exactly, but:
- import `DeleteRoles, HeroV1CRUD, ReadRoles, WriteRoles` from
  `app.controllers.heroes_v1` instead of `heroes`,
- use `HeroV1Create`/`HeroV1Update` from `app.views.hero_v1`,
- router `prefix="/heroes/xml"` / `"/heroes"` as today (the `/v1` prefix is
  added at mount time in `main.py`, same as v2),
- `_FIELDS = ("name", "superpower")` in the web variant — no `list_fields`
  needed, v1's `superpower` is scalar, so no change to the generic codec
  path is exercised here.

### `main.py`

Replace:
```python
app.include_router(heroes.router)
app.include_router(heroes_xml.router)
app.include_router(heroes_web.router)
```
with:
```python
app.include_router(heroes.router, prefix="/v2")
app.include_router(heroes_xml.router, prefix="/v2")
app.include_router(heroes_web.router, prefix="/v2")
app.include_router(heroes_v1.router, prefix="/v1")
app.include_router(heroes_v1_xml.router, prefix="/v1")
app.include_router(heroes_v1_web.router, prefix="/v1")
```
and add `heroes_v1, heroes_v1_web, heroes_v1_xml` to the `from
app.controllers import (...)` line. `health`, `protected`, `audit`, `mock`
mounts are unchanged.

### Import-linter

No new `layers` entries needed in `pyproject.toml`'s `[tool.importlinter]`
— `crud/compat.py` and `views/hero_v1.py` stay within their existing
layers; `controllers/heroes_v1*.py` import only already-lower layers
(`crud`, `http_headers`, `models`, `views`) plus sibling `controllers`
modules, the same direction `heroes_xml.py`/`heroes_web.py` already use.
Run `uv run lint-imports` to confirm.

### Tests

- Update path references from `/heroes` to `/v2/heroes` (and `/heroes/xml`,
  `/heroes/form`, `/heroes/components.js` to their `/v2` equivalents)
  across `tests/unit/controllers/test_heroes*.py`,
  `tests/integration/controllers/test_heroes.py`,
  `tests/e2e/test_heroes*_e2e.py`.
- New `tests/unit/controllers/test_heroes_v1.py`:
  - GET on a hero with multiple `powers` returns `superpower == powers[0]`.
  - POST with `superpower` persists such that a subsequent `/v2/heroes/{id}`
    GET shows `powers == [superpower]`.
  - PATCH that only sends `name` (not `superpower`) against a hero with
    multiple v2 `powers` leaves `powers` untouched (verify via `/v2` GET
    after) — the `exclude_unset` correctness case.
  - Every v1 response carries `Sunset`, `Deprecation: true`, and
    `Link: <.../v2/heroes>; rel="sunset"` headers; v2 responses carry none
    of them.
- New `tests/unit/controllers/test_heroes_v1_xml.py` /
  `test_heroes_v1_web.py` mirroring the existing xml/web test shapes.
- New `tests/unit/views/test_hero_v1.py`: `hero_to_v1` on a multi-power
  Hero returns only the first power; `hero_v1_create_to_v2` and
  `hero_v1_update_to_v2` round-trip correctly, including the
  unset-field-preserved case.
- New `tests/unit/crud/test_compat.py`: exercise `CompatCRUD` against a
  fake/minimal schema pair and converter functions (not Hero-specific) to
  verify get/list/create/update/delete all convert in the right direction.

### Docs

- New `docs/adrs/0002-api-and-model-versioning.md`, following
  `docs/adrs/template.md`'s Status/Context/Decision/Consequences shape:
  why path-based versioning (simple, explicit, browsable in Swagger UI, no
  new routing infrastructure needed); why the DB model itself stays
  unversioned/single-shape (`models/hero.py` always represents "current";
  older API versions are a views + CRUD-wrapper concern only, never a
  second table/model); why conversion lives in the views layer (pure,
  no I/O, easy to unit test in isolation); why `CompatCRUD` is generic
  (so the *n*-th future deprecated version costs a views module + a thin
  controller, not new CRUD infrastructure) — same framing as
  `0001-mvc-layering-with-a-generic-crud-interface.md`'s "cheap to add the
  next one" argument.
- `CLAUDE.md`: new section (placed near "Multi-format CRUD (XML / HTML web
  components)") titled "API and model versioning", describing: the
  `/v{N}` path-prefix convention; that the DB model always represents the
  current shape only; the `*_vN.py` views module + converter-function
  pattern; `crud/compat.py`'s `CompatCRUD` as the reusable wrapper; router-
  level `sunset()` application for a whole deprecated version at once.
- `src/app/crud/README.md`: short mention of `CompatCRUD` as an available
  building block for a resource that's grown a deprecated version.
- `src/app/views/README.md`: short mention of the `*_vN.py` + converter
  pattern alongside the existing `*Base`/`*Create`/`*Update`/plain-name
  convention.
- `src/app/controllers/README.md` (if it documents the xml/web sibling
  convention): extend it to mention version siblings (`heroes_v1.py`
  alongside `heroes.py`) as the same kind of sibling-router reuse.

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
- `/v1/heroes` responses carry `Sunset`/`Deprecation`/`Link` headers;
  `/v2/heroes` responses don't.
- A hero created via `POST /v1/heroes` with `superpower` reads back via
  `GET /v2/heroes/{id}` with `powers == [superpower]`.
- A hero created via `POST /v2/heroes` with multiple `powers` reads back
  via `GET /v1/heroes/{id}` showing only `powers[0]` as `superpower`.

## Open questions

None currently, beyond the hard dependency on
`2026-09-hero-v2-powers-field.md` landing first (see "Depends on" above).
