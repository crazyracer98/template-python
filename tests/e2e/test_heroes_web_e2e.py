"""E2E smoke test: /heroes/form and /heroes/components.js against the live api."""

from playwright.sync_api import Page

from tests.e2e.test_heroes_e2e import _fetch_access_token


def test_hero_form_serves_html_and_accepts_a_submission(page: Page, base_url: str) -> None:
    """GET /heroes/form serves HTML; POSTing to it creates a hero and redirects back."""
    headers = {"Authorization": f"Bearer {_fetch_access_token()}"}

    form_response = page.request.get(f"{base_url}/heroes/form", headers=headers)
    assert form_response.ok
    assert "<form" in form_response.text()

    submit_response = page.request.post(
        f"{base_url}/heroes/form",
        form={"name": "Storm", "superpower": "Weather control"},
        headers=headers,
    )
    assert submit_response.ok  # Playwright follows the 303 redirect by default
    assert submit_response.url == f"{base_url}/heroes/form"


def test_hero_components_js_serves_javascript(page: Page, base_url: str) -> None:
    """GET /heroes/components.js serves the web-component JS, unauthenticated."""
    response = page.request.get(f"{base_url}/heroes/components.js")
    assert response.ok
    assert "customElements.define" in response.text()
