import json
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from app.models.enums import LearningPlanStatus, RecordType, TaskPriority, TaskStatus

MAX_JSON_BYTES = 32_768


def normalize_optional_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


def limit_json(value: dict[str, JsonValue] | None) -> dict[str, JsonValue] | None:
    if value is not None:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
            raise ValueError("结构化内容不能超过 32768 字节")
    return value


class ResourceRefResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str


class PlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5_000)
    status: LearningPlanStatus = LearningPlanStatus.DRAFT
    start_date: date | None = None
    end_date: date | None = None
    goal_data: dict[str, JsonValue] | None = None
    project_id: int | None = Field(default=None, ge=1)
    course_id: int | None = Field(default=None, ge=1)

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return normalize_optional_text(value)

    @field_validator("goal_data")
    @classmethod
    def validate_goal_data(
        cls, value: dict[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        return limit_json(value)

    @model_validator(mode="after")
    def validate_date_range(self) -> "PlanCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("计划结束日期不能早于开始日期")
        return self


class PlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5_000)
    status: LearningPlanStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    goal_data: dict[str, JsonValue] | None = None
    project_id: int | None = Field(default=None, ge=1)
    course_id: int | None = Field(default=None, ge=1)

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return normalize_optional_text(value)

    @field_validator("goal_data")
    @classmethod
    def validate_goal_data(
        cls, value: dict[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        return limit_json(value)

    @model_validator(mode="after")
    def validate_changes(self) -> "PlanUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title 不能为 null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status 不能为 null")
        return self


class PlanResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    description: str | None
    status: LearningPlanStatus
    start_date: date | None
    end_date: date | None
    goal_data: dict[str, JsonValue] | None
    progress: int
    project: ResourceRefResponse | None
    course: ResourceRefResponse | None
    created_at: datetime
    updated_at: datetime


class PlanListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[PlanResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class LearningTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5_000)
    priority: TaskPriority = TaskPriority.MEDIUM
    scheduled_date: date
    start_time: time | None = None
    end_time: time | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1_440)
    plan_id: int | None = Field(default=None, ge=1)
    project_id: int | None = Field(default=None, ge=1)

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> "LearningTaskCreate":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class LearningTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5_000)
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    scheduled_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1_440)
    plan_id: int | None = Field(default=None, ge=1)
    project_id: int | None = Field(default=None, ge=1)

    @field_validator("title", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_changes(self) -> "LearningTaskUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in ("title", "priority", "status", "scheduled_date"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class LearningTaskResponse(BaseModel):
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
    plan: ResourceRefResponse | None
    project: ResourceRefResponse | None
    created_at: datetime
    updated_at: datetime


class LearningTaskListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[LearningTaskResponse]
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
    occurred_at: datetime | None = None
    project_id: int | None = Field(default=None, ge=1)
    course_id: int | None = Field(default=None, ge=1)
    task_id: int | None = Field(default=None, ge=1)
    record_metadata: dict[str, JsonValue] | None = None

    @field_validator("title", "content", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return normalize_optional_text(value)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("记录时间必须包含时区")
        return value

    @field_validator("record_metadata")
    @classmethod
    def validate_metadata(
        cls, value: dict[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        return limit_json(value)


class LearningRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, max_length=10_000)
    record_type: RecordType | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1_440)
    occurred_at: datetime | None = None
    project_id: int | None = Field(default=None, ge=1)
    course_id: int | None = Field(default=None, ge=1)
    task_id: int | None = Field(default=None, ge=1)
    record_metadata: dict[str, JsonValue] | None = None

    @field_validator("title", "content", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return normalize_optional_text(value)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        return LearningRecordCreate.require_timezone(value)

    @field_validator("record_metadata")
    @classmethod
    def validate_metadata(
        cls, value: dict[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        return limit_json(value)

    @model_validator(mode="after")
    def validate_changes(self) -> "LearningRecordUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in ("title", "record_type", "duration_minutes", "occurred_at"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class LearningRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    content: str | None
    record_type: RecordType
    duration_minutes: int
    occurred_at: datetime
    project: ResourceRefResponse | None
    course: ResourceRefResponse | None
    task: ResourceRefResponse | None
    record_metadata: dict[str, JsonValue] | None
    created_at: datetime


class LearningRecordListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[LearningRecordResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
