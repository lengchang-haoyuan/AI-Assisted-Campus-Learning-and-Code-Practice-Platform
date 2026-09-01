import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from app.models.enums import CourseStatus

MAX_SCHEDULE_BYTES = 32_768


class CourseFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=5_000)
    instructor: str | None = Field(default=None, max_length=100)
    schedule_data: dict[str, JsonValue] | None = None
    status: CourseStatus = CourseStatus.ACTIVE

    @field_validator("name", "code", "description", "instructor", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("schedule_data")
    @classmethod
    def limit_schedule_size(
        cls, value: dict[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        if value is not None:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > MAX_SCHEDULE_BYTES:
                raise ValueError("课程安排不能超过 32768 字节")
        return value


class CourseCreate(CourseFields):
    pass


class CourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=5_000)
    instructor: str | None = Field(default=None, max_length=100)
    schedule_data: dict[str, JsonValue] | None = None
    status: CourseStatus | None = None

    @field_validator("name", "code", "description", "instructor", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return CourseFields.normalize_text(value)

    @field_validator("schedule_data")
    @classmethod
    def limit_schedule_size(
        cls, value: dict[str, JsonValue] | None
    ) -> dict[str, JsonValue] | None:
        return CourseFields.limit_schedule_size(value)

    @model_validator(mode="after")
    def validate_changes(self) -> "CourseUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name 不能为 null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status 不能为 null")
        return self


class CourseResponse(CourseFields):
    model_config = ConfigDict(frozen=True)

    id: int
    created_at: datetime
    updated_at: datetime


class CourseListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[CourseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
