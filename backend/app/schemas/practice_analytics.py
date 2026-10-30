"""S10有界实践过程摘要；模型线索与本人审阅分列。"""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.practice import PracticeSessionStatus
from app.practice.review import CriterionId, IssueType
from app.schemas.learning import normalize_optional_text

Count = Annotated[int, Field(strict=True, ge=0, le=2**63-1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdviceReference(StrictModel):
    attempt_id: UUID
    attempt_no: int = Field(ge=1)
    operation_id: UUID
    ai_request_id: int = Field(ge=1)
    review_event_id: UUID
    issue_event_id: UUID
    criterion_id: CriterionId
    issue_type: IssueType
    prompt_version: str | None = Field(max_length=100)
    source: Literal["ai_report"] = "ai_report"


class PracticeSessionFact(StrictModel):
    session_id: UUID
    project_id: int = Field(ge=1)
    template_id: Literal["python-learning-csv"]
    template_version: Literal["1.0"]
    context_version: int = Field(ge=1)
    revision: int = Field(ge=1)
    current_step_key: Literal["understand", "implement"]
    status: PracticeSessionStatus
    created_at: datetime
    attempt_count: Count
    event_counts: dict[str, Count] = Field(max_length=20)
    latest_attempt_id: UUID | None
    latest_attempt_no: int | None = Field(ge=1)
    latest_operation_id: UUID | None
    latest_ai_request_id: int | None = Field(ge=1)
    personal_reviewed: bool
    self_statement: bool | None
    output_comparison: Literal["matched", "mismatched", "unknown"]
    teacher_confirmation: bool | None
    advice: list[AdviceReference] = Field(max_length=600)


class PracticeSummary(StrictModel):
    semantics: Literal["advisory_process"] = "advisory_process"
    cohort_rule: Literal["sessions_created_in_window;state_at_snapshot;events_in_window_before_cutoff"]
    observed_event_coverage_start: datetime | None
    coverage_basis: Literal["first_retained_owner_event"] = "first_retained_owner_event"
    session_count: Count
    attempt_count: Count
    no_submission_count: Count
    submission_event_count: Count
    personal_end_count: Count
    request_count: Count
    cancel_count: Count
    resume_count: Count
    teacher_confirmation_count: Count | None
    sessions: list[PracticeSessionFact] = Field(max_length=500)


class RecommendationCandidate(StrictModel):
    candidate_key: str = Field(max_length=255)
    rule_version: Literal["B-R1-advisory-1.0"]
    source: Literal["ai_report"]
    session_id: UUID
    project_id: int
    template_id: Literal["python-learning-csv"]
    template_version: Literal["1.0"]
    context_version: int
    session_revision: int
    attempt_id: UUID
    attempt_no: int
    criterion_id: CriterionId
    issue_type: IssueType
    references: list[AdviceReference] = Field(min_length=2, max_length=100)
    title: str
    explanation: str


class RecommendationApplicationCreate(StrictModel):
    request_key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    candidate_key: str = Field(min_length=1, max_length=255)
    expected_metric_version: Literal["learning-process-2.0"]
    expected_rule_version: Literal["B-R1-advisory-1.0"]
    expected_session_revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    scheduled_date: date
    project_id: int = Field(ge=1)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value):
        return normalize_optional_text(value)


class RecommendationApplicationResponse(StrictModel):
    application_id: UUID
    task_id: int
    batch_id: UUID
    candidate_key: str
    replayed: bool
    source_url: str
