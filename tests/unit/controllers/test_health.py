"""Unit test: /health/live and /health/ready, with the health registry faked out."""

from fastapi.testclient import TestClient

from app.health.base import HealthCheckResult
from app.health.registry import HealthRegistry, get_health_registry
from app.main import app

client = TestClient(app)


class _FakeCheck:
    """A HealthCheck stand-in with a fixed outcome."""

    def __init__(self, name: str, *, healthy: bool) -> None:
        """Bind this check to a name and the fixed result it will report."""
        self.name = name
        self._healthy = healthy

    async def check(self) -> HealthCheckResult:
        """Return the fixed result this fake was constructed with."""
        return HealthCheckResult(self.name, healthy=self._healthy)


def _registry(*, healthy: bool) -> HealthRegistry:
    """Build a registry with one check, healthy or not as requested."""
    registry = HealthRegistry()
    registry.register(_FakeCheck("fake", healthy=healthy))
    return registry


def test_live() -> None:
    """GET /health/live returns 200 and the static ok payload, no dependency checks."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_all_checks_pass() -> None:
    """GET /health/ready returns 200 when every registered check is healthy."""
    app.dependency_overrides[get_health_registry] = lambda: _registry(healthy=True)
    try:
        response = client.get("/health/ready")
    finally:
        del app.dependency_overrides[get_health_registry]
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["fake"]["healthy"] is True


def test_ready_when_a_check_fails() -> None:
    """GET /health/ready returns 503 when a registered check is unhealthy."""
    app.dependency_overrides[get_health_registry] = lambda: _registry(healthy=False)
    try:
        response = client.get("/health/ready")
    finally:
        del app.dependency_overrides[get_health_registry]
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
