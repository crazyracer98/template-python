"""E2E smoke test: /v2/heroes/form and /v2/heroes/components.js against the live api."""

from collections.abc import Callable

from playwright.sync_api import Page, expect


def test_hero_form_serves_html_and_accepts_a_submission(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """GET /v2/heroes/form serves HTML; POSTing to it creates a hero and redirects back."""
    headers = {"Authorization": f"Bearer {access_token('maintainer')}"}

    form_response = page.request.get(f"{base_url}/v2/heroes/form", headers=headers)
    assert form_response.ok
    assert "<form" in form_response.text()
    assert form_response.headers["x-frame-options"] == "DENY"
    assert form_response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in form_response.headers["content-security-policy"]

    submit_response = page.request.post(
        f"{base_url}/v2/heroes/form",
        form={"name": "Storm", "powers": "Weather control, Flight"},
        headers=headers,
    )
    assert submit_response.ok  # Playwright follows the 303 redirect by default
    assert submit_response.url == f"{base_url}/v2/heroes/form"


def test_hero_form_submission_with_invalid_data_returns_422(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """POSTing /v2/heroes/form with an empty required field returns a validation problem."""
    headers = {"Authorization": f"Bearer {access_token('maintainer')}"}
    response = page.request.post(
        f"{base_url}/v2/heroes/form",
        form={"name": "Nobody", "powers": ""},
        headers=headers,
        fail_on_status_code=False,
    )
    assert response.status == 422


def test_hero_components_js_serves_javascript(page: Page, base_url: str) -> None:
    """GET /v2/heroes/components.js serves the web-component JS, unauthenticated."""
    response = page.request.get(f"{base_url}/v2/heroes/components.js")
    assert response.ok
    assert "customElements.define" in response.text()


def test_hero_list_filter_and_bulk_delete_through_the_rendered_ui(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """Filtering the rendered <hero-list> and bulk-deleting the checked rows both work.

    Drives the actual browser-rendered web component (not just its API calls
    directly), proving the filter controls/sort select/bulk checkboxes the JS
    renders from `/v2/heroes/filters` actually reach the JSON router end to end.
    """
    headers = {"Authorization": f"Bearer {access_token('maintainer')}"}
    page.set_extra_http_headers(headers)
    first = page.request.post(
        f"{base_url}/v2/heroes",
        data={"name": "Web UI Test Alpha", "powers": ["Speed"]},
        headers=headers,
    ).json()
    second = page.request.post(
        f"{base_url}/v2/heroes",
        data={"name": "Web UI Test Beta", "powers": ["Speed"]},
        headers=headers,
    ).json()

    try:
        page.goto(f"{base_url}/v2/heroes/form")
        page.wait_for_selector("hero-list table")

        rows = page.locator("hero-list table tr:has(input[data-id])")

        filter_input = page.locator('input[data-field="name"][data-op="icontains"]')
        filter_input.fill("Web UI Test")
        page.locator("button.apply").click()
        expect(rows).to_have_count(2)

        page.locator('hero-list input[type="checkbox"].select-all').check()
        page.locator("hero-list button.bulk-delete").click()
        # The bulk-result message is overwritten by refresh()'s own re-render right
        # after it's set, so assert on the resulting (empty) row list instead of
        # trying to catch that transient text. `expect(...).to_have_count` polls
        # via Playwright's own protocol-level queries, not an in-page eval(), so
        # it works under the form page's strict `default-src 'self'` CSP where
        # `page.wait_for_function` (which does eval a string) does not.
        expect(rows).to_have_count(0)
    finally:
        page.request.delete(
            f"{base_url}/v2/heroes",
            params={"id": first["id"]},
            headers=headers,
            fail_on_status_code=False,
        )
        page.request.delete(
            f"{base_url}/v2/heroes",
            params={"id": second["id"]},
            headers=headers,
            fail_on_status_code=False,
        )
