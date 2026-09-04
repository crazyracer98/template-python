"""E2E smoke test: /heroes/xml CRUD, through real Playwright requests against the live api."""

from playwright.sync_api import Page

from tests.e2e.test_heroes_e2e import _fetch_access_token


def test_hero_xml_crud_lifecycle(page: Page, base_url: str) -> None:
    """Create, list, get, update, and delete a hero through the XML routes."""
    headers = {
        "Authorization": f"Bearer {_fetch_access_token()}",
        "Content-Type": "application/xml",
    }
    create_response = page.request.post(
        f"{base_url}/heroes/xml",
        data="<hero><name>Storm</name><superpower>Weather control</superpower></hero>",
        headers=headers,
    )
    assert create_response.status == 201
    body = create_response.text()
    hero_id = body.split("<id>")[1].split("</id>")[0]

    try:
        list_response = page.request.get(f"{base_url}/heroes/xml", headers=headers)
        assert list_response.ok
        assert f"<id>{hero_id}</id>" in list_response.text()

        get_response = page.request.get(f"{base_url}/heroes/xml/{hero_id}", headers=headers)
        assert get_response.ok
        assert "<name>Storm</name>" in get_response.text()

        update_response = page.request.patch(
            f"{base_url}/heroes/xml/{hero_id}",
            data="<hero><superpower>Lightning storms</superpower></hero>",
            headers=headers,
        )
        assert update_response.ok
        assert "<superpower>Lightning storms</superpower>" in update_response.text()
    finally:
        delete_response = page.request.delete(f"{base_url}/heroes/xml/{hero_id}", headers=headers)
        assert delete_response.status == 204

    missing_response = page.request.get(
        f"{base_url}/heroes/xml/{hero_id}", headers=headers, fail_on_status_code=False
    )
    assert missing_response.status == 404


def test_hero_xml_update_missing_returns_404(page: Page, base_url: str) -> None:
    """PATCH /heroes/xml/{id} for a nonexistent id returns 404."""
    headers = {
        "Authorization": f"Bearer {_fetch_access_token()}",
        "Content-Type": "application/xml",
    }
    response = page.request.patch(
        f"{base_url}/heroes/xml/999999",
        data="<hero><name>Nobody</name></hero>",
        headers=headers,
        fail_on_status_code=False,
    )
    assert response.status == 404


def test_hero_xml_delete_missing_returns_404(page: Page, base_url: str) -> None:
    """DELETE /heroes/xml/{id} for a nonexistent id returns 404."""
    headers = {"Authorization": f"Bearer {_fetch_access_token()}"}
    response = page.request.delete(
        f"{base_url}/heroes/xml/999999", headers=headers, fail_on_status_code=False
    )
    assert response.status == 404
