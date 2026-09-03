"""E2E fixture overrides: point Playwright at the running api container."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the api service's base URL, overridable via E2E_BASE_URL."""
    return os.environ.get("E2E_BASE_URL", "http://api:8000")
