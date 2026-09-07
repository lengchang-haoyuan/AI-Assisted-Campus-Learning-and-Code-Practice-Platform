from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.teaching import (
    ClassMemberRole,
    ClassMembershipStatus,
    TeachingAssignmentStatus,
    TeachingClassStatus,
)


def normalize_text(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def normalize_text_list(value: object) -> object:
    if not isinstance(value, list):
        return value
    return [item.strip() if isinstance(item, str) else item for item in value]


def ensure_aware_datetime(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("截止时间必须包含时区")
    return value


class TeachingClassCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    course_title: str = Field(min_length=2, max_length=120)
    term_label: str = Field(min_length=2, max_length=60)

    _normalize = field_validator(
        "name", "course_title", "term_label", mode="before"
    )(normalize_text)


class TeachingClassUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    course_title: str | None = Field(default=None, min_length=2, max_length=120)
    term_label: str | None = Field(default=None, min_length=2, max_length=60)
    status: TeachingClassStatus | None = None

    _normalize = field_validator(
        "name", "course_title", "term_label", mode="before"
    )(normalize_text)

    @model_validator(mode="after")
    def require_change(self) -> "TeachingClassUpdateRequest":
        if all(
            value is None
            for value in (self.name, self.course_title, self.term_label, self.status)
        ):
            raise ValueError("至少提交一个班级变更字段")
        return self


class TeachingClassResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    name: str
    course_title: str
    term_label: str
    status: TeachingClassStatus
    revision: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    viewer_role: Literal["administrator", "teacher", "student"]
    viewer_member_id: int | None
    viewer_member_revision: int | None
    can_edit: bool
    can_view_members: bool
    can_manage_members: bool
    can_create_assignments: bool


class TeachingClassPageResponse(BaseModel):
    items: list[TeachingClassResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ClassMemberCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campus_membership_id: int = Field(ge=1)
    member_role: ClassMemberRole


class ClassMemberUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    status: ClassMembershipStatus


class ClassMemberResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    campus_membership_id: int
    user_id: int
    username: str
    member_role: ClassMemberRole
    status: ClassMembershipStatus
    joined_at: datetime
    left_at: datetime | None
    revision: int


class ClassMemberPageResponse(BaseModel):
    items: list[ClassMemberResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TeachingAssignmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=160)
    instructions: str = Field(min_length=10, max_length=20_000)
    learning_objectives: list[str] = Field(min_length=1, max_length=20)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=30)
    due_at: datetime | None = None
    source_project_id: int | None = Field(default=None, ge=1)

    _normalize_text = field_validator("title", "instructions", mode="before")(
        normalize_text
    )
    _normalize_lists = field_validator(
        "learning_objectives", "acceptance_criteria", mode="before"
    )(normalize_text_list)
    _validate_due_at = field_validator("due_at")(ensure_aware_datetime)

    @field_validator("learning_objectives", "acceptance_criteria")
    @classmethod
    def validate_list_items(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("目标和交付要求每项需为 1 至 500 个字符")
        return value


class TeachingAssignmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=2, max_length=160)
    instructions: str | None = Field(default=None, min_length=10, max_length=20_000)
    learning_objectives: list[str] | None = Field(
        default=None, min_length=1, max_length=20
    )
    acceptance_criteria: list[str] | None = Field(
        default=None, min_length=1, max_length=30
    )
    due_at: datetime | None = None
    source_project_id: int | None = Field(default=None, ge=1)

    _normalize_text = field_validator("title", "instructions", mode="before")(
        normalize_text
    )
    _normalize_lists = field_validator(
        "learning_objectives", "acceptance_criteria", mode="before"
    )(normalize_text_list)
    _validate_due_at = field_validator("due_at")(ensure_aware_datetime)

    @field_validator("learning_objectives", "acceptance_criteria")
    @classmethod
    def validate_optional_list_items(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is not None and any(not item or len(item) > 500 for item in value):
            raise ValueError("目标和交付要求每项需为 1 至 500 个字符")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "TeachingAssignmentUpdateRequest":
        changed_fields = self.model_fields_set - {"expected_revision"}
        if not changed_fields:
            raise ValueError("至少提交一个任务变更字段")
        return self


class AssignmentTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class TeachingAssignmentResponse(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    class_id: int
    title: str
    instructions: str
    learning_objectives: list[str]
    acceptance_criteria: list[str]
    due_at: datetime | None
    status: TeachingAssignmentStatus
    source_project_snapshot: dict[str, Any] | None
    revision: int
    published_at: datetime | None
    closed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_publish: bool
    can_close: bool
    can_archive: bool


class TeachingAssignmentPageResponse(BaseModel):
    items: list[TeachingAssignmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
