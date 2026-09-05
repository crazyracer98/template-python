"""E2E smoke test: /crud/v1/heroes/v2/xml CRUD against the live api."""

from collections.abc import Callable

from playwright.sync_api import Page


def test_hero_xml_crud_lifecycle(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """Create, list, get, update, and delete a hero through the XML routes."""
    headers = {
        "Authorization": f"Bearer {access_token('maintainer')}",
        "Content-Type": "application/xml",
    }
    create_response = page.request.post(
        f"{base_url}/crud/v1/heroes/v2/xml",
        data="<hero><name>Storm</name><powers>Weather control</powers></hero>",
        headers=headers,
    )
    assert create_response.status == 201
    body = create_response.text()
    hero_id = body.split("<id>")[1].split("</id>")[0]

    try:
        list_response = page.request.get(f"{base_url}/crud/v1/heroes/v2/xml", headers=headers)
        assert list_response.ok
        assert f"<id>{hero_id}</id>" in list_response.text()

        get_response = page.request.get(
            f"{base_url}/crud/v1/heroes/v2/xml", params={"id": hero_id}, headers=headers
        )
        assert get_response.ok
        assert "<name>Storm</name>" in get_response.text()

        update_response = page.request.patch(
            f"{base_url}/crud/v1/heroes/v2/xml",
            params={"id": hero_id},
            data="<hero><powers>Lightning storms</powers></hero>",
            headers=headers,
        )
        assert update_response.ok
        assert "<powers>Lightning storms</powers>" in update_response.text()
    finally:
        delete_response = page.request.delete(
            f"{base_url}/crud/v1/heroes/v2/xml", params={"id": hero_id}, headers=headers
        )
        assert delete_response.status == 204

    missing_response = page.request.get(
        f"{base_url}/crud/v1/heroes/v2/xml",
        params={"id": hero_id},
        headers=headers,
        fail_on_status_code=False,
    )
    assert missing_response.status == 404


def test_hero_xml_update_missing_returns_404(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """PATCH /crud/v1/heroes/v2/xml?id= for a nonexistent id returns 404."""
    headers = {
        "Authorization": f"Bearer {access_token('maintainer')}",
        "Content-Type": "application/xml",
    }
    response = page.request.patch(
        f"{base_url}/crud/v1/heroes/v2/xml",
        params={"id": 999999},
        data="<hero><name>Nobody</name></hero>",
        headers=headers,
        fail_on_status_code=False,
    )
    assert response.status == 404


def test_hero_xml_delete_missing_returns_404(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """DELETE /crud/v1/heroes/v2/xml?id= for a nonexistent id returns 404."""
    headers = {"Authorization": f"Bearer {access_token('maintainer')}"}
    response = page.request.delete(
        f"{base_url}/crud/v1/heroes/v2/xml",
        params={"id": 999999},
        headers=headers,
        fail_on_status_code=False,
    )
    assert response.status == 404


def test_hero_xml_create_rejects_a_billion_laughs_payload(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """POST xml rejects a nested-entity-expansion payload with 400, not a hang/OOM."""
    billion_laughs = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ELEMENT lolz (#PCDATA)>
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
]>
<hero><name>&lol2;</name></hero>"""
    response = page.request.post(
        f"{base_url}/crud/v1/heroes/v2/xml",
        data=billion_laughs,
        headers={
            "Authorization": f"Bearer {access_token('maintainer')}",
            "Content-Type": "application/xml",
        },
        fail_on_status_code=False,
    )
    assert response.status == 400


def test_hero_xml_bulk_update_and_delete_via_filters(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """PATCH/DELETE xml?<filters> act in bulk and render an XML bulk-result body."""
    headers = {
        "Authorization": f"Bearer {access_token('maintainer')}",
        "Content-Type": "application/xml",
    }
    page.request.post(
        f"{base_url}/crud/v1/heroes/v2/xml",
        data="<hero><name>XML Bulk Test Alpha</name><powers>Speed</powers></hero>",
        headers=headers,
    )
    page.request.post(
        f"{base_url}/crud/v1/heroes/v2/xml",
        data="<hero><name>XML Bulk Test Beta</name><powers>Speed</powers></hero>",
        headers=headers,
    )

    update_response = page.request.patch(
        f"{base_url}/crud/v1/heroes/v2/xml",
        params={"name__icontains": "XML Bulk Test"},
        data="<hero><powers>Updated</powers></hero>",
        headers=headers,
    )
    assert update_response.ok
    assert "<bulk-update-result>" in update_response.text()
    assert "<matched>2</matched>" in update_response.text()

    delete_response = page.request.delete(
        f"{base_url}/crud/v1/heroes/v2/xml",
        params={"name__icontains": "XML Bulk Test"},
        headers=headers,
    )
    assert delete_response.ok
    assert "<bulk-delete-result>" in delete_response.text()
    assert "<matched>2</matched>" in delete_response.text()
