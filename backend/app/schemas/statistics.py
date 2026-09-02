from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProjectStatus


class StatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TodayStatisticsResponse(StatisticsResponse):
    date: date
    timezone_offset_minutes: int
    visitors: int = Field(ge=0)
    completed_task_users: int = Field(ge=0)
    project_total: int = Field(ge=0)
    published_project_total: int = Field(ge=0)
    projects_created: int = Field(ge=0)
    projects_published: int = Field(ge=0)
    community_interactions: int = Field(ge=0)


class TrendPointResponse(StatisticsResponse):
    date: date
    visitors: int = Field(ge=0)
    completed_task_users: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    projects_created: int = Field(ge=0)
    projects_completed: int = Field(ge=0)
    projects_published: int = Field(ge=0)
    community_interactions: int = Field(ge=0)


class TrendStatisticsResponse(StatisticsResponse):
    days: Literal[7, 30]
    start_date: date
    end_date: date
    timezone_offset_minutes: int
    items: list[TrendPointResponse]


class ProjectStatusCountResponse(StatisticsResponse):
    status: ProjectStatus
    count: int = Field(ge=0)


class DailyCountResponse(StatisticsResponse):
    date: date
    count: int = Field(ge=0)


class ProjectStatisticsResponse(StatisticsResponse):
    days: Literal[7, 30]
    total: int = Field(ge=0)
    published: int = Field(ge=0)
    completed: int = Field(ge=0)
    average_progress: float = Field(ge=0, le=100)
    statuses: list[ProjectStatusCountResponse]
    completion_trend: list[DailyCountResponse]


class TechnologyItemResponse(StatisticsResponse):
    name: str
    count: int = Field(ge=0)
    percentage: float = Field(ge=0, le=100)


class TechnologyDimensionResponse(StatisticsResponse):
    key: Literal["language", "framework", "frontend", "backend", "database"]
    label: str
    items: list[TechnologyItemResponse]


class TechnologyStatisticsResponse(StatisticsResponse):
    total_projects: int = Field(ge=0)
    dimensions: list[TechnologyDimensionResponse]
