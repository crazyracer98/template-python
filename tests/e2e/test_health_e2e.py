"""E2E smoke test: /health/live and /health/ready respond through a real Playwright request."""

from playwright.sync_api import Page


def test_live(page: Page, base_url: str) -> None:
    """GET /health/live returns the static ok payload."""
    response = page.request.get(f"{base_url}/health/live")
    assert response.ok
    assert response.json() == {"status": "ok"}


def test_ready(page: Page, base_url: str) -> None:
    """GET /health/ready returns 200 with every real external service healthy."""
    response = page.request.get(f"{base_url}/health/ready")
    assert response.ok
    assert response.json()["status"] == "ok"
