from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DatabaseSession
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import BatchDetail, BatchFilters, BatchPage, NoDetailFilters
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/offline-analytics", tags=["offline-analytics"])


def get_analytics_service(session: DatabaseSession):
    return AnalyticsService(AnalyticsRepository(session))


AnalyticsDependency = Annotated[AnalyticsService, Depends(get_analytics_service)]


@router.get("/batches", response_model=BatchPage, summary="查询本人已完成离线分析批次")
def list_batches(current_user: CurrentUser, service: AnalyticsDependency, filters: Annotated[BatchFilters, Query()]):
    return service.list_batches(current_user.id, filters)


@router.get("/batches/{batch_id}", response_model=BatchDetail, summary="读取本人同批日汇总与专题")
def get_batch(batch_id: UUID, current_user: CurrentUser, service: AnalyticsDependency,
              filters: Annotated[NoDetailFilters, Query()]):
    return service.get_batch(current_user.id, batch_id)
