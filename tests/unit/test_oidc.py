"""Unit test: decode_bearer_token rejects a malformed token without network access."""

import pytest
from fastapi import HTTPException

from app.oidc import decode_bearer_token


def test_decode_bearer_token_rejects_a_malformed_token() -> None:
    """A token that isn't valid JWT structure is rejected with 401, no network needed."""
    with pytest.raises(HTTPException) as exc_info:
        decode_bearer_token("not-a-jwt")
    assert exc_info.value.status_code == 401
