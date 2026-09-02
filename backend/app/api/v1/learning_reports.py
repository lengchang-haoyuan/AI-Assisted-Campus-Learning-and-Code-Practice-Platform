from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.deps import CurrentUser, LearningReportServiceDependency
from app.schemas.learning_report import (
    LearningReportCreateRequest,
    LearningReportErrorResponse,
    LearningReportListResponse,
    LearningReportResponse,
)
from app.services.learning_report import LearningReportData, LearningReportPage

router = APIRouter(prefix="/learning-reports", tags=["learning-reports"])
ReportId = Annotated[int, Path(ge=1)]


def to_report_response(data: LearningReportData) -> LearningReportResponse:
    return LearningReportResponse(
        id=data.id,
        period_start=data.period_start,
        period_end=data.period_end,
        status=data.status,
        summary=data.summary,
        achievement=data.achievement,
        problems=data.problems,
        suggestions=data.suggestions,
        structured_data=data.structured_data,
        error=(
            LearningReportErrorResponse(
                code=data.error.code,
                message=data.error.message,
            )
            if data.error is not None
            else None
        ),
        generated_at=data.generated_at,
        created_at=data.created_at,
        updated_at=data.updated_at,
    )


@router.post(
    "",
    response_model=LearningReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="生成当前用户的 AI 学习报告",
)
async def generate_learning_report(
    payload: LearningReportCreateRequest,
    current_user: CurrentUser,
    service: LearningReportServiceDependency,
) -> LearningReportResponse:
    return to_report_response(
        await service.generate(
            current_user.id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            timezone_offset_minutes=payload.timezone_offset_minutes,
        )
    )


@router.get("", response_model=LearningReportListResponse, summary="查询学习报告列表")
def list_learning_reports(
    current_user: CurrentUser,
    service: LearningReportServiceDependency,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> LearningReportListResponse:
    data: LearningReportPage = service.list_reports(
        current_user.id, page=page, page_size=page_size
    )
    return LearningReportListResponse(
        items=[to_report_response(item) for item in data.items],
        total=data.total,
        page=data.page,
        page_size=data.page_size,
        total_pages=data.total_pages,
    )


@router.get(
    "/{report_id}",
    response_model=LearningReportResponse,
    summary="查询学习报告详情",
)
def get_learning_report(
    report_id: ReportId,
    current_user: CurrentUser,
    service: LearningReportServiceDependency,
) -> LearningReportResponse:
    return to_report_response(service.get_report(report_id, current_user.id))
