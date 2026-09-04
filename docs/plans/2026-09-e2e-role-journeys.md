# Reorganize e2e RBAC coverage into per-role user-journey subdirectories

## Status

Draft

## Goal

`tests/e2e/` currently proves each *format* works (`test_heroes_e2e.py` for
JSON, `test_heroes_xml_e2e.py` for XML, `test_heroes_web_e2e.py` for the web
form) and, separately, that two individual routes enforce RBAC
(`test_protected_e2e.py`, `test_audit_e2e.py`) — but nothing walks through
what a *specific role* is actually able to do end-to-end in one session, or
proves what it's denied. Add one subdirectory per Keycloak client role
(`viewer`, `editor`, `maintainer`, `security`, `detective` — see
`.devcontainer/stack/keycloak/realm-export.json`) under `tests/e2e/`, each
containing a single journey test that logs in as that role and walks through
its realistic sequence of allowed actions plus the boundaries it should hit.

This is additive/reorganizational only — no application code changes.

## Current RBAC shape (for reference)

From `src/app/controllers/heroes.py` and `src/app/controllers/audit.py`:

| Role | `/heroes` read (JSON+XML+form) | `/heroes` write | `/heroes` delete | `/audit` |
|---|---|---|---|---|
| `viewer` | yes | no | no | no |
| `editor` | yes | yes | no | no |
| `maintainer` | yes | yes | yes | no |
| `security` | no | no | no | yes |
| `detective` | yes | no | no | yes |

Note `security` is the only role with *no* hero access at all, and
`detective` is the only role with both hero read and audit access — each
role's journey should exercise exactly its row above, including the "no"
cells as explicit 403 assertions, not just the "yes" cells.

## Approach

### 1. Add a shared token fixture to `conftest.py`

Three files currently each define their own near-identical
`_fetch_access_token()` (`test_heroes_e2e.py`, `test_protected_e2e.py`,
`test_audit_e2e.py` — the latter two importing or reimplementing the same
password-grant call). Consolidate into one fixture in `tests/e2e/conftest.py`
so every new journey test uses it instead of adding a sixth copy:

```python
@pytest.fixture(scope="session")
def access_token() -> Callable[[str], str]:
    """Return a function that logs in a dev-realm user and returns their access token."""
    settings = get_settings()

    def _fetch(username: str) -> str:
        response = httpx.post(
            settings.oidc_token_url,
            data={
                "grant_type": "password",
                "client_id": settings.oidc_client_id,
                "username": username,
                "password": username,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["access_token"]  # type: ignore[no-any-return]

    return _fetch
```

(Every dev-realm test user's password equals its username — see
`realm-export.json`.) Update `test_protected_e2e.py` and
`test_heroes_e2e.py`/`test_heroes_xml_e2e.py`/`test_heroes_web_e2e.py` (the
latter two currently `import _fetch_access_token from tests.e2e.test_heroes_e2e`)
to take the `access_token` fixture and call `access_token("viewer")` /
`access_token("maintainer")` instead of the local helper. Delete the
now-redundant `_fetch_access_token` definitions.

### 2. Retire `test_audit_e2e.py` into the role journeys

Its two cases — security accepted, viewer rejected — are exactly the
`security` and `viewer` rows of the table above, so they move into
`security/test_security_journey.py` and `viewer/test_viewer_journey.py`
respectively (step-by-step below) rather than being duplicated. Delete the
file once both assertions have a home.

Leave `test_protected_e2e.py` where it is — `/protected` is explicitly an
unversioned bare-auth example (sunset-marked, superseded by the role-scoped
routes per its own docstring), not tied to any one role's journey.

### 3. New directories

```
tests/e2e/
  viewer/
    __init__.py
    test_viewer_journey.py
  editor/
    __init__.py
    test_editor_journey.py
  maintainer/
    __init__.py
    test_maintainer_journey.py
  security/
    __init__.py
    test_security_journey.py
  detective/
    __init__.py
    test_detective_journey.py
```

`__init__.py` in each, matching `tests/e2e/__init__.py`'s existing
package style (needed for the `from tests.e2e.... import ...` absolute-import
convention already used between e.g. `test_heroes_xml_e2e.py` and
`test_heroes_e2e.py`). No per-subdirectory `README.md` — precedent is
`tests/unit/controllers/`, `tests/integration/repositories/`, etc., which
don't have one either; only suite-level directories do. Update
`tests/e2e/README.md`'s directory description to mention the per-role
layout.

Each journey test keeps the existing create/try/finally/delete pattern for
any hero it creates itself, and seeds/tears down via the `maintainer` token
when the role under test can't do that step itself (documented per-role
below) — that dependency *is* part of the realism (an editor's leftover data
genuinely needs a maintainer to remove it), not test-only plumbing.

### 4. `viewer/test_viewer_journey.py`

A viewer only ever reads. Seed a hero with `access_token("maintainer")` in a
fixture/setup step, then as `access_token("viewer")`:

1. `GET /heroes` → 200, the seeded hero appears.
2. `GET /heroes/{id}` → 200.
3. `GET /heroes/xml` → 200, hero appears.
4. `GET /heroes/xml/{id}` → 200.
5. `GET /heroes/form` → 200, HTML form.
6. `POST /heroes` → 403.
7. `PATCH /heroes/{id}` → 403.
8. `DELETE /heroes/{id}` → 403.
9. `GET /audit` → 403 (absorbed from `test_audit_e2e.py`).

Tear down the seeded hero with the `maintainer` token.

### 5. `editor/test_editor_journey.py`

An editor creates and updates but can't delete or reach audit:

1. `POST /heroes` (JSON) → 201.
2. `PATCH /heroes/{id}` → 200.
3. `POST /heroes/xml` → 201 (a second hero, to exercise the XML create path
   too).
4. `PATCH /heroes/xml/{id}` → 200.
5. `POST /heroes/form` → creates a third hero via the web form.
6. `GET /heroes` → 200, all three visible (editor is also a read role).
7. `DELETE /heroes/{id}` on any of the three → 403.
8. `GET /audit` → 403.
9. Teardown: delete all three heroes with the `maintainer` token, since the
   editor themselves has no delete access — the journey's own boundary.

### 6. `maintainer/test_maintainer_journey.py`

A maintainer has full lifecycle rights across every surface but still can't
see the audit log. Keep this a short cross-surface narrative rather than
duplicating `test_heroes_e2e.py`'s exhaustive CRUD/404/422 coverage, which
stays where it is as format-regression coverage:

1. `POST /heroes` (JSON) → 201.
2. `GET /heroes/form` → 200, the new hero is listed.
3. `PATCH /heroes/xml/{id}` → 200, edits it via the XML integration.
4. `GET /heroes/{id}` (JSON) → 200, confirms the XML edit is visible from
   the JSON side.
5. `DELETE /heroes/{id}` → 204.
6. `GET /audit` → 403.

### 7. `security/test_security_journey.py`

Security has audit access and nothing else:

1. `GET /audit` → 200, `roles == ["security"]` (absorbed from
   `test_audit_e2e.py`).
2. `GET /heroes` → 403.
3. `GET /heroes/xml` → 403.
4. `GET /heroes/form` → 403.
5. `POST /heroes` → 403.

### 8. `detective/test_detective_journey.py`

A detective is the one role with both audit and hero-read access, modeling
someone cross-referencing the audit log against the roster:

1. `GET /audit` → 200, `roles == ["detective"]`.
2. Seed a hero via the `maintainer` token.
3. `GET /heroes` → 200, `GET /heroes/{id}` → 200.
4. `POST /heroes` → 403.
5. `PATCH /heroes/{id}` → 403.
6. `DELETE /heroes/{id}` → 403.
7. Teardown via `maintainer`.

## Verification

```
uv run pytest tests/e2e
```

Show the actual pass/fail output for the full `tests/e2e` run (all five new
journeys plus the unchanged format-regression files), and confirm the
combined coverage report (`tests/e2e/README.md`'s coverage-combination
mechanism) still clears the repo's 95% floor — the new tests hit routes
already covered by the format-regression suite, so no new lines should
appear uncovered, but a role-boundary branch (e.g. `security` hitting
`ReadRoles`'s 403 path) that was previously untested might now show up
differently in the report.

## Open questions

Whether `test_heroes_e2e.py`/`test_heroes_xml_e2e.py`/`test_heroes_web_e2e.py`
should eventually fold into `maintainer/` too, since they already run as the
`maintainer` user — left alone for now because they're format/regression
tests (do JSON/XML/web-form CRUD work at all) rather than role tests (can
*this* role do this), and conflating the two would make it harder to tell,
from a failure, which property broke.
