from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    service: str
    version: str


@router.get("", response_model=HealthResponse, summary="服务健康检查")
async def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )

