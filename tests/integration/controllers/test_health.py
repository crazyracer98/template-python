"""Integration test: /health/ready against the real registered health checks."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ready_reports_every_stack_service_healthy() -> None:
    """GET /health/ready returns 200 with every real external service healthy."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["checks"]) == {"database", "redis", "s3", "oidc"}
    assert all(check["healthy"] for check in body["checks"].values())
