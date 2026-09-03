"""Integration test: validate a real access token against the live Keycloak.

Unlike tests/unit/, this reaches the actual `keycloak` infra-stack
container (already running under the devcontainer, and under CI's
devcontainers/ci) instead of mocking it -- exercising the same discovery
+ JWKS code path app.oidc.decode_bearer_token uses for a real request.
"""

import httpx

from app.config import get_settings
from app.oidc import decode_bearer_token


def test_decode_bearer_token_accepts_a_real_keycloak_token() -> None:
    """A token obtained from the real Keycloak dev realm decodes successfully."""
    settings = get_settings()
    response = httpx.post(
        settings.oidc_token_url,
        data={
            "grant_type": "password",
            "client_id": settings.oidc_client_id,
            "username": "devuser",
            "password": "devuser",
        },
        timeout=10,
    )
    response.raise_for_status()
    access_token = response.json()["access_token"]

    claims = decode_bearer_token(access_token)

    assert claims["preferred_username"] == "devuser"
