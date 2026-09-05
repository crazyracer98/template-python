# Explicit CRUD-router/model versioning and format segments in routes

## Status

Draft

## Goal

Today `/v1`/`/v2` in a Hero path conflates two independent things: the
version of the *generic CRUD router* (`crud_router.py`'s factories,
which have in fact never changed) and the version of the *Hero shape*
(`HeroV1` vs. the current `Hero`/`HeroCreate`/`HeroUpdate`, unversioned
in name despite being "v2" in the path). Format (JSON vs. XML vs. web)
is distinguished only by an internal `/xml` path fragment or by which
routes exist at all, never a uniform segment — and each combination
lives in its own controller module (`heroes.py`/`heroes_xml.py`/
`heroes_web.py`, times two for the `_v1` siblings: six files total for
one resource). This plan separates the versioning axes explicitly — a
`/crud/v{router}` segment for the CRUD engine version, a `/heroes/v{model}`
segment for the resource/shape version, a `/{format}` segment for
JSON/XML/web — gives every versioned Pydantic view class a matching
numeric suffix, and collapses each resource-version's three per-format
files into one controller module built by a single new factory
function, so `main.py` mounts one router per resource-version instead
of three.

Path segment order is `/crud/v{router}/heroes/v{model}/{format}` (format
*last*, not between the two version segments) specifically so that one
resource-version's JSON/XML/web routes can be built as sub-routers of a
single combined `APIRouter` (each included at its own `/{format}`
sub-prefix) and mounted with one `include_router` call — see step 3.

## Approach

1. Write a new ADR (`docs/adrs/0009-...md`) recording this decision,
   superseding `docs/adrs/0002-api-and-model-versioning.md` (mark 0002's
   Status `Superseded by 0009`, per `docs/adrs/README.md` — never edit
   0002's Decision itself). Carry forward everything in 0002 that still
   holds (DB model stays unversioned and represents only the current
   shape; `CompatCRUD`/`*_vN.py` views pattern; per-format sibling
   routers) and add:
   - The path shape: `/crud/v{router_version}/heroes/v{model_version}/{format}`,
     e.g. `/crud/v1/heroes/v2/json`, `/crud/v1/heroes/v1/xml`,
     `/crud/v1/heroes/v2/web/form`. No bare alias on any axis — same
     "callers pick a version explicitly" rule 0002 already established,
     now applied to `router_version` and `format` too.
   - One combined `APIRouter` per resource-version, built by a single
     new factory call (step 3), replacing today's one-controller-module-
     per-format layout — so a resource-version is one file and one
     `include_router` call, not three.
   - `router_version` names a version of `crud_router.py`'s factories
     themselves (their route shape/behavior), not a resource's shape —
     it stays `1` for every existing route, since the factories haven't
     changed; it only increments when `build_json_router`/
     `build_xml_router`/`build_web_router`'s own behavior changes in a
     breaking way. Define it once as a constant in `crud_router.py`
     (e.g. `ROUTER_VERSION = 1`) that resource controllers import into
     their prefix, rather than each resource hardcoding `"v1"`
     independently.
   - The **DB model** (`models/hero.py`'s `Hero`) keeps its unversioned
     name — 0002's reasoning for this still holds and doesn't change
     just because view classes now carry suffixes: it represents one
     persisted shape, never a specific API version's. Only `app.views`
     classes get the numeric suffix.

2. Rename the current (latest) Hero views for symmetry with the
   already-suffixed `HeroV1*`:
   - `src/app/views/hero.py` → `src/app/views/hero_v2.py`;
     `HeroBase`/`HeroCreate`/`HeroUpdate`/`Hero` → `HeroV2Base`/
     `HeroV2Create`/`HeroV2Update`/`HeroV2`.
   - Update every importer: `views/hero_v1.py` (converter functions'
     type hints — consider also renaming `hero_to_v1`/
     `hero_v1_create_to_v2`/`hero_v1_update_to_v2` to name both
     versions explicitly, e.g. `hero_v2_to_v1`/`hero_v1_create_to_v2`
     stays fine since it already names both — only `hero_to_v1` is
     ambiguous, rename to `hero_v2_to_v1`) and `controllers/heroes.py`
     (`get_hero_crud`'s return type, `HeroCRUD`, and the
     `build_resource_router` call's `schema=`/`create_schema=`/
     `update_schema=` from step 4 — `heroes_xml.py`/`heroes_web.py` are
     deleted in step 4 rather than updated, so their imports don't need
     touching here).
   - `tests/unit/views/test_hero_v1.py` and any other test importing
     `app.views.hero`.

3. Add one new factory to `crud_router.py`, `build_resource_router`,
   that composes the three existing factories into a single `APIRouter`
   for one resource-version, taking the union of what
   `build_json_router`/`build_xml_router`/`build_web_router` each need
   today (`resource_label`, `schema`/`create_schema`/`update_schema`,
   `crud_dependency`, `read_roles`/`write_roles`/`delete_roles`,
   `item_tag`/`list_tag` for XML, `resource`/`fields` for web) plus the
   resource-version's full `prefix` (e.g.
   `/crud/v1/heroes/v2`). Internally it builds the three sub-routers as
   today, then does:

   ```python
   router = APIRouter(prefix=prefix, tags=tags)
   router.include_router(build_json_router(...))
   router.include_router(build_xml_router(...), prefix="/xml")
   router.include_router(build_web_router(...), prefix="/web")
   return router
   ```

   (`build_json_router`'s own routes sit directly under `prefix`, giving
   JSON the un-suffixed base per resource, or add `prefix="/json"` too
   if a uniform "every format is an explicit segment" rule is preferred
   over a JSON default — pick whichever `controllers/README.md` ends up
   documenting, but apply it identically to Hero's v1 and v2 routers.)
   Because the router already carries its own full prefix, a resource
   module's `router` is mounted with a bare `app.include_router(router)`
   in `main.py` — no prefix computed at the mount site.
   `build_web_router`'s `api_base` (today `"/v2/heroes"`, used to point
   the rendered form at the JSON API) becomes `f"{prefix}/json"`,
   computed once from the same `prefix` argument rather than passed
   separately and risking drift.
   `build_json_router`/`build_xml_router`/`build_web_router` themselves
   are unchanged — `build_resource_router` is a thin composition on top,
   so each remains independently usable (and independently tested) for
   a resource that genuinely only needs one format.

4. Replace the six existing Hero controller modules with two:
   - `heroes.py` (current/v2): one `build_resource_router(prefix=
     f"/crud/v{ROUTER_VERSION}/heroes/v2", ...)` call, replacing what
     `heroes.py`+`heroes_xml.py`+`heroes_web.py` did across three files.
   - `heroes_v1.py` (deprecated/v1): same, `prefix=
     f"/crud/v{ROUTER_VERSION}/heroes/v1"`, `CompatCRUD`-wrapped
     dependency as today; replaces `heroes_v1.py`+`heroes_v1_xml.py`+
     `heroes_v1_web.py`.
   - Delete `heroes_xml.py`, `heroes_web.py`, `heroes_v1_xml.py`,
     `heroes_v1_web.py`.
   - `main.py`: the current six `include_router(heroes*, prefix="/v{1,2}")`
     calls become two bare `include_router(heroes.router)` /
     `include_router(heroes_v1.router)` calls (prefix already baked into
     each router from step 3).

5. `crud_actions.py`/`crud_query.py` stay unchanged — only
   `crud_router.py` gains the new composing factory; per
   `controllers/README.md`'s existing guidance, a resource-specific
   layout change must not require touching the generic query/action
   helpers.

6. Update every hardcoded Hero path/class-name reference:
   - Tests: `tests/e2e/test_heroes_e2e.py`, `test_heroes_v1_e2e.py`,
     `test_heroes_v1_web_e2e.py`, `test_heroes_v1_xml_e2e.py`,
     `test_heroes_web_e2e.py`, `test_heroes_xml_e2e.py`,
     `tests/unit/controllers/test_heroes*.py`,
     `tests/integration/controllers/test_heroes.py`. (`test_crud_router.py`/
     `test_crud_query.py` use synthetic in-test resources, not `/heroes`
     literals — unaffected, though `test_crud_router.py` gains coverage
     for the new `build_resource_router` composition itself.)
   - Docs: `src/app/controllers/README.md`'s "Generic CRUD router
     factories", "API and model versioning", and module-list sections
     (six bullets collapse to two), `src/app/README.md`'s Hero worked
     example, root `README.md` if it shows an example path.

7. Verify: `ruff`, `mypy --strict`, `pytest` (unit + integration + e2e),
   and hit at least one route per format/version combination manually
   (or via the Playwright/e2e suite) to confirm the new paths actually
   resolve — a rename like this is easy to get half-right (e.g. leaving
   the web sub-router's `api_base` pointing at an old path, or a
   `dependencies=[...]`-injected header — see `controllers/README.md`'s
   `_with_dependency_headers` note — not propagating through the extra
   `include_router` nesting `build_resource_router` introduces).

## Open questions

- Whether JSON gets an explicit `/json` segment (fully uniform with
  `/xml`/`/web`) or stays the bare default at `/crud/v{router}/heroes/v{model}`
  (step 3) — either is consistent with "no bare alias on any *version*
  axis" from step 1, since that rule was about router/model versions,
  not format; format defaulting to JSON is a separate, smaller call.
  Resolve this while writing ADR 0009 (step 1), since the ADR needs to
  state the final rule before step 3 implements it.

Path segment order, scope (Hero/CRUD routes only, not
`/health`/`/audit`/`/protected`/`/mock/token`), and DB-model-stays-
unversioned were confirmed with the user before writing this plan.
