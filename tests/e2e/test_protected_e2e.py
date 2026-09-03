"""E2E test: /protected, through a real Playwright request, both accepts a
real Keycloak token and rejects a malformed one.
"""

import httpx
from playwright.sync_api import Page

from app.config import get_settings


def _fetch_access_token() -> str:
    """Obtain a real access token for the dev realm's "viewer" user."""
    settings = get_settings()
    response = httpx.post(
        settings.oidc_token_url,
        data={
            "grant_type": "password",
            "client_id": settings.oidc_client_id,
            "username": "viewer",
            "password": "viewer",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]  # type: ignore[no-any-return]


def test_protected_accepts_a_real_keycloak_token(page: Page, base_url: str) -> None:
    """GET /protected with a real bearer token returns the subject claim."""
    access_token = _fetch_access_token()

    response = page.request.get(
        f"{base_url}/protected", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.ok
    assert response.json()["sub"]


def test_protected_rejects_a_malformed_token(page: Page, base_url: str) -> None:
    """GET /protected with a present but malformed bearer token is rejected with 401."""
    response = page.request.get(
        f"{base_url}/protected",
        headers={"Authorization": "Bearer not-a-jwt"},
        fail_on_status_code=False,
    )

    assert response.status == 401
