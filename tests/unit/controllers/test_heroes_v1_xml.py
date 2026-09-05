"""Unit test: /v1/heroes/xml CRUD routes -- the deprecated single-power Hero shape, in XML."""

from fastapi.testclient import TestClient

from app.controllers.heroes import get_hero_crud
from app.crud.base import CRUDInterface
from app.main import app
from app.models.hero import Hero as HeroModel
from app.repositories.memory import InMemoryRepository
from app.views.hero import Hero

client = TestClient(app)


def test_hero_v1_xml_crud_lifecycle(authed: None) -> None:
    """Create, list, get, update, and delete a hero through the v1 XML routes."""
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = lambda: CRUDInterface(
        schema=Hero, repository=repository
    )
    try:
        create_response = client.post(
            "/v1/heroes/xml",
            content="<hero><name>Spider-Man</name><superpower>Wall-crawling</superpower></hero>",
            headers={"Content-Type": "application/xml"},
        )
        assert create_response.status_code == 201
        assert create_response.headers["content-type"] == "application/xml"
        assert "<name>Spider-Man</name>" in create_response.text
        assert "<superpower>Wall-crawling</superpower>" in create_response.text

        list_response = client.get("/v1/heroes/xml")
        assert list_response.status_code == 200
        assert "<heroes>" in list_response.text
        hero_id = list_response.text.split("<id>")[1].split("</id>")[0]

        get_response = client.get("/v1/heroes/xml", params={"id": hero_id})
        assert get_response.status_code == 200
        assert "<name>Spider-Man</name>" in get_response.text

        update_response = client.patch(
            "/v1/heroes/xml",
            params={"id": hero_id},
            content="<hero><superpower>Web-slinging</superpower></hero>",
            headers={"Content-Type": "application/xml"},
        )
        assert update_response.status_code == 200
        assert "<superpower>Web-slinging</superpower>" in update_response.text

        delete_response = client.delete("/v1/heroes/xml", params={"id": hero_id})
        assert delete_response.status_code == 204

        missing_response = client.get("/v1/heroes/xml", params={"id": hero_id})
        assert missing_response.status_code == 404
    finally:
        del app.dependency_overrides[get_hero_crud]


def test_hero_v1_xml_update_missing_returns_404(authed: None) -> None:
    """PATCH /v1/heroes/xml?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = lambda: CRUDInterface(
        schema=Hero, repository=InMemoryRepository(HeroModel)
    )
    try:
        response = client.patch(
            "/v1/heroes/xml",
            params={"id": 999},
            content="<hero><name>Nobody</name></hero>",
            headers={"Content-Type": "application/xml"},
        )
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_hero_v1_xml_delete_missing_returns_404(authed: None) -> None:
    """DELETE /v1/heroes/xml?id= for a nonexistent id returns 404."""
    app.dependency_overrides[get_hero_crud] = lambda: CRUDInterface(
        schema=Hero, repository=InMemoryRepository(HeroModel)
    )
    try:
        response = client.delete("/v1/heroes/xml", params={"id": 999})
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 404


def test_v1_xml_responses_carry_deprecation_headers(authed: None) -> None:
    """Every /v1/heroes/xml response carries Sunset/Deprecation/Link headers."""
    app.dependency_overrides[get_hero_crud] = lambda: CRUDInterface(
        schema=Hero, repository=InMemoryRepository(HeroModel)
    )
    try:
        response = client.get("/v1/heroes/xml")
    finally:
        del app.dependency_overrides[get_hero_crud]
    assert response.status_code == 200
    assert response.headers["Deprecation"] == "true"
    assert "Sunset" in response.headers
    assert response.headers["Link"] == '</v2/heroes/xml>; rel="sunset"'
