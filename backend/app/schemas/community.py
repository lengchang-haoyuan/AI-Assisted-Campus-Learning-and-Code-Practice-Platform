from datetime import datetime
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.community import (
    GovernanceActionType,
    GovernanceCaseStatus,
    GovernanceCaseType,
    PublicationKind,
    PublicationStatus,
)
from app.models.enums import ProjectDifficulty, ProjectStatus


REQUEST_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def normalize_text(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def validate_request_key(value: object) -> object:
    normalized = normalize_text(value)
    if isinstance(normalized, str) and not REQUEST_KEY_PATTERN.fullmatch(normalized):
        raise ValueError("请求键只能包含字母、数字、下划线和连字符")
    return normalized


class TagResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    name: str
    slug: str


class TagSummaryResponse(TagResponse):
    project_count: int


class CommunityOwnerResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    username: str
    avatar_url: str | None


class CommunityProjectResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    publication_id: int
    publication_kind: PublicationKind
    publication_status: PublicationStatus
    publication_version: int
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    status: ProjectStatus
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
    repository_url: str | None
    attribution: str | None
    source_license_statement: str | None
    ai_assistance_statement: str | None
    human_review_statement: str | None
    owner: CommunityOwnerResponse
    tags: list[TagResponse]
    published_at: datetime
    updated_at: datetime
    view_count: int
    comment_count: int
    like_count: int
    favorite_count: int
    liked: bool
    favorited: bool


class CommunityProjectListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[CommunityProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=2_000)
    _normalize_content = field_validator("content", mode="before")(normalize_text)


class CommentAuthorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    username: str
    avatar_url: str | None


class CommentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    project_id: int
    author: CommentAuthorResponse
    content: str
    revision: int
    created_at: datetime
    updated_at: datetime
    can_delete: bool
    can_report: bool


class CommentListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[CommentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class InteractionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    active: bool
    count: int


class ViewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    view_count: int


class PublishProjectRequest(BaseModel):
    """旧发布接口保留请求校验，但不再执行即时公开。"""

    model_config = ConfigDict(extra="forbid")
    tags: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_tag in value:
            tag = raw_tag.strip()
            if not tag or len(tag) > 50:
                raise ValueError("标签长度必须为 1 到 50 个字符")
            key = tag.casefold()
            if key not in seen:
                normalized.append(tag)
                seen.add(key)
        return normalized


class PublicationRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=8, max_length=64)
    expected_project_updated_at: datetime
    kind: PublicationKind = PublicationKind.WORK
    tags: list[str] = Field(default_factory=list, max_length=5)
    attribution: str = Field(min_length=1, max_length=160)
    source_license_statement: str = Field(min_length=1, max_length=500)
    ai_assistance_statement: str = Field(min_length=1, max_length=1_000)
    human_review_statement: str | None = Field(default=None, max_length=1_000)
    _validate_key = field_validator("request_key", mode="before")(validate_request_key)
    _normalize_required = field_validator(
        "attribution", "source_license_statement", "ai_assistance_statement", mode="before"
    )(normalize_text)

    @field_validator("human_review_statement", mode="before")
    @classmethod
    def normalize_optional_review(cls, value: object) -> object:
        normalized = normalize_text(value)
        return normalized or None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return PublishProjectRequest.normalize_tags(value)

    @field_validator("expected_project_updated_at")
    @classmethod
    def require_project_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("项目更新时间必须包含时区")
        return value

    @model_validator(mode="after")
    def validate_template_review(self) -> "PublicationRequestCreate":
        if self.kind == PublicationKind.PRACTICE_TEMPLATE and not self.human_review_statement:
            raise ValueError("实践项目模板必须填写人工审阅说明")
        return self


class PublicationWithdrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)
    _normalize_reason = field_validator("reason", mode="before")(normalize_text)


class PublicationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    decision: Literal["approve", "return", "take_down"]
    reason: str = Field(min_length=3, max_length=500)
    _normalize_reason = field_validator("reason", mode="before")(normalize_text)


class GovernanceReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=8, max_length=64)
    target_type: Literal["project", "comment"]
    target_id: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)
    _validate_key = field_validator("request_key", mode="before")(validate_request_key)
    _normalize_reason = field_validator("reason", mode="before")(normalize_text)


class GovernanceAppealCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=8, max_length=64)
    reason: str = Field(min_length=3, max_length=500)
    _validate_key = field_validator("request_key", mode="before")(validate_request_key)
    _normalize_reason = field_validator("reason", mode="before")(normalize_text)


class GovernanceCaseDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    decision: Literal["accept", "reject"]
    reason: str = Field(min_length=3, max_length=500)
    _normalize_reason = field_validator("reason", mode="before")(normalize_text)


class PublicationVersionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    version_number: int
    kind: PublicationKind
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    project_status: ProjectStatus
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
    repository_url: str | None
    tags: list[str]
    attribution: str | None
    source_license_statement: str | None
    ai_assistance_statement: str | None
    human_review_statement: str | None
    submitted_at: datetime


class GovernanceActionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    action: GovernanceActionType
    actor_user_id: int | None
    publication_id: int | None
    publication_version_number: int | None
    comment_id: int | None
    from_status: str | None
    to_status: str
    reason: str
    occurred_at: datetime


class PublicationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    project_id: int | None
    owner_user_id: int
    kind: PublicationKind
    status: PublicationStatus
    public_version_number: int | None
    pending_version_number: int | None
    revision: int
    submitted_at: datetime | None
    reviewed_at: datetime | None
    published_at: datetime | None
    withdrawn_at: datetime | None
    taken_down_at: datetime | None
    public_version: PublicationVersionResponse | None
    pending_version: PublicationVersionResponse | None
    actions: list[GovernanceActionResponse] = Field(default_factory=list)


class PublicationPageResponse(BaseModel):
    items: list[PublicationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class GovernanceCaseResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    case_type: GovernanceCaseType
    opened_by_user_id: int | None
    target_owner_user_id: int
    target_type: Literal["project", "comment", "action"]
    publication_id: int | None
    publication_version_number: int | None
    comment_id: int | None
    target_action_id: int | None
    reason: str | None
    target_excerpt: str
    status: GovernanceCaseStatus
    resolution_reason: str | None
    resolved_action_id: int | None
    revision: int
    created_at: datetime
    resolved_at: datetime | None


class GovernanceCasePageResponse(BaseModel):
    items: list[GovernanceCaseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
