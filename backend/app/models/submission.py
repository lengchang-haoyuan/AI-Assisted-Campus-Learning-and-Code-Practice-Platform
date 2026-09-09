from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, MYSQL_TABLE_OPTIONS, TimestampMixin, UTCDateTime
from app.models.enums import enum_type


class SubmissionStatus(StrEnum):
    SUBMITTED = "submitted"
    RETURNED = "returned"
    ACCEPTED = "accepted"


class FeedbackDecision(StrEnum):
    ACCEPT = "accept"
    RETURN = "return"


class Submission(IdMixin, TimestampMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_membership_id", name="uq_submission_student"),
        UniqueConstraint("id", "class_id", name="uq_submission_class"),
        ForeignKeyConstraint(["assignment_id", "class_id"], ["teaching_assignments.id", "teaching_assignments.class_id"], name="fk_submission_assignment", ondelete="RESTRICT"),
        ForeignKeyConstraint(["student_membership_id", "class_id"], ["class_memberships.id", "class_memberships.class_id"], name="fk_submission_student", ondelete="RESTRICT"),
        ForeignKeyConstraint(["id", "latest_version_number"], ["submission_versions.submission_id", "submission_versions.version_number"], name="fk_submission_latest", use_alter=True, ondelete="RESTRICT"),
        Index("ix_submission_student_updated", "student_membership_id", "updated_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )
    class_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    assignment_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    student_membership_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    assignment_title: Mapped[str] = mapped_column(String(160), nullable=False)
    assignment_due_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    latest_version_number: Mapped[int | None] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class SubmissionVersion(IdMixin, Base):
    __tablename__ = "submission_versions"
    __table_args__ = (
        UniqueConstraint("submission_id", "version_number", name="uq_submission_version"),
        UniqueConstraint("submission_id", "request_key", name="uq_submission_request"),
        CheckConstraint("version_number >= 1", name="positive_version"),
        Index("ix_submission_version_status_time", "status", "submitted_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )
    submission_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("submissions.id", ondelete="RESTRICT"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[dict[str, str | int | None]] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    repository_url: Mapped[str | None] = mapped_column(String(1024))
    repository_ref: Mapped[str | None] = mapped_column(String(100))
    source_project_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("projects.id", ondelete="SET NULL"))
    source_project_title: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[SubmissionStatus] = mapped_column(enum_type(SubmissionStatus, name="submission_status", length=16), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class Feedback(IdMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("submission_id", "version_number", name="uq_feedback_version"),
        ForeignKeyConstraint(["submission_id", "version_number"], ["submission_versions.submission_id", "submission_versions.version_number"], name="fk_feedback_version", ondelete="RESTRICT"),
        ForeignKeyConstraint(["submission_id", "class_id"], ["submissions.id", "submissions.class_id"], name="fk_feedback_class", ondelete="RESTRICT"),
        ForeignKeyConstraint(["teacher_membership_id", "class_id"], ["class_memberships.id", "class_memberships.class_id"], name="fk_feedback_teacher", ondelete="RESTRICT"),
        Index("ix_feedback_teacher_created", "teacher_membership_id", "created_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )
    submission_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    class_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    teacher_membership_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    decision: Mapped[FeedbackDecision] = mapped_column(enum_type(FeedbackDecision, name="feedback_decision", length=16), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    learning_record_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("learning_records.id", ondelete="SET NULL"), unique=True)


class Notification(IdMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("recipient_user_id", "event_key", name="uq_notification_event"),
        CheckConstraint("kind IN ('assignment_published', 'feedback_created')", name="notification_kind"),
        Index("ix_notification_recipient_read_created", "recipient_user_id", "read_at", "created_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )
    recipient_user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_key: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    assignment_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("teaching_assignments.id", ondelete="RESTRICT"), nullable=False)
    feedback_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), ForeignKey("feedback.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
