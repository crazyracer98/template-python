"""Unit test: Settings.database_url assembles the async Postgres DSN, plus its
mode-dependent validation (production requires oidc_audience, mock requires
allow_mock_mode).
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_database_url_assembles_dsn_from_pieces() -> None:
    """database_url combines user/password/host/port/db into one asyncpg DSN."""
    settings = Settings(
        postgres_user="u",
        postgres_password="p",  # noqa: S106 -- test fixture value, not a real secret
        postgres_host="h",
        postgres_port=1234,
        postgres_db="d",
    )
    assert settings.database_url == "postgresql+asyncpg://u:p@h:1234/d"


def test_production_mode_requires_oidc_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings(mode="production") with no oidc_audience raises ValidationError."""
    monkeypatch.delenv("OIDC_AUDIENCE", raising=False)
    with pytest.raises(ValidationError, match="oidc_audience"):
        Settings(mode="production")


def test_production_mode_with_oidc_audience_succeeds() -> None:
    """Settings(mode="production", oidc_audience=...) constructs without error."""
    settings = Settings(mode="production", oidc_audience="api")
    assert settings.oidc_audience == "api"


def test_dev_mode_does_not_require_oidc_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings(mode="dev") (the default) constructs fine with no oidc_audience set."""
    monkeypatch.delenv("OIDC_AUDIENCE", raising=False)
    assert Settings(mode="dev").oidc_audience is None


def test_mock_mode_requires_allow_mock_mode_flag() -> None:
    """Settings(mode="mock") with no allow_mock_mode raises ValidationError."""
    with pytest.raises(ValidationError, match="ALLOW_MOCK_MODE"):
        Settings(mode="mock")


def test_mock_mode_with_allow_mock_mode_succeeds() -> None:
    """Settings(mode="mock", allow_mock_mode=True) constructs without error."""
    settings = Settings(mode="mock", allow_mock_mode=True)
    assert settings.mode == "mock"
