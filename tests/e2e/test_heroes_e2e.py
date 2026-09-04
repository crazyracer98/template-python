"""E2E smoke test: /heroes CRUD, through real Playwright requests against the live api."""

import httpx
from playwright.sync_api import Page

from app.config import get_settings


def _fetch_access_token() -> str:
    """Obtain a real access token for the dev realm's "maintainer" user (full Hero CRUD)."""
    settings = get_settings()
    response = httpx.post(
        settings.oidc_token_url,
        data={
            "grant_type": "password",
            "client_id": settings.oidc_client_id,
            "username": "maintainer",
            "password": "maintainer",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]  # type: ignore[no-any-return]


def test_hero_crud_lifecycle(page: Page, base_url: str) -> None:
    """Create, list, get, update, and delete a hero, then confirm 404s past that point."""
    headers = {"Authorization": f"Bearer {_fetch_access_token()}"}
    create_response = page.request.post(
        f"{base_url}/heroes",
        data={"name": "Black Panther", "superpower": "Vibranium suit"},
        headers=headers,
    )
    assert create_response.status == 201
    hero_id = create_response.json()["id"]

    try:
        list_response = page.request.get(f"{base_url}/heroes", headers=headers)
        assert list_response.ok
        assert any(hero["id"] == hero_id for hero in list_response.json())

        get_response = page.request.get(f"{base_url}/heroes/{hero_id}", headers=headers)
        assert get_response.ok
        assert get_response.json()["name"] == "Black Panther"

        update_response = page.request.patch(
            f"{base_url}/heroes/{hero_id}",
            data={"superpower": "Enhanced senses"},
            headers=headers,
        )
        assert update_response.ok
        assert update_response.json()["superpower"] == "Enhanced senses"
    finally:
        delete_response = page.request.delete(f"{base_url}/heroes/{hero_id}", headers=headers)
        assert delete_response.status == 204

    missing_get_response = page.request.get(
        f"{base_url}/heroes/{hero_id}", headers=headers, fail_on_status_code=False
    )
    assert missing_get_response.status == 404

    missing_update_response = page.request.patch(
        f"{base_url}/heroes/{hero_id}",
        data={"name": "Nobody"},
        headers=headers,
        fail_on_status_code=False,
    )
    assert missing_update_response.status == 404

    missing_delete_response = page.request.delete(
        f"{base_url}/heroes/{hero_id}", headers=headers, fail_on_status_code=False
    )
    assert missing_delete_response.status == 404


def test_create_hero_with_missing_field_returns_422(page: Page, base_url: str) -> None:
    """POST /heroes without the required superpower field returns a validation problem."""
    response = page.request.post(
        f"{base_url}/heroes",
        data={"name": "Nobody"},
        headers={"Authorization": f"Bearer {_fetch_access_token()}"},
        fail_on_status_code=False,
    )
    assert response.status == 422
    assert response.headers["content-type"] == "application/problem+json"
