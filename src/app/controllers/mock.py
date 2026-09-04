"""HTTP routes for POST /mock/token -- only mounted when MODE=mock (see app.main).

Issues an unsigned-in-practice JWT shaped like a real Keycloak token (the same
resource_access.<client>.roles claim app.oidc.require_roles reads), so RBAC is
exercisable without a running Keycloak. app.oidc.decode_bearer_token's own
MODE=mock branch never verifies the signature, so the signing key here is a fixed,
non-secret, local-only value -- never used outside MODE=mock.

The route body is `# pragma: no cover` for tests/e2e specifically: e2e drives one
live MODE=dev process (see .devcontainer/compose.yml), which never mounts this
router at all (app.main's `_mount_mode_specific_routers`) -- there's no request
path that could reach it there. tests/unit/controllers/test_mock.py exercises it
directly and still counts toward its own 95% gate.
"""

from typing import Any

import jwt
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["mock"])
settings = get_settings()

# At least 32 bytes so PyJWT doesn't warn about a weak HMAC key -- length matters
# here (PyJWT checks it), secrecy doesn't (see the module docstring above).
_MOCK_SIGNING_KEY = "mock-mode-signing-key-not-a-real-secret"


class MockTokenRequest(BaseModel):
    """Desired claims for a mock access token."""

    sub: str
    roles: list[str] = []


@router.post("/mock/token")
async def issue_mock_token(request: MockTokenRequest) -> dict[str, Any]:  # pragma: no cover
    """Issue a mock access token carrying the given subject and client roles."""
    claims = {
        "sub": request.sub,
        "preferred_username": request.sub,
        "resource_access": {settings.oidc_client_id: {"roles": request.roles}},
    }
    return {"access_token": jwt.encode(claims, _MOCK_SIGNING_KEY, algorithm="HS256")}
