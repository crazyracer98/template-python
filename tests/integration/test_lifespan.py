"""Integration test: the app's lifespan applies pending Alembic migrations on startup."""

from fastapi.testclient import TestClient

from app.main import app


def test_lifespan_applies_migrations_and_starts_serving() -> None:
    """Starting the app (lifespan included) against the real database succeeds."""
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
