from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DatabaseSession
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import BatchDetail, BatchFilters, BatchPage, NoDetailFilters
from app.services.analytics import AnalyticsService
from app.repositories.learning import LearningRepository
from app.repositories.recommendation import RecommendationRepository
from app.schemas.practice_analytics import RecommendationApplicationCreate, RecommendationApplicationResponse
from app.services.learning import LearningService

router = APIRouter(prefix="/offline-analytics", tags=["offline-analytics"])


def get_analytics_service(session: DatabaseSession):
    return AnalyticsService(AnalyticsRepository(session))


AnalyticsDependency = Annotated[AnalyticsService, Depends(get_analytics_service)]


def get_recommendation_service(session: DatabaseSession):
    return LearningService(LearningRepository(session), RecommendationRepository(session))


RecommendationDependency = Annotated[LearningService, Depends(get_recommendation_service)]


@router.post("/batches/{batch_id}/recommendation-applications", response_model=RecommendationApplicationResponse,
             summary="本人审阅后将重复建议提醒创建为一次任务")
def apply_recommendation(batch_id: UUID, payload: RecommendationApplicationCreate,
                         current_user: CurrentUser, service: RecommendationDependency):
    return service.create_task_from_recommendation(current_user.id, payload, str(batch_id))


@router.get("/batches", response_model=BatchPage, summary="查询本人已完成离线分析批次")
def list_batches(current_user: CurrentUser, service: AnalyticsDependency, filters: Annotated[BatchFilters, Query()]):
    return service.list_batches(current_user.id, filters)


@router.get("/batches/{batch_id}", response_model=BatchDetail, summary="读取本人同批日汇总与专题")
def get_batch(batch_id: UUID, current_user: CurrentUser, service: AnalyticsDependency,
              filters: Annotated[NoDetailFilters, Query()]):
    return service.get_batch(current_user.id, batch_id)
