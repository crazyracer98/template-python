"""Integration fixtures: wait for stack services to finish starting."""

from __future__ import annotations

import time
from collections.abc import Generator

import httpx
import pytest

from app.config import get_settings

_STARTUP_TIMEOUT_SECONDS = 60.0


@pytest.fixture(scope="session", autouse=True)
def _keycloak_ready() -> Generator[None]:
    """Block until the live Keycloak container is accepting requests.

    Unlike the other stack services, Keycloak is a JVM app doing
    `start-dev --import-realm` (see .devcontainer/stack/keycloak/compose.yml)
    and has no compose healthcheck, so it can still be starting up when this
    suite's first request goes out on a cold CI run -- poll its discovery
    endpoint instead of letting that request fail with connection refused.
    """
    settings = get_settings()
    discovery_url = f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration"
    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            httpx.get(discovery_url, timeout=2).raise_for_status()
            yield
            return
        except httpx.HTTPError:
            time.sleep(0.5)
    raise RuntimeError(f"keycloak did not become ready within {_STARTUP_TIMEOUT_SECONDS}s")
