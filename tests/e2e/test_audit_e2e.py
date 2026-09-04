"""E2E smoke test: /audit, through a real Playwright request against the live api."""

import httpx
from playwright.sync_api import Page

from app.config import get_settings


def _fetch_access_token(username: str) -> str:
    """Obtain a real access token for the given dev realm user."""
    settings = get_settings()
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


def test_audit_accepts_the_security_role(page: Page, base_url: str) -> None:
    """GET /audit with the security user's token returns their subject and roles."""
    response = page.request.get(
        f"{base_url}/audit",
        headers={"Authorization": f"Bearer {_fetch_access_token('security')}"},
    )
    assert response.ok
    assert response.json()["roles"] == ["security"]


def test_audit_rejects_the_viewer_role(page: Page, base_url: str) -> None:
    """GET /audit with the viewer user's token (no security/detective role) is rejected."""
    response = page.request.get(
        f"{base_url}/audit",
        headers={"Authorization": f"Bearer {_fetch_access_token('viewer')}"},
        fail_on_status_code=False,
    )
    assert response.status == 403
