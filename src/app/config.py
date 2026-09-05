"""Application settings, sourced entirely from the process environment.

Both `_require_*` validators below are `# pragma: no cover` for tests/e2e
specifically: the live api process only ever starts with a Settings that
already satisfies them (see .devcontainer/compose.yml's MODE=dev/mock), so a
raise from either one would mean the process never came up for tests/e2e to
run against in the first place. tests/unit/test_config.py exercises both
directly and still counts toward its own 95% gate.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Mode = Literal["dev", "mock", "production"]


class Settings(BaseSettings):
    """Typed application settings."""

    # No .env file for the app itself: every value below is meant to come
    # from the process environment, which the compose files set directly
    # (see .devcontainer/compose.yml and stack/*/compose.yml) --
    # some pulled straight from a stack service's own env file,
    # some (DATABASE_URL, s3_access_key/s3_secret_key) assembled below
    # from those raw pieces since Compose can't interpolate a value from
    # one env file into another compose file's own env var. See
    # README.md's "Configuration" section.
    model_config = SettingsConfigDict(extra="ignore")

    app_name: str = "template-fastapi"

    # dev: debugger enabled (see app.main). mock: every external service
    # (Postgres, Redis, S3, OIDC) is replaced with a local/in-memory fake --
    # see app.controllers.heroes, app.health.registry, app.oidc. production:
    # debugger disabled. Defaults to "dev" to match this template's other
    # defaults (localhost hosts, etc.), which assume local/devcontainer use
    # unless overridden -- see the Dockerfile's runner stage for the
    # production default.
    mode: Mode = "dev"

    # MODE=mock trusts every bearer token's claims and skips every real
    # external service (see oidc.decode_bearer_token) -- a deployment that
    # somehow ends up running it (a misconfigured env, a copy-pasted compose
    # file) would silently bypass auth entirely. Requiring this second,
    # explicitly-named flag means MODE=mock can never be reached by MODE's
    # own default/typo alone; only .devcontainer/compose.yml and CI set it,
    # both already scoped to local/CI use.
    allow_mock_mode: bool = False

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
    # unset outside "production" (see _require_oidc_audience_in_production
    # below): the bundled dev realm's "api" client does not set one.
    oidc_issuer_url: str = "http://localhost:8080/realms/template-fastapi"
    oidc_authorization_url: str = (
        "http://localhost:8080/realms/template-fastapi/protocol/openid-connect/auth"
    )
    # "_token_url" trips ruff's S105 (looks like a hardcoded password); it is a URL.
    oidc_token_url: str = (
        "http://localhost:8080/realms/template-fastapi/protocol/openid-connect/token"  # noqa: S105
    )
    oidc_client_id: str = "api"
    oidc_algorithm: str = "RS256"
    oidc_audience: str | None = None

    @model_validator(mode="after")
    def _require_oidc_audience_in_production(self) -> Self:
        """Refuse to construct production Settings with no audience check configured.

        oidc.decode_bearer_token only verifies the "aud" claim when oidc_audience is
        set, so an unset audience in production would accept a token issued for any
        other client of the same provider. dev/mock stay opt-in (the bundled dev
        Keycloak realm sets no audience mapper), so this only tightens the mode that
        actually faces real traffic.
        """
        if self.mode == "production" and self.oidc_audience is None:  # pragma: no cover
            raise ValueError("oidc_audience must be set when MODE=production")
        return self

    @model_validator(mode="after")
    def _require_allow_mock_mode_flag(self) -> Self:
        """Refuse to construct MODE=mock Settings without the explicit allow_mock_mode flag.

        See allow_mock_mode's own docstring for why this second flag exists.
        """
        if self.mode == "mock" and not self.allow_mock_mode:  # pragma: no cover
            raise ValueError("MODE=mock requires ALLOW_MOCK_MODE=1 to be set")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
