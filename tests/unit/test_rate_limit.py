"""Unit test: app.rate_limit's exempt_single_record_action helper, and that
limiter.limit(...) actually enforces a limit (against a throwaway Limiter/app, not
the real shared one -- see tests/conftest.py's _disable_rate_limiting).
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter

from app.rate_limit import exempt_single_record_action


def test_exempt_single_record_action_true_when_id_given() -> None:
    """exempt_single_record_action is True for a request carrying an id query param."""
    app = FastAPI()

    @app.get("/probe")
    def probe(request: Request) -> dict[str, bool]:
        return {"exempt": exempt_single_record_action(request)}

    response = TestClient(app).get("/probe", params={"id": 1})
    assert response.json() == {"exempt": True}


def test_exempt_single_record_action_false_when_no_id() -> None:
    """exempt_single_record_action is False for a request with no id query param."""
    app = FastAPI()

    @app.get("/probe")
    def probe(request: Request) -> dict[str, bool]:
        return {"exempt": exempt_single_record_action(request)}

    response = TestClient(app).get("/probe")
    assert response.json() == {"exempt": False}


def test_limiter_limit_enforces_the_configured_rate() -> None:
    """A route decorated with limiter.limit(...) 429s once its limit is exceeded."""
    throwaway_limiter = Limiter(key_func=lambda request: "fixed-test-key")
    app = FastAPI()

    @app.get("/limited")
    @throwaway_limiter.limit("1/minute")
    async def limited(request: Request) -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 429


def test_limiter_limit_respects_exempt_when() -> None:
    """exempt_when=... skips enforcement entirely for a matching request."""
    throwaway_limiter = Limiter(key_func=lambda request: "fixed-test-key-2")
    app = FastAPI()

    @app.get("/limited-unless-exempt")
    @throwaway_limiter.limit("1/minute", exempt_when=exempt_single_record_action)
    async def limited_unless_exempt(request: Request) -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/limited-unless-exempt", params={"id": 1}).status_code == 200
    assert client.get("/limited-unless-exempt", params={"id": 2}).status_code == 200
    assert client.get("/limited-unless-exempt").status_code == 200
    assert client.get("/limited-unless-exempt").status_code == 429
