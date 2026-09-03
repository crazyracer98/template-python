"""E2E smoke test: /health responds through a real Playwright request."""

from playwright.sync_api import Page


def test_health(page: Page, base_url: str) -> None:
    """GET /health, through a real HTTP request, returns the ok payload."""
    response = page.request.get(f"{base_url}/health")
    assert response.ok
    assert response.json() == {"status": "ok"}
