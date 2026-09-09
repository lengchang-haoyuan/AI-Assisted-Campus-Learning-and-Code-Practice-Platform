from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, MYSQL_TABLE_OPTIONS, TimestampMixin, UTCDateTime
from app.models.enums import enum_type


class TeachingClassStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ClassMemberRole(StrEnum):
    TEACHER = "teacher"
    STUDENT = "student"


class ClassMembershipStatus(StrEnum):
    ACTIVE = "active"
    LEFT = "left"
    REMOVED = "removed"


class TeachingAssignmentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    ARCHIVED = "archived"


class TeachingClass(IdMixin, TimestampMixin, Base):
    __tablename__ = "teaching_classes"
    __table_args__ = (
        Index("ix_teaching_classes_status_id", "status", "id"),
        Index(
            "ix_teaching_classes_creator_status",
            "created_by_membership_id",
            "status",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    course_title: Mapped[str] = mapped_column(String(120), nullable=False)
    term_label: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[TeachingClassStatus] = mapped_column(
        enum_type(TeachingClassStatus, name="teaching_class_status", length=16),
        nullable=False,
        default=TeachingClassStatus.ACTIVE,
        server_default=TeachingClassStatus.ACTIVE.value,
    )
    created_by_membership_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("campus_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ClassMembership(IdMixin, TimestampMixin, Base):
    __tablename__ = "class_memberships"
    __table_args__ = (
        UniqueConstraint("id", "class_id", name="uq_class_member_class"),
        UniqueConstraint(
            "class_id",
            "campus_membership_id",
            name="uq_class_memberships_class_campus_membership",
        ),
        Index(
            "ix_class_memberships_member_status_class",
            "campus_membership_id",
            "status",
            "class_id",
        ),
        Index(
            "ix_class_memberships_class_status_role",
            "class_id",
            "status",
            "member_role",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    class_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("teaching_classes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    campus_membership_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("campus_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )
    member_role: Mapped[ClassMemberRole] = mapped_column(
        enum_type(ClassMemberRole, name="class_member_role", length=16),
        nullable=False,
    )
    status: Mapped[ClassMembershipStatus] = mapped_column(
        enum_type(
            ClassMembershipStatus,
            name="class_membership_status",
            length=16,
        ),
        nullable=False,
        default=ClassMembershipStatus.ACTIVE,
        server_default=ClassMembershipStatus.ACTIVE.value,
    )
    joined_by_membership_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("campus_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class TeachingAssignment(IdMixin, TimestampMixin, Base):
    __tablename__ = "teaching_assignments"
    __table_args__ = (
        UniqueConstraint("id", "class_id", name="uq_assignment_class"),
        Index(
            "ix_teaching_assignments_class_status_due",
            "class_id",
            "status",
            "due_at",
            "id",
        ),
        Index(
            "ix_teaching_assignments_class_published",
            "class_id",
            "published_at",
            "id",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    class_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("teaching_classes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_class_membership_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "class_memberships.id",
            ondelete="RESTRICT",
            name="fk_teaching_assignments_creator_member",
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    learning_objectives: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[TeachingAssignmentStatus] = mapped_column(
        enum_type(
            TeachingAssignmentStatus,
            name="teaching_assignment_status",
            length=16,
        ),
        nullable=False,
        default=TeachingAssignmentStatus.DRAFT,
        server_default=TeachingAssignmentStatus.DRAFT.value,
    )
    source_project_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
    )
    source_project_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
