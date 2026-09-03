"""Provider-agnostic OIDC bearer-token validation (Authorization Code + PKCE).

Only the OpenAPI-facing piece (the OAuth2AuthorizationCodeBearer scheme, used
to render the Swagger UI login flow) is built eagerly, from static settings.
Everything that needs the network -- fetching the provider's OIDC discovery
document and JWKS -- is deferred behind an lru_cache-wrapped function, so
importing this module (and therefore app.main, and therefore every unit test
using TestClient) never requires a running OIDC provider.
"""

from functools import lru_cache
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import PyJWKClient

from app.config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=settings.oidc_authorization_url,
    tokenUrl=settings.oidc_token_url,
)


@lru_cache
def _get_jwks_client() -> PyJWKClient:
    """Discover the provider's JWKS endpoint and return a caching client for it."""
    discovery_url = f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration"
    response = httpx.get(discovery_url, timeout=10)
    response.raise_for_status()
    jwks_uri: str = response.json()["jwks_uri"]
    return PyJWKClient(jwks_uri, cache_keys=True)


def decode_bearer_token(token: str) -> dict[str, Any]:
    """Verify a bearer token's signature and standard claims, and return its payload."""
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[settings.oidc_algorithm],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer_url,
            options={"verify_aud": settings.oidc_audience is not None},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_claims(token: Annotated[str, Depends(oauth2_scheme)]) -> dict[str, Any]:
    """FastAPI dependency: validate the request's bearer token and return its claims."""
    return decode_bearer_token(token)
