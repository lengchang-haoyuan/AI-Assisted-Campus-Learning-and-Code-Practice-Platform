from datetime import date, datetime, time
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    IdMixin,
    MYSQL_TABLE_OPTIONS,
    TimestampMixin,
    UTCDateTime,
)
from app.models.enums import (
    LearningPlanStatus,
    RecordType,
    ReportStatus,
    TaskPriority,
    TaskStatus,
    enum_type,
)

if TYPE_CHECKING:
    from app.models.ai import AIResult
    from app.models.course import Course
    from app.models.project import Project
    from app.models.user import User


class LearningPlan(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_plans"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="valid_date_range",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="progress_range"),
        Index("ix_learning_plans_user_status", "user_id", "status"),
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
    course_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("courses.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LearningPlanStatus] = mapped_column(
        enum_type(LearningPlanStatus, name="learning_plan_status", length=16),
        nullable=False,
        server_default=LearningPlanStatus.DRAFT.value,
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    goal_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    progress: Mapped[int] = mapped_column(
        SMALLINT(unsigned=True), nullable=False, server_default=text("0")
    )

    user: Mapped["User"] = relationship(back_populates="learning_plans")
    project: Mapped["Project | None"] = relationship(back_populates="learning_plans")
    course: Mapped["Course | None"] = relationship(back_populates="learning_plans")
    daily_tasks: Mapped[list["DailyTask"]] = relationship(
        back_populates="plan", passive_deletes=True
    )


class DailyTask(IdMixin, TimestampMixin, Base):
    __tablename__ = "daily_tasks"
    __table_args__ = (
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes >= 0",
            name="estimated_minutes_nonnegative",
        ),
        CheckConstraint(
            "end_time IS NULL OR start_time IS NULL OR end_time > start_time",
            name="valid_time_range",
        ),
        Index("ix_daily_tasks_user_schedule", "user_id", "scheduled_date", "status"),
        Index("ix_daily_tasks_plan_status", "plan_id", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("learning_plans.id", ondelete="SET NULL")
    )
    project_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[TaskPriority] = mapped_column(
        enum_type(TaskPriority, name="task_priority", length=8),
        nullable=False,
        server_default=TaskPriority.MEDIUM.value,
    )
    status: Mapped[TaskStatus] = mapped_column(
        enum_type(TaskStatus, name="task_status", length=16),
        nullable=False,
        server_default=TaskStatus.PENDING.value,
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    estimated_minutes: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped["User"] = relationship(back_populates="daily_tasks")
    plan: Mapped[LearningPlan | None] = relationship(back_populates="daily_tasks")
    project: Mapped["Project | None"] = relationship(back_populates="daily_tasks")
    learning_records: Mapped[list["LearningRecord"]] = relationship(
        back_populates="task", passive_deletes=True
    )


class LearningRecord(IdMixin, Base):
    __tablename__ = "learning_records"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 0",
            name="duration_nonnegative",
        ),
        Index("ix_learning_records_user_occurred", "user_id", "occurred_at"),
        Index("ix_learning_records_project_type", "project_id", "record_type"),
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
    course_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("courses.id", ondelete="SET NULL")
    )
    task_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("daily_tasks.id", ondelete="SET NULL")
    )
    record_type: Mapped[RecordType] = mapped_column(
        enum_type(RecordType, name="record_type", length=16), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int | None] = mapped_column(INTEGER(unsigned=True))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    record_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    user: Mapped["User"] = relationship(back_populates="learning_records")
    project: Mapped["Project | None"] = relationship(back_populates="learning_records")
    course: Mapped["Course | None"] = relationship(back_populates="learning_records")
    task: Mapped[DailyTask | None] = relationship(back_populates="learning_records")


class LearningReport(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_reports"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "period_start", "period_end", name="uq_reports_user_period"
        ),
        CheckConstraint("period_end >= period_start", name="valid_period"),
        Index("ix_learning_reports_user_created", "user_id", "created_at"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ai_result_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ai_results.id", ondelete="SET NULL"),
        unique=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        enum_type(ReportStatus, name="report_status", length=16),
        nullable=False,
        server_default=ReportStatus.PENDING.value,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[list[Any] | None] = mapped_column(JSON)
    problems: Mapped[list[Any] | None] = mapped_column(JSON)
    suggestions: Mapped[list[Any] | None] = mapped_column(JSON)
    structured_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    user: Mapped["User"] = relationship(back_populates="learning_reports")
    ai_result: Mapped["AIResult | None"] = relationship(
        back_populates="learning_report"
    )
