"""E2E journey test: what the "editor" role can and can't do end-to-end."""

from collections.abc import Callable

from playwright.sync_api import Page


def test_editor_can_create_and_update_but_not_delete(
    page: Page, base_url: str, access_token: Callable[[str], str]
) -> None:
    """An editor can create/update heroes across every format but can't delete or reach /audit."""
    headers = {"Authorization": f"Bearer {access_token('editor')}"}
    maintainer_headers = {"Authorization": f"Bearer {access_token('maintainer')}"}
    hero_ids: list[str] = []

    try:
        json_create_response = page.request.post(
            f"{base_url}/heroes",
            data={"name": "Black Widow", "superpower": "Espionage"},
            headers=headers,
        )
        assert json_create_response.status == 201
        json_hero_id = json_create_response.json()["id"]
        hero_ids.append(json_hero_id)

        update_response = page.request.patch(
            f"{base_url}/heroes/{json_hero_id}",
            data={"superpower": "Master spy"},
            headers=headers,
        )
        assert update_response.ok
        assert update_response.json()["superpower"] == "Master spy"

        xml_create_response = page.request.post(
            f"{base_url}/heroes/xml",
            data="<hero><name>Hawkeye</name><superpower>Marksmanship</superpower></hero>",
            headers={**headers, "Content-Type": "application/xml"},
        )
        assert xml_create_response.status == 201
        xml_hero_id = xml_create_response.text().split("<id>")[1].split("</id>")[0]
        hero_ids.append(xml_hero_id)

        xml_update_response = page.request.patch(
            f"{base_url}/heroes/xml/{xml_hero_id}",
            data="<hero><superpower>Precision archery</superpower></hero>",
            headers={**headers, "Content-Type": "application/xml"},
        )
        assert xml_update_response.ok
        assert "<superpower>Precision archery</superpower>" in xml_update_response.text()

        form_response = page.request.post(
            f"{base_url}/heroes/form",
            form={"name": "Quicksilver", "superpower": "Super speed"},
            headers=headers,
        )
        assert form_response.ok

        list_response = page.request.get(f"{base_url}/heroes", headers=headers)
        assert list_response.ok
        heroes = list_response.json()
        form_hero_id = next(hero["id"] for hero in heroes if hero["name"] == "Quicksilver")
        hero_ids.append(form_hero_id)
        listed_ids = {hero["id"] for hero in heroes}
        assert {json_hero_id, int(xml_hero_id), form_hero_id} <= listed_ids

        delete_response = page.request.delete(
            f"{base_url}/heroes/{json_hero_id}", headers=headers, fail_on_status_code=False
        )
        assert delete_response.status == 403

        audit_response = page.request.get(
            f"{base_url}/audit", headers=headers, fail_on_status_code=False
        )
        assert audit_response.status == 403
    finally:
        for hero_id in hero_ids:
            page.request.delete(f"{base_url}/heroes/{hero_id}", headers=maintainer_headers)
