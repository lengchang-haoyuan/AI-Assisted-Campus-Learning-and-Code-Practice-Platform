from fastapi import APIRouter

from app.api.deps import HealthServiceDependency
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, summary="服务健康检查")
async def get_health(service: HealthServiceDependency) -> HealthResponse:
    health_status = service.get_status()
    return HealthResponse(
        status=health_status.status,
        service=health_status.service,
        version=health_status.version,
    )
