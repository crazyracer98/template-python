"""E2E test: /protected, through a real Playwright request, both accepts a
real Keycloak token and rejects a malformed one.
"""

from collections.abc import Callable

from playwright.sync_api import Page


def test_protected_accepts_a_real_keycloak_token(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """GET /protected with a real bearer token returns the subject claim."""
    response = page.request.get(
        f"{base_url}/protected", headers={"Authorization": f"Bearer {access_token('viewer')}"}
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
