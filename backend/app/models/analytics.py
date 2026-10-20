"""已发布离线分析；现有业务表不承担分析批次状态。"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import CHAR, JSON, CheckConstraint, Date, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, MYSQL_TABLE_OPTIONS, UTCDateTime


class AnalyticsBatch(Base):
    __tablename__ = "analytics_batches"
    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="valid_period"),
        CheckConstraint("dataset_kind IN ('business','controlled')", name="publishable_kind"),
        CheckConstraint("state IN ('prepared','failed','completed')", name="valid_state"),
        UniqueConstraint("owner_user_id", "artifact_ref", "metric_version", "rule_version", name="uq_analytics_source_identity"),
        Index("ix_analytics_owner_state_cutoff", "owner_user_id", "state", "source_cutoff", "batch_id"),
        MYSQL_TABLE_OPTIONS,
    )
    batch_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    business_timezone: Mapped[str] = mapped_column(String(40), nullable=False)
    source_cutoff: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    input_counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    quality: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    topic_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    artifact_ref: Mapped[str] = mapped_column(String(255, collation="utf8mb4_bin"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)"))
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class AnalyticsDailyMetric(Base):
    __tablename__ = "analytics_daily_metrics"
    __table_args__ = (
        CheckConstraint("completed <= task_total AND cancelled <= task_total", name="task_counts_valid"),
        CheckConstraint("known_duration_count + missing_duration_count = records", name="record_coverage_valid"),
        CheckConstraint("ordinary_count + trusted_teaching_count + unverified_claim_count = records", name="source_counts_valid"),
        MYSQL_TABLE_OPTIONS,
    )
    batch_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("analytics_batches.batch_id", ondelete="RESTRICT"), primary_key=True)
    metric_date: Mapped[date] = mapped_column(Date, primary_key=True)
    records: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    known_minutes: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    known_duration_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    missing_duration_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    known_zero_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    ordinary_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    trusted_teaching_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    unverified_claim_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    task_total: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    completed: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    cancelled: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    overdue_unfinished: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    cohort_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    revised_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    confirmed_count: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
