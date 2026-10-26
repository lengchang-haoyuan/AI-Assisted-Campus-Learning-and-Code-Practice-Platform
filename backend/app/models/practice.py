"""固定模板实践会话；与旧工作流运行及离线分析批次隔离。"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, MYSQL_TABLE_OPTIONS, TimestampMixin, UTCDateTime
from app.models.enums import enum_type


class PracticeSessionStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    WAITING_SUBMISSION = "waiting_submission"
    WAITING_REVISION = "waiting_revision"
    WAITING_CONFIRMATION = "waiting_confirmation"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class PracticeSession(TimestampMixin, Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        CheckConstraint("context_version >= 1", name="context_version_positive"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "current_step_key IN ('understand','implement')", name="valid_step"
        ),
        Index("ix_practice_sessions_owner_created", "owner_user_id", "created_at", "id"),
        Index("ix_practice_sessions_project_status", "project_id", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    context_version: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    current_step_key: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="understand"
    )
    status: Mapped[PracticeSessionStatus] = mapped_column(
        enum_type(PracticeSessionStatus, name="practice_session_status", length=32),
        nullable=False,
        server_default=PracticeSessionStatus.READY.value,
    )
    revision: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("1")
    )
    active_operation_id: Mapped[str | None] = mapped_column(CHAR(36))
    active_action: Mapped[str | None] = mapped_column(String(32))
    active_ai_request_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ai_requests.id", ondelete="SET NULL")
    )
    # JSON字段使用整体赋值，避免原地修改绕过ORM变更跟踪。
    step_outputs: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )


class PracticeAttempt(TimestampMixin, Base):
    __tablename__ = "practice_attempts"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "step_key", "attempt_no", name="uq_practice_attempt_step_no"
        ),
        UniqueConstraint("session_id", "request_key", name="uq_practice_attempt_request"),
        UniqueConstraint("session_id", "id", name="uq_practice_attempt_session_id"),
        CheckConstraint("attempt_no >= 1", name="attempt_no_positive"),
        CheckConstraint("step_key = 'implement'", name="submission_step"),
        CheckConstraint("CHAR_LENGTH(code_text) <= 12000", name="code_length"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_no: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    request_key: Mapped[str] = mapped_column(
        String(64, collation="utf8mb4_bin"), nullable=False
    )
    code_text: Mapped[str] = mapped_column(Text, nullable=False)
    declared_output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    self_statement: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="submitted"
    )
    operation_id: Mapped[str | None] = mapped_column(CHAR(36))
    ai_request_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ai_requests.id", ondelete="SET NULL")
    )
    review_schema_version: Mapped[str | None] = mapped_column(String(64))
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PracticeEvent(Base):
    __tablename__ = "practice_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "attempt_id"],
            ["practice_attempts.session_id", "practice_attempts.id"],
            name="fk_practice_events_attempt_session",
            ondelete="CASCADE",
        ),
        UniqueConstraint("session_id", "event_key", name="uq_practice_event_key"),
        CheckConstraint(
            "criterion_id IS NULL OR criterion_id IN ('C01','C02','C03','C04','C05','C06')",
            name="valid_criterion",
        ),
        Index("ix_practice_events_session_time", "session_id", "occurred_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[str | None] = mapped_column(CHAR(36))
    event_key: Mapped[str] = mapped_column(
        String(160, collation="utf8mb4_bin"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    criterion_id: Mapped[str | None] = mapped_column(String(8))
    issue_type: Mapped[str | None] = mapped_column(String(64))
    confirmation_kind: Mapped[str | None] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
