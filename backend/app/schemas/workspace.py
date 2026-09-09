from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    ProjectDifficulty,
    ProjectStatus,
    RecordType,
    TaskPriority,
    TaskStatus,
)


class WorkspaceProjectRefResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5_000)
    priority: TaskPriority = TaskPriority.MEDIUM
    scheduled_date: date
    start_time: time | None = None
    end_time: time | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1_440)
    project_id: int | None = Field(default=None, ge=1)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_time_range(self) -> "TaskCreate":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class TaskResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    description: str | None
    priority: TaskPriority
    status: TaskStatus
    scheduled_date: date
    start_time: time | None
    end_time: time | None
    estimated_minutes: int | None
    completed_at: datetime | None
    project: WorkspaceProjectRefResponse | None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class LearningRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    content: str | None = Field(default=None, max_length=10_000)
    record_type: RecordType
    duration_minutes: int = Field(ge=1, le=1_440)
    project_id: int | None = Field(default=None, ge=1)
    occurred_at: datetime | None = None

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("记录时间必须包含时区")
        return value


class LearningRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    content: str | None
    record_type: RecordType
    duration_minutes: int | None
    occurred_at: datetime
    project: WorkspaceProjectRefResponse | None
    created_at: datetime


class LearningRecordListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[LearningRecordResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class WorkspaceProjectResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    status: ProjectStatus
    language: str | None
    progress: int
    linked_task_count: int
    completed_task_count: int
    recorded_minutes: int
    updated_at: datetime


class WorkspaceProjectListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[WorkspaceProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class WorkspaceProjectDetailResponse(WorkspaceProjectResponse):
    recent_tasks: list[TaskResponse]
    recent_records: list[LearningRecordResponse]


class WorkspaceStatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    today_task_total: int
    today_task_completed: int
    today_estimated_minutes: int
    today_recorded_minutes: int
    learning_progress: int
    project_total: int
    active_project_total: int


class WorkspaceDashboardResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    stats: WorkspaceStatsResponse
    today_tasks: list[TaskResponse]
    recent_projects: list[WorkspaceProjectResponse]
    recent_records: list[LearningRecordResponse]
