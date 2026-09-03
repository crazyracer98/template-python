"""E2E fixture overrides: point Playwright at the running api container,
and at a browser served by the selenium container instead of a local one.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Generator
from urllib.parse import urlparse

import httpx
import pytest
from playwright.sync_api import Browser, Playwright
from selenium.webdriver import ChromeOptions, Remote

_STARTUP_TIMEOUT_SECONDS = 10.0


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the api service's base URL, overridable via E2E_BASE_URL."""
    return os.environ.get("E2E_BASE_URL", "http://api:8000")


@pytest.fixture(scope="session", autouse=True)
def _running_app(base_url: str) -> Generator[None, None, None]:
    """Start the api server for the duration of the e2e run, unless one is
    already up (e.g. under the "FastAPI: api" launch config) or E2E_BASE_URL
    points somewhere this suite doesn't own.
    """
    if "E2E_BASE_URL" in os.environ:
        yield
        return

    health_url = f"{base_url}/health"
    try:
        httpx.get(health_url, timeout=1).raise_for_status()
        yield
        return
    except httpx.HTTPError:
        pass

    port = urlparse(base_url).port
    uvicorn = shutil.which("uvicorn")
    if uvicorn is None:
        raise RuntimeError("uvicorn not found on PATH")
    # 0.0.0.0: must be reachable from the sibling selenium container, not
    # just loopback -- same as the root README's manual startup command.
    # Fixed args plus our own parsed base_url's port, not external input.
    process = subprocess.Popen(  # noqa: S603
        [uvicorn, "app.main:app", "--host", "0.0.0.0", "--port", str(port)]  # noqa: S104
    )
    try:
        deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                httpx.get(health_url, timeout=1).raise_for_status()
                break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            process.terminate()
            process.wait(timeout=5)
            raise RuntimeError(
                f"api server did not become healthy within {_STARTUP_TIMEOUT_SECONDS}s"
            )
        yield
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Generator[Browser, None, None]:
    """Connect to the selenium container's Chromium over CDP.

    No browser binaries are installed in this container -- see
    tests/e2e/README.md for why the browser itself lives in a separate
    container that Playwright connects to remotely instead.
    """
    selenium_url = os.environ.get("E2E_SELENIUM_URL", "http://selenium:4444")
    driver = Remote(command_executor=f"{selenium_url}/wd/hub", options=ChromeOptions())
    try:
        cdp_url = str(driver.capabilities["se:cdp"])
        browser = playwright.chromium.connect_over_cdp(cdp_url)
        try:
            yield browser
        finally:
            browser.close()
    finally:
        driver.quit()
