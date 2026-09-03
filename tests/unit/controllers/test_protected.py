"""Unit test: GET /protected rejects requests without a bearer token."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_protected_requires_auth() -> None:
    """GET /protected with no Authorization header is rejected with 401."""
    response = client.get("/protected")
    assert response.status_code == 401
