# Fix security review findings

## Status

Draft

## Goal

Address five findings from the 2026-09-04 OWASP-focused security review of
`src/app/`: stored XSS in the CRUD web components, an XML entity-expansion
DoS, a default-disabled JWT audience check, missing security response
headers, and an unguarded `MODE=mock` auth-bypass path.

## Approach

1. **Escape record data in the CRUD web-component JS** —
   [src/app/web_components.py](../../src/app/web_components.py). Replace the
   `innerHTML` template-literal interpolation in `render_crud_component_js`
   (`{resource}List.refresh`, `{resource}Form.connectedCallback`) with either
   DOM APIs (`textContent`, `createElement`) instead of string-built HTML, or
   an explicit HTML-escaping helper applied to every field value before it's
   interpolated. Add/extend `tests/unit/test_web_components.py` to assert a
   field value like `<img src=x onerror=alert(1)>` round-trips as inert text,
   not markup.

2. **Parse request-body XML with a safe parser** —
   [src/app/xml_codec.py](../../src/app/xml_codec.py). Replace
   `xml.etree.ElementTree.fromstring` in `from_xml` with
   `defusedxml.ElementTree.fromstring` (add `defusedxml` as a dependency),
   and drop the now-incorrect `# noqa: S314` comment. Add a unit test posting
   a nested-entity ("billion laughs") payload to a `heroes_xml`/
   `heroes_v1_xml` create endpoint and asserting it's rejected rather than
   hanging or consuming excess memory.

3. **Require an explicit OIDC audience** —
   [src/app/config.py](../../src/app/config.py),
   [src/app/oidc.py](../../src/app/oidc.py). Decide (see Open questions)
   whether to make `oidc_audience` a required setting outside `MODE=mock`, or
   have `decode_bearer_token`/settings validation raise at startup when
   `oidc_audience` is unset and `mode != "mock"`. Update
   `tests/unit/test_oidc.py` and `tests/unit/test_config.py` accordingly, and
   set `oidc_audience` in any dev/CI env files that currently omit it
   (`.devcontainer/stack/keycloak/`, CI workflow env).

4. **Add baseline security response headers** —
   [src/app/http_headers.py](../../src/app/http_headers.py),
   [src/app/main.py](../../src/app/main.py). Add a small middleware (or
   extend the existing header helper) that sets `Content-Security-Policy`
   (locked down enough for the `/form` pages' inline `<script src=...>` and
   custom elements — no `unsafe-inline` needed since the JS is
   externally-sourced from `components.js`), `X-Frame-Options: DENY` (or
   `frame-ancestors 'none'` in CSP), and `X-Content-Type-Options: nosniff` on
   all responses. Extend `tests/unit/test_http_headers.py` and the relevant
   e2e web tests to assert the headers are present.

5. **Guard against `MODE=mock` in non-dev deployments** —
   [src/app/oidc.py](../../src/app/oidc.py),
   [src/app/config.py](../../src/app/config.py). Add a startup check (e.g.
   in `app.main`'s app factory/lifespan, or `Settings` validation) that
   refuses to start with `mode == "mock"` unless a second explicit flag
   (e.g. `ALLOW_MOCK_MODE=1`, already-scoped to local/CI use) is also set.
   Document the flag in `src/app/README.md` and update
   `tests/unit/test_config.py`/`test_main.py` to cover the refusal.

Run `ruff`, `mypy --strict`, and `pytest` (unit + integration) after each
step, and the Playwright e2e suite after steps 1 and 4 (the ones touching
served HTML/headers), per `CLAUDE.md`'s verification requirement.

## Open questions

- For step 3: should `oidc_audience` become a required (non-Optional)
  setting for every non-mock mode, or should the existing opt-in behavior
  stay but with a loud startup warning? Decide before implementing — it
  changes `Settings` validation and every non-mock env file.
