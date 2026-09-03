"""E2E smoke test: /heroes CRUD, through real Playwright requests against the live api."""

from playwright.sync_api import Page


def test_hero_crud_lifecycle(page: Page, base_url: str) -> None:
    """Create, list, get, update, and delete a hero, then confirm 404s past that point."""
    create_response = page.request.post(
        f"{base_url}/heroes", data={"name": "Black Panther", "superpower": "Vibranium suit"}
    )
    assert create_response.status == 201
    hero_id = create_response.json()["id"]

    try:
        list_response = page.request.get(f"{base_url}/heroes")
        assert list_response.ok
        assert any(hero["id"] == hero_id for hero in list_response.json())

        get_response = page.request.get(f"{base_url}/heroes/{hero_id}")
        assert get_response.ok
        assert get_response.json()["name"] == "Black Panther"

        update_response = page.request.patch(
            f"{base_url}/heroes/{hero_id}", data={"superpower": "Enhanced senses"}
        )
        assert update_response.ok
        assert update_response.json()["superpower"] == "Enhanced senses"
    finally:
        delete_response = page.request.delete(f"{base_url}/heroes/{hero_id}")
        assert delete_response.status == 204

    missing_get_response = page.request.get(
        f"{base_url}/heroes/{hero_id}", fail_on_status_code=False
    )
    assert missing_get_response.status == 404

    missing_update_response = page.request.patch(
        f"{base_url}/heroes/{hero_id}", data={"name": "Nobody"}, fail_on_status_code=False
    )
    assert missing_update_response.status == 404

    missing_delete_response = page.request.delete(
        f"{base_url}/heroes/{hero_id}", fail_on_status_code=False
    )
    assert missing_delete_response.status == 404
