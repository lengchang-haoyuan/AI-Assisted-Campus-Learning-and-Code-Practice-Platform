from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, MYSQL_TABLE_OPTIONS, UTCDateTime
from app.models.enums import AIRequestStatus, enum_type

if TYPE_CHECKING:
    from app.models.learning import LearningReport
    from app.models.project import Project
    from app.models.user import User
    from app.models.workflow import WorkflowRun


class AIRequest(IdMixin, Base):
    __tablename__ = "ai_requests"
    __table_args__ = (
        CheckConstraint("prompt_tokens IS NULL OR prompt_tokens >= 0", name="prompt_tokens_nonnegative"),
        CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0",
            name="completion_tokens_nonnegative",
        ),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="latency_nonnegative"),
        Index("ix_ai_requests_user_requested", "user_id", "requested_at"),
        Index("ix_ai_requests_project_status", "project_id", "status"),
        Index("ix_ai_requests_workflow_run", "workflow_run_id"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    workflow_run_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("workflow_runs.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[AIRequestStatus] = mapped_column(
        enum_type(AIRequestStatus, name="ai_request_status", length=16),
        nullable=False,
        server_default=AIRequestStatus.PENDING.value,
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_summary: Mapped[str | None] = mapped_column(String(500))
    request_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    prompt_tokens: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    completion_tokens: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    latency_ms: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    requested_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped["User"] = relationship(back_populates="ai_requests")
    project: Mapped["Project | None"] = relationship(back_populates="ai_requests")
    workflow_run: Mapped["WorkflowRun | None"] = relationship(
        back_populates="ai_requests"
    )
    result: Mapped["AIResult | None"] = relationship(
        back_populates="request", cascade="all, delete-orphan", passive_deletes=True
    )


class AIResult(IdMixin, Base):
    __tablename__ = "ai_results"
    __table_args__ = MYSQL_TABLE_OPTIONS

    request_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ai_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    result_type: Mapped[str] = mapped_column(String(50), nullable=False)
    structured_result: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON)
    text_summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    request: Mapped[AIRequest] = relationship(back_populates="result")
    learning_report: Mapped["LearningReport | None"] = relationship(
        back_populates="ai_result", passive_deletes=True
    )
