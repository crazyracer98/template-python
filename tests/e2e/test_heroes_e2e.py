"""E2E smoke test: /heroes CRUD, through real Playwright requests against the live api."""

from collections.abc import Callable

from playwright.sync_api import Page


def test_hero_crud_lifecycle(page: Page, base_url: str, access_token: Callable[[str], str]) -> None:
    """Create, list, get, update, and delete a hero, then confirm 404s past that point."""
    headers = {"Authorization": f"Bearer {access_token('maintainer')}"}
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


def test_create_hero_with_missing_field_returns_422(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """POST /heroes without the required superpower field returns a validation problem."""
    response = page.request.post(
        f"{base_url}/heroes",
        data={"name": "Nobody"},
        headers={"Authorization": f"Bearer {access_token('maintainer')}"},
        fail_on_status_code=False,
    )
    assert response.status == 422
    assert response.headers["content-type"] == "application/problem+json"
