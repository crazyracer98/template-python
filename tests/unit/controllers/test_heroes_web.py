"""Unit test: /heroes/form and /heroes/components.js."""

from fastapi.testclient import TestClient

from app.controllers.heroes import get_hero_crud
from app.crud.base import CRUDInterface
from app.main import app
from app.models.hero import Hero as HeroModel
from app.repositories.memory import InMemoryRepository
from app.views.hero import Hero

client = TestClient(app)


def test_hero_form_serves_html(authed: None) -> None:
    """GET /heroes/form serves an HTML page with the form and web-component tags."""
    response = client.get("/heroes/form")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<form" in response.text
    assert "<hero-list" in response.text


def test_submit_hero_form_creates_a_hero_and_redirects(authed: None) -> None:
    """POST /heroes/form creates a hero and redirects back to the form."""
    repository = InMemoryRepository(HeroModel)
    app.dependency_overrides[get_hero_crud] = lambda: CRUDInterface(
        schema=Hero, repository=repository
    )
    try:
        response = client.post(
            "/heroes/form",
            data={"name": "Batman", "powers": "Detective skills, Martial arts"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/heroes/form"
    finally:
        del app.dependency_overrides[get_hero_crud]


def test_hero_components_js_defines_custom_elements() -> None:
    """GET /heroes/components.js serves the web-component JS, unauthenticated."""
    response = client.get("/heroes/components.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert "customElements.define" in response.text
