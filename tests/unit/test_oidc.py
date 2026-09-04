"""Unit test: decode_bearer_token rejects a malformed token, and require_roles gating."""

from typing import Annotated, Any

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import oidc
from app.oidc import decode_bearer_token, require_roles


def test_decode_bearer_token_rejects_a_malformed_token() -> None:
    """A token that isn't valid JWT structure is rejected with 401, no network needed."""
    with pytest.raises(HTTPException) as exc_info:
        decode_bearer_token("not-a-jwt")
    assert exc_info.value.status_code == 401


def test_decode_bearer_token_mock_mode_skips_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """MODE=mock trusts the token's claims without checking its signature."""
    monkeypatch.setattr(oidc.settings, "mode", "mock")
    token = jwt.encode(
        {"sub": "test-user"}, "at-least-32-bytes-long-hmac-signing-key", algorithm="HS256"
    )
    assert decode_bearer_token(token)["sub"] == "test-user"


def _require_roles_app() -> FastAPI:
    """A throwaway app with one route gated by require_roles("editor")."""
    app = FastAPI()

    @app.get("/gated")
    def gated(
        claims: Annotated[dict[str, Any], Depends(require_roles("editor"))],
    ) -> dict[str, Any]:
        return claims

    return app


def test_require_roles_allows_a_granted_role() -> None:
    """require_roles passes through when the caller has one of the required roles."""
    app = _require_roles_app()
    app.dependency_overrides[oidc.get_current_claims] = lambda: {
        "sub": "u",
        "resource_access": {oidc.settings.oidc_client_id: {"roles": ["editor"]}},
    }
    response = TestClient(app).get("/gated")
    assert response.status_code == 200


def test_require_roles_rejects_a_missing_role() -> None:
    """require_roles rejects with 403 when the caller lacks every required role."""
    app = _require_roles_app()
    app.dependency_overrides[oidc.get_current_claims] = lambda: {
        "sub": "u",
        "resource_access": {oidc.settings.oidc_client_id: {"roles": ["viewer"]}},
    }
    response = TestClient(app).get("/gated")
    assert response.status_code == 403


def test_require_roles_rejects_claims_with_no_resource_access() -> None:
    """require_roles rejects with 403 when the token carries no resource_access at all."""
    app = _require_roles_app()
    app.dependency_overrides[oidc.get_current_claims] = lambda: {"sub": "u"}
    response = TestClient(app).get("/gated")
    assert response.status_code == 403
