"""Example authenticated route, demonstrating app.oidc's auth dependency.

Superseded by the role-scoped routes in app.resources.heroes/audit, which
demonstrate app.oidc.require_roles instead of bare authentication -- marked
sunset accordingly (see app.http_headers).
"""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.http_headers import sunset
from app.oidc import get_current_claims

router = APIRouter(tags=["protected"])


@router.get(
    "/protected",
    dependencies=[Depends(sunset(datetime(2027, 1, 1, tzinfo=UTC), link="/v2/heroes"))],
)
# Gated by get_current_claims only (authenticated, no role check) -- fine for this
# documented example, but do not copy this route into a real resource's router
# without also adding a role requirement (dependencies=[Depends(require_roles(...))],
# see app.oidc's "RBAC" section and heroes.py's ReadRoles/WriteRoles/DeleteRoles).
async def protected(
    claims: Annotated[dict[str, Any], Depends(get_current_claims)],
) -> dict[str, str]:
    """Example authenticated route: return only the subject claim, not the full token."""
    return {"sub": claims["sub"]}
