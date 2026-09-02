from datetime import date
from typing import Literal

from pydantic import Field

from app.agents.schemas import AgentSchema


class LearningActivityMetrics(AgentSchema):
    record_count: int = Field(ge=0)
    total_minutes: int = Field(ge=0)
    active_days: int = Field(ge=0)
    by_type: dict[str, int]


class TaskActivityMetrics(AgentSchema):
    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=100)


class ProjectActivityMetrics(AgentSchema):
    total: int = Field(ge=0)
    published: int = Field(ge=0)
    completed: int = Field(ge=0)
    average_progress: float = Field(ge=0, le=100)
    by_status: dict[str, int]


class WorkflowActivityMetrics(AgentSchema):
    total_runs: int = Field(ge=0)
    completed_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    success_rate: float = Field(ge=0, le=100)


class AIActivityMetrics(AgentSchema):
    request_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class CommunityActivityMetrics(AgentSchema):
    comments: int = Field(ge=0)
    likes: int = Field(ge=0)
    favorites: int = Field(ge=0)
    project_views: int = Field(ge=0)


class LearningReportSource(AgentSchema):
    period_start: date
    period_end: date
    timezone_offset_minutes: int = Field(ge=-720, le=840)
    learning: LearningActivityMetrics
    tasks: TaskActivityMetrics
    projects: ProjectActivityMetrics
    workflows: WorkflowActivityMetrics
    ai_usage: AIActivityMetrics
    community: CommunityActivityMetrics


class LearningReportStructuredData(AgentSchema):
    performance_level: Literal["starting", "steady", "strong", "excellent"]
    total_learning_minutes: int = Field(ge=0)
    active_days: int = Field(ge=0)
    task_completion_rate: float = Field(ge=0, le=100)
    project_average_progress: float = Field(ge=0, le=100)
    workflow_success_rate: float = Field(ge=0, le=100)
    ai_request_count: int = Field(ge=0)
    focus_areas: list[str] = Field(default_factory=list, max_length=8)
    recommended_weekly_minutes: int = Field(ge=0, le=10080)


class LearningReportResult(AgentSchema):
    result_type: Literal["learning_report"]
    summary: str = Field(min_length=1, max_length=2000)
    achievement: list[str] = Field(default_factory=list, max_length=10)
    problems: list[str] = Field(default_factory=list, max_length=10)
    suggestions: list[str] = Field(default_factory=list, max_length=10)
    structured_data: LearningReportStructuredData
