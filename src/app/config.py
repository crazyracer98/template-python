"""Application settings, sourced entirely from the process environment."""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings."""

    # No .env file for the app itself: every value below is meant to come
    # from the process environment, which the compose files set directly
    # (see .devcontainer/compose.yml and stack/*/compose.yml) --
    # some pulled straight from a stack service's own env file,
    # some (DATABASE_URL, s3_access_key/s3_secret_key) assembled below
    # from those raw pieces since Compose can't interpolate a value from
    # one env file into another compose file's own env var. See CLAUDE.md's
    # "Configuration" section.
    model_config = SettingsConfigDict(extra="ignore")

    app_name: str = "template-python"

    postgres_user: str = "app"
    postgres_password: str = "app"  # noqa: S105 -- local Postgres default, not a real secret
    postgres_db: str = "app"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = Field(default="rustfsadmin", validation_alias="RUSTFS_ACCESS_KEY")
    s3_secret_key: str = Field(default="rustfsadmin", validation_alias="RUSTFS_SECRET_KEY")

    redis_url: str = "redis://localhost:6379/0"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Build the async Postgres DSN from the individual connection pieces."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # OIDC: works with any provider supporting Authorization Code + PKCE, not
    # just Keycloak (see src/app/oidc.py). authorization_url/token_url are
    # static so FastAPI can build the Swagger UI login flow at import time,
    # without a network round trip; the JWKS used to validate tokens is
    # instead discovered lazily from issuer_url (see oidc.py), so unit tests
    # that never authenticate never need network access. audience is left
    # unset: the bundled dev realm's "api" client does not set one.
    oidc_issuer_url: str = "http://localhost:8080/realms/template-python"
    oidc_authorization_url: str = (
        "http://localhost:8080/realms/template-python/protocol/openid-connect/auth"
    )
    # "_token_url" trips ruff's S105 (looks like a hardcoded password); it is a URL.
    oidc_token_url: str = (
        "http://localhost:8080/realms/template-python/protocol/openid-connect/token"  # noqa: S105
    )
    oidc_client_id: str = "api"
    oidc_algorithm: str = "RS256"
    oidc_audience: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
