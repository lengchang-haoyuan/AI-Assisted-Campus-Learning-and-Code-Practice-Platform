from datetime import datetime
import re
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.submission import FeedbackDecision, SubmissionStatus


ALLOWED_REPOSITORY_HOSTS = {"github.com", "gitlab.com", "gitee.com"}
REQUEST_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def normalize_optional_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


class SubmissionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_key: str = Field(min_length=8, max_length=64)
    expected_latest_version: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=8000)
    repository_url: str | None = Field(default=None, max_length=1024)
    repository_ref: str | None = Field(default=None, max_length=100)
    source_project_id: int | None = Field(default=None, ge=1)

    @field_validator("request_key", mode="before")
    @classmethod
    def validate_request_key(cls, value: object) -> object:
        value = value.strip() if isinstance(value, str) else value
        if isinstance(value, str) and not REQUEST_KEY_PATTERN.fullmatch(value):
            raise ValueError("请求标识只能包含字母、数字、下划线和短横线")
        return value

    _normalize_summary = field_validator("summary", mode="before")(
        lambda value: value.strip() if isinstance(value, str) else value
    )
    _normalize_optional = field_validator(
        "repository_url", "repository_ref", mode="before"
    )(normalize_optional_text)

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("仓库链接端口无效") from exc
        if (
            parsed.scheme.lower() != "https"
            or parsed.hostname is None
            or parsed.hostname.lower() not in ALLOWED_REPOSITORY_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
            or parsed.query
            or parsed.fragment
            or len([part for part in parsed.path.split("/") if part]) < 2
        ):
            raise ValueError("仓库链接必须是 GitHub、GitLab 或 Gitee 的 HTTPS 仓库地址")
        hostname = parsed.hostname.lower()
        path = parsed.path.rstrip("/")
        return urlunsplit(("https", hostname, path, "", ""))


class FeedbackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    decision: FeedbackDecision
    comment: str = Field(min_length=1, max_length=4000)

    _normalize_comment = field_validator("comment", mode="before")(
        lambda value: value.strip() if isinstance(value, str) else value
    )


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    decision: FeedbackDecision
    comment: str
    created_at: datetime


class SubmissionVersionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    version_number: int
    summary: str
    repository_url: str | None
    repository_ref: str | None
    source_project_title: str | None
    has_project_reference: bool
    status: SubmissionStatus
    submitted_at: datetime
    reviewed_at: datetime | None
    revision: int
    feedback: FeedbackResponse | None


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    class_id: int
    assignment_id: int
    assignment_title: str
    assignment_due_at: datetime
    student_username: str
    latest_version_number: int
    revision: int
    created_at: datetime
    updated_at: datetime
    latest_version: SubmissionVersionResponse
    can_review: bool
    can_submit_next: bool
    is_owner: bool


class SubmissionPageResponse(BaseModel):
    items: list[SubmissionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SubmissionVersionPageResponse(BaseModel):
    items: list[SubmissionVersionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PendingAssignmentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    class_id: int
    title: str
    due_at: datetime
    submission_id: int | None
    current_status: SubmissionStatus | None


class PendingAssignmentPageResponse(BaseModel):
    items: list[PendingAssignmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class NotificationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    kind: str
    assignment_id: int | None
    feedback_id: int | None
    submission_id: int | None
    community_publication_id: int | None
    community_case_id: int | None
    created_at: datetime
    read_at: datetime | None


class NotificationPageResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int
