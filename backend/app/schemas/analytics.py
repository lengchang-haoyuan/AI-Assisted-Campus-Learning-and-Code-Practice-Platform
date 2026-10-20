from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(strict=True, ge=0, le=2**63-1)]
Kind = Literal["business", "controlled"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ratio(StrictModel):
    numerator: Count
    denominator: Count
    percent: str | None = Field(pattern=r"^\d+\.\d{6}$")
    display: str = Field(max_length=30)


class RecordsSummary(StrictModel):
    valid_unique_rows: Count
    known_minutes: Count
    known_duration_count: Count
    missing_duration_count: Count
    known_zero_count: Count
    active_days: Count
    trusted_teaching_count: Count
    unverified_claim_count: Count
    ordinary_count: Count
    raw_rows: Count
    exact_duplicates: Count


class TasksSummary(StrictModel):
    total: Count
    completed: Count
    cancelled: Count
    overdue_unfinished: Count
    completion_rate: Ratio


class TopicSummary(StrictModel):
    cohort_count: Count
    revised_count: Count
    confirmed_count: Count
    returned_ever_count: Count
    first_pass_confirmed_count: Count
    revised_confirmed_count: Count
    pending_latest_count: Count
    revision_attempts: Count
    first_review_covered: Count
    first_review_wait_sum_minutes: float = Field(ge=0, allow_inf_nan=False)
    first_review_wait_mean_minutes: str | None = Field(pattern=r"^\d+\.\d{6}$")
    missing_teaching_record_links: Count
    revised_rate: Ratio
    confirmation_rate: Ratio
    revised_confirmation_rate: Ratio
    first_review_histogram: dict[str, Count]


class DailyMetric(StrictModel):
    metric_date: date
    records: Count
    known_minutes: Count
    known_duration_count: Count
    missing_duration_count: Count
    known_zero_count: Count
    ordinary_count: Count
    trusted_teaching_count: Count
    unverified_claim_count: Count
    task_total: Count
    completed: Count
    cancelled: Count
    overdue_unfinished: Count
    cohort_count: Count
    revised_count: Count
    confirmed_count: Count


class PublicationPayload(StrictModel):
    dataset_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    snapshot_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    job_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    owner_user_id: int = Field(strict=True, ge=1)
    dataset_kind: Kind
    period_start: date
    period_end: date
    business_timezone: Literal["Asia/Shanghai"]
    source_cutoff: datetime
    schema_version: Literal["scholarhub-source-1.0"]
    metric_version: Literal["learning-process-1.0"]
    rule_version: Literal["quality-1.0"]
    source_counts: dict[str, Count]
    quality: dict[str, Count | bool]
    records_summary: RecordsSummary
    tasks_summary: TasksSummary
    topic_summary: TopicSummary
    daily: list[DailyMetric] = Field(max_length=90)

    @model_validator(mode="after")
    def require_window(self):
        if self.period_end < self.period_start or (self.period_end-self.period_start).days >= 90:
            raise ValueError("分析窗口必须为1至90天")
        if self.source_cutoff.tzinfo is None or self.source_cutoff.utcoffset() is None:
            raise ValueError("截点必须带时区")
        return self


class BatchFilters(StrictModel):
    dataset_kind: Kind = "business"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("起止日期需要一起提供")
        if self.period_start is not None and (self.period_end < self.period_start or (self.period_end-self.period_start).days >= 90):
            raise ValueError("查询窗口必须为1至90天")
        return self


class NoDetailFilters(StrictModel):
    pass


class BatchInfo(StrictModel):
    batch_id: UUID
    dataset_kind: Kind
    period_start: date
    period_end: date
    business_timezone: str
    source_cutoff: datetime
    schema_version: str
    metric_version: str
    rule_version: str
    published_at: datetime


class BatchPage(StrictModel):
    items: list[BatchInfo]
    total: int
    page: int
    page_size: int
    empty_reason: Literal["no_completed_batch", "no_matching_batch", "page_empty"] | None = None


class BatchDetail(BatchInfo):
    source: dict[str, str]
    records_summary: RecordsSummary
    tasks_summary: TasksSummary
    topic_summary: TopicSummary
    quality: dict[str, Count | bool]
    daily: list[DailyMetric]
