import json
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from app.models.enums import ProjectDifficulty, ProjectStatus
from app.schemas.community import TagResponse

MAX_REQUIREMENTS_BYTES = 65_536
OPTIONAL_TEXT_FIELDS = (
    "description",
    "language",
    "framework",
    "frontend",
    "backend",
    "database",
    "output_requirement",
)
NON_NULL_UPDATE_FIELDS = ("name", "difficulty", "status")


class ProjectFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5_000)
    difficulty: ProjectDifficulty = ProjectDifficulty.BEGINNER
    language: str | None = Field(default=None, max_length=100)
    framework: str | None = Field(default=None, max_length=100)
    frontend: str | None = Field(default=None, max_length=100)
    backend: str | None = Field(default=None, max_length=100)
    database: str | None = Field(default=None, max_length=100)
    requirements: list[dict[str, JsonValue]] | None = Field(
        default=None, max_length=100
    )
    output_requirement: str | None = Field(default=None, max_length=10_000)
    status: ProjectStatus = ProjectStatus.NOT_STARTED

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(*OPTIONAL_TEXT_FIELDS, mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("requirements")
    @classmethod
    def limit_requirements_size(
        cls, value: list[dict[str, JsonValue]] | None
    ) -> list[dict[str, JsonValue]] | None:
        if value is not None:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > MAX_REQUIREMENTS_BYTES:
                raise ValueError("项目需求内容不能超过 65536 字节")
        return value


class ProjectCreate(ProjectFields):
    pass


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5_000)
    difficulty: ProjectDifficulty | None = None
    language: str | None = Field(default=None, max_length=100)
    framework: str | None = Field(default=None, max_length=100)
    frontend: str | None = Field(default=None, max_length=100)
    backend: str | None = Field(default=None, max_length=100)
    database: str | None = Field(default=None, max_length=100)
    requirements: list[dict[str, JsonValue]] | None = Field(
        default=None, max_length=100
    )
    output_requirement: str | None = Field(default=None, max_length=10_000)
    status: ProjectStatus | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(*OPTIONAL_TEXT_FIELDS, mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("requirements")
    @classmethod
    def limit_requirements_size(
        cls, value: list[dict[str, JsonValue]] | None
    ) -> list[dict[str, JsonValue]] | None:
        return ProjectFields.limit_requirements_size(value)

    @model_validator(mode="after")
    def validate_changes(self) -> "ProjectUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in NON_NULL_UPDATE_FIELDS:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class ProjectOwnerResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    username: str


class ProjectResponse(ProjectFields):
    model_config = ConfigDict(frozen=True)

    id: int
    owner: ProjectOwnerResponse
    tags: list[TagResponse]
    is_published: bool
    published_at: datetime | None
    view_count: int
    progress: int
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
