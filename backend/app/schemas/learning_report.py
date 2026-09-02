from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.learning_report_schemas import LearningReportStructuredData
from app.models.enums import ReportStatus


class LearningReportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    timezone_offset_minutes: int = Field(default=480, ge=-720, le=840)

    @model_validator(mode="after")
    def validate_period(self) -> "LearningReportCreateRequest":
        if self.period_end < self.period_start:
            raise ValueError("结束日期不能早于开始日期")
        if (self.period_end - self.period_start).days + 1 > 90:
            raise ValueError("报告周期不能超过 90 天")
        return self


class LearningReportErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class LearningReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    period_start: date
    period_end: date
    status: ReportStatus
    summary: str | None
    achievement: list[str]
    problems: list[str]
    suggestions: list[str]
    structured_data: LearningReportStructuredData | None
    error: LearningReportErrorResponse | None
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LearningReportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LearningReportResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)
