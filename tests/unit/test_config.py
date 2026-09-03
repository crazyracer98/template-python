"""Unit test: Settings.database_url assembles the async Postgres DSN."""

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
