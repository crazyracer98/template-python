"""FastAPI app entrypoint: wires up settings, OIDC auth, and routes."""

from typing import Annotated, Any

from fastapi import Depends, FastAPI

from app.config import get_settings
from app.oidc import get_current_claims

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": settings.oidc_client_id,
    },
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check; reachable without a token."""
    return {"status": "ok"}


@app.get("/protected")
async def protected(
    claims: Annotated[dict[str, Any], Depends(get_current_claims)],
) -> dict[str, str]:
    """Example authenticated route: return only the subject claim, not the full token."""
    return {"sub": claims["sub"]}
