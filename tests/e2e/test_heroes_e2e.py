"""E2E smoke test: /v2/heroes CRUD, through real Playwright requests against the live api."""

from collections.abc import Callable

from playwright.sync_api import Page


def test_hero_crud_lifecycle(page: Page, base_url: str, access_token: Callable[[str], str]) -> None:
    """Create, list, get, update, and delete a hero, then confirm 404s past that point."""
    headers = {"Authorization": f"Bearer {access_token('maintainer')}"}
    create_response = page.request.post(
        f"{base_url}/v2/heroes",
        data={"name": "Black Panther", "powers": ["Vibranium suit"]},
        headers=headers,
    )
    assert create_response.status == 201
    hero_id = create_response.json()["id"]

    try:
        list_response = page.request.get(f"{base_url}/v2/heroes", headers=headers)
        assert list_response.ok
        assert any(hero["id"] == hero_id for hero in list_response.json())

        get_response = page.request.get(
            f"{base_url}/v2/heroes", params={"id": hero_id}, headers=headers
        )
        assert get_response.ok
        assert get_response.json()["name"] == "Black Panther"

        update_response = page.request.patch(
            f"{base_url}/v2/heroes",
            params={"id": hero_id},
            data={"powers": ["Enhanced senses"]},
            headers=headers,
        )
        assert update_response.ok
        assert update_response.json()["powers"] == ["Enhanced senses"]
    finally:
        delete_response = page.request.delete(
            f"{base_url}/v2/heroes", params={"id": hero_id}, headers=headers
        )
        assert delete_response.status == 204

    missing_get_response = page.request.get(
        f"{base_url}/v2/heroes",
        params={"id": hero_id},
        headers=headers,
        fail_on_status_code=False,
    )
    assert missing_get_response.status == 404

    missing_update_response = page.request.patch(
        f"{base_url}/v2/heroes",
        params={"id": hero_id},
        data={"name": "Nobody"},
        headers=headers,
        fail_on_status_code=False,
    )
    assert missing_update_response.status == 404

    missing_delete_response = page.request.delete(
        f"{base_url}/v2/heroes",
        params={"id": hero_id},
        headers=headers,
        fail_on_status_code=False,
    )
    assert missing_delete_response.status == 404


def test_hero_filter_sort_and_bulk_actions(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """Filtering/sorting a list and a bulk delete via filters work end to end."""
    headers = {"Authorization": f"Bearer {access_token('maintainer')}"}
    first = page.request.post(
        f"{base_url}/v2/heroes",
        data={"name": "Filter Test Alpha", "powers": ["Speed"]},
        headers=headers,
    ).json()
    second = page.request.post(
        f"{base_url}/v2/heroes",
        data={"name": "Filter Test Beta", "powers": ["Speed"]},
        headers=headers,
    ).json()

    try:
        filtered = page.request.get(
            f"{base_url}/v2/heroes",
            params={"name__icontains": "Filter Test", "sort": "name"},
            headers=headers,
        )
        assert filtered.ok
        assert [hero["name"] for hero in filtered.json()] == [
            "Filter Test Alpha",
            "Filter Test Beta",
        ]

        created_after = page.request.get(
            f"{base_url}/v2/heroes",
            params={
                "name__icontains": "Filter Test",
                "created_at__min": "2000-01-01T00:00:00+00:00",
            },
            headers=headers,
        )
        assert created_after.ok
        assert len(created_after.json()) == 2

        bulk_update = page.request.patch(
            f"{base_url}/v2/heroes",
            params={"name__icontains": "Filter Test"},
            data={"powers": ["Bulk updated"]},
            headers=headers,
        )
        assert bulk_update.ok
        assert bulk_update.json()["matched"] == 2

        bulk_delete = page.request.delete(
            f"{base_url}/v2/heroes",
            params={"name__icontains": "Filter Test"},
            headers=headers,
        )
        assert bulk_delete.ok
        assert bulk_delete.json()["matched"] == 2
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


def test_create_hero_with_missing_field_returns_422(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """POST /v2/heroes without the required powers field returns a validation problem."""
    response = page.request.post(
        f"{base_url}/v2/heroes",
        data={"name": "Nobody"},
        headers={"Authorization": f"Bearer {access_token('maintainer')}"},
        fail_on_status_code=False,
    )
    assert response.status == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_bulk_update_and_delete_with_no_filters_and_no_id_are_rejected(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """A bulk PATCH/DELETE with neither id nor filters is rejected, never a full-table action."""
    headers = {"Authorization": f"Bearer {access_token('maintainer')}"}

    update_response = page.request.patch(
        f"{base_url}/v2/heroes",
        data={"name": "Should Not Apply"},
        headers=headers,
        fail_on_status_code=False,
    )
    assert update_response.status == 422

    delete_response = page.request.delete(
        f"{base_url}/v2/heroes", headers=headers, fail_on_status_code=False
    )
    assert delete_response.status == 422
