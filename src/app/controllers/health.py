"""HTTP routes for k8s-style liveness and readiness probes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.health.registry import HealthRegistry, get_health_registry

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    """Liveness probe: the process is up and serving requests. Never checks dependencies."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(
    response: Response,
    registry: Annotated[HealthRegistry, Depends(get_health_registry)],
) -> dict[str, object]:
    """Readiness probe: every registered external service must be reachable."""
    results = await registry.run_all()
    healthy = all(result.healthy for result in results)
    response.status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "degraded",
        "checks": {
            result.name: {"healthy": result.healthy, "detail": result.detail} for result in results
        },
    }
