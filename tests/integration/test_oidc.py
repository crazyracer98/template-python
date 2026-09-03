"""Integration test: validate a real access token against the live Keycloak.

Unlike tests/unit/, this reaches the actual `keycloak` stack
container (already running under the devcontainer, and under CI's
devcontainers/ci) instead of mocking it -- exercising the same discovery
+ JWKS code path app.oidc.decode_bearer_token uses for a real request.
"""

import httpx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.oidc import decode_bearer_token

client = TestClient(app)


def _fetch_access_token() -> str:
    """Obtain a real access token for the dev realm's "viewer" user."""
    settings = get_settings()
    response = httpx.post(
        settings.oidc_token_url,
        data={
            "grant_type": "password",
            "client_id": settings.oidc_client_id,
            "username": "viewer",
            "password": "viewer",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]  # type: ignore[no-any-return]


def test_decode_bearer_token_accepts_a_real_keycloak_token() -> None:
    """A token obtained from the real Keycloak dev realm decodes successfully."""
    claims = decode_bearer_token(_fetch_access_token())

    assert claims["preferred_username"] == "viewer"


def test_protected_route_accepts_a_real_keycloak_token() -> None:
    """GET /protected with a real bearer token returns its subject claim."""
    access_token = _fetch_access_token()

    response = client.get("/protected", headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 200
    assert response.json() == {"sub": decode_bearer_token(access_token)["sub"]}
