from enum import IntEnum
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, StatisticsServiceDependency
from app.schemas.statistics import (
    DailyCountResponse,
    ProjectStatisticsResponse,
    ProjectStatusCountResponse,
    TechnologyDimensionResponse,
    TechnologyItemResponse,
    TechnologyStatisticsResponse,
    TodayStatisticsResponse,
    TrendPointResponse,
    TrendStatisticsResponse,
)

router = APIRouter(prefix="/statistics", tags=["statistics"])
TimezoneOffset = Annotated[int, Query(ge=-720, le=840)]


class TrendRange(IntEnum):
    SEVEN_DAYS = 7
    THIRTY_DAYS = 30


TrendDays = Annotated[TrendRange, Query()]


@router.get("/today", response_model=TodayStatisticsResponse, summary="查询今日平台统计")
def get_today_statistics(
    current_user: CurrentUser,
    service: StatisticsServiceDependency,
    timezone_offset_minutes: TimezoneOffset = 480,
) -> TodayStatisticsResponse:
    del current_user
    return TodayStatisticsResponse.model_validate(
        service.get_today(timezone_offset_minutes), from_attributes=True
    )


@router.get("/trend", response_model=TrendStatisticsResponse, summary="查询平台趋势")
def get_trend_statistics(
    current_user: CurrentUser,
    service: StatisticsServiceDependency,
    days: TrendDays = TrendRange.SEVEN_DAYS,
    timezone_offset_minutes: TimezoneOffset = 480,
) -> TrendStatisticsResponse:
    del current_user
    data = service.get_trend(int(days), timezone_offset_minutes)
    return TrendStatisticsResponse(
        days=data.days,
        start_date=data.start_date,
        end_date=data.end_date,
        timezone_offset_minutes=data.timezone_offset_minutes,
        items=[TrendPointResponse.model_validate(item, from_attributes=True) for item in data.items],
    )


@router.get("/projects", response_model=ProjectStatisticsResponse, summary="查询项目统计")
def get_project_statistics(
    current_user: CurrentUser,
    service: StatisticsServiceDependency,
    days: TrendDays = TrendRange.THIRTY_DAYS,
    timezone_offset_minutes: TimezoneOffset = 480,
) -> ProjectStatisticsResponse:
    del current_user
    data = service.get_projects(int(days), timezone_offset_minutes)
    return ProjectStatisticsResponse(
        days=data.days,
        total=data.total,
        published=data.published,
        completed=data.completed,
        average_progress=data.average_progress,
        statuses=[
            ProjectStatusCountResponse.model_validate(item, from_attributes=True)
            for item in data.statuses
        ],
        completion_trend=[
            DailyCountResponse.model_validate(item, from_attributes=True)
            for item in data.completion_trend
        ],
    )


@router.get(
    "/tech-stacks",
    response_model=TechnologyStatisticsResponse,
    summary="查询技术栈统计",
)
def get_technology_statistics(
    current_user: CurrentUser,
    service: StatisticsServiceDependency,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> TechnologyStatisticsResponse:
    del current_user
    data = service.get_technology_stacks(limit)
    return TechnologyStatisticsResponse(
        total_projects=data.total_projects,
        dimensions=[
            TechnologyDimensionResponse(
                key=dimension.key,
                label=dimension.label,
                items=[
                    TechnologyItemResponse.model_validate(item, from_attributes=True)
                    for item in dimension.items
                ],
            )
            for dimension in data.dimensions
        ],
    )
