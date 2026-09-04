"""Unit test: /v1/heroes/form and /v1/heroes/components.js -- the deprecated v1 shape."""

from fastapi.testclient import TestClient

from app.controllers.heroes import get_hero_crud
from app.crud.base import CRUDInterface
from app.main import app
from app.models.hero import Hero as HeroModel
from app.repositories.memory import InMemoryRepository
from app.views.hero import Hero

client = TestClient(app)


def test_hero_v1_form_serves_html(authed: None) -> None:
    """GET /v1/heroes/form serves an HTML page with the form and web-component tags."""
    response = client.get("/v1/heroes/form")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<form" in response.text
    assert "<hero-list" in response.text


def test_submit_hero_v1_form_creates_a_hero_and_redirects(authed: None) -> None:
    """POST /v1/heroes/form creates a hero and redirects back to the form."""
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = lambda: CRUDInterface(
        schema=Hero, repository=repository
    )
    try:
        response = client.post(
            "/v1/heroes/form",
            data={"name": "Batman", "superpower": "Detective skills"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/v1/heroes/form"
    finally:
        del app.dependency_overrides[get_hero_crud]


def test_hero_v1_components_js_defines_custom_elements() -> None:
    """GET /v1/heroes/components.js serves the web-component JS, unauthenticated."""
    response = client.get("/v1/heroes/components.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert "customElements.define" in response.text


def test_v1_form_page_carries_deprecation_headers(authed: None) -> None:
    """GET /v1/heroes/form carries Sunset/Deprecation/Link headers."""
    response = client.get("/v1/heroes/form")
    assert response.status_code == 200
    assert response.headers["Deprecation"] == "true"
    assert "Sunset" in response.headers
    assert response.headers["Link"] == '</v2/heroes>; rel="sunset"'
