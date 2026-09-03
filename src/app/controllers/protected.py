"""Example authenticated route, demonstrating app.oidc's auth dependency."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.oidc import get_current_claims

router = APIRouter(tags=["protected"])


@router.get("/protected")
async def protected(
    claims: Annotated[dict[str, Any], Depends(get_current_claims)],
) -> dict[str, str]:
    """Example authenticated route: return only the subject claim, not the full token."""
    return {"sub": claims["sub"]}
