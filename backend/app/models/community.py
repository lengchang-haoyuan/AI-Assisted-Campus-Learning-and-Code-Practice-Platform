from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    IdMixin,
    MYSQL_TABLE_OPTIONS,
    TimestampMixin,
    UTCDateTime,
)
from app.models.enums import ProjectDifficulty, ProjectStatus, enum_type

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class CommentModerationStatus(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"


class PublicationKind(StrEnum):
    WORK = "work"
    PRACTICE_TEMPLATE = "practice_template"


class PublicationStatus(StrEnum):
    LEGACY_REVIEW_REQUIRED = "legacy_review_required"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    RETURNED = "returned"
    WITHDRAWN = "withdrawn"
    TAKEN_DOWN = "taken_down"


class GovernanceActionType(StrEnum):
    APPLY = "apply"
    APPROVE = "approve"
    RETURN = "return"
    WITHDRAW = "withdraw"
    TAKE_DOWN = "take_down"
    RESTORE = "restore"
    HIDE_COMMENT = "hide_comment"
    RESTORE_COMMENT = "restore_comment"


class GovernanceCaseType(StrEnum):
    REPORT = "report"
    APPEAL = "appeal"


class GovernanceCaseStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Comment(IdMixin, TimestampMixin, Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_project_created", "project_id", "created_at"),
        Index(
            "ix_comments_project_moderation_created",
            "project_id",
            "moderation_status",
            "created_at",
            "id",
        ),
        Index("ix_comments_created_at", "created_at"),
        MYSQL_TABLE_OPTIONS,
    )

    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("0")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    moderation_status: Mapped[CommentModerationStatus] = mapped_column(
        enum_type(CommentModerationStatus, name="comment_moderation_status", length=16),
        nullable=False,
        default=CommentModerationStatus.VISIBLE,
        server_default=CommentModerationStatus.VISIBLE.value,
    )
    moderated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    project: Mapped["Project"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="comments")


class Like(IdMixin, Base):
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_likes_user_project"),
        Index("ix_likes_project_created", "project_id", "created_at"),
        Index("ix_likes_created_at", "created_at"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    user: Mapped["User"] = relationship(back_populates="likes")
    project: Mapped["Project"] = relationship(back_populates="likes")


class Favorite(IdMixin, Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_favorites_user_project"),
        Index("ix_favorites_project_created", "project_id", "created_at"),
        Index("ix_favorites_created_at", "created_at"),
        MYSQL_TABLE_OPTIONS,
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    user: Mapped["User"] = relationship(back_populates="favorites")
    project: Mapped["Project"] = relationship(back_populates="favorites")


class ProjectView(IdMixin, Base):
    __tablename__ = "project_views"
    __table_args__ = (
        Index("ix_project_views_viewed_user", "viewed_at", "user_id"),
        Index("ix_project_views_project_viewed", "project_id", "viewed_at"),
        MYSQL_TABLE_OPTIONS,
    )

    project_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    viewed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    project: Mapped["Project"] = relationship(back_populates="views")
    user: Mapped["User"] = relationship(back_populates="project_views")


class CommunityPublication(IdMixin, TimestampMixin, Base):
    __tablename__ = "community_publications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id", "public_version_number"],
            [
                "community_publication_versions.publication_id",
                "community_publication_versions.version_number",
            ],
            name="fk_publication_public_version",
            use_alter=True,
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["id", "pending_version_number"],
            [
                "community_publication_versions.publication_id",
                "community_publication_versions.version_number",
            ],
            name="fk_publication_pending_version",
            use_alter=True,
            ondelete="RESTRICT",
        ),
        Index("ix_publication_status_submitted", "status", "submitted_at", "id"),
        Index("ix_publication_owner_updated", "owner_user_id", "updated_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )

    project_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("projects.id", name="fk_publication_project", ondelete="SET NULL"),
        unique=True,
    )
    owner_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_publication_owner", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[PublicationKind] = mapped_column(
        enum_type(PublicationKind, name="community_publication_kind", length=24),
        nullable=False,
        default=PublicationKind.WORK,
        server_default=PublicationKind.WORK.value,
    )
    status: Mapped[PublicationStatus] = mapped_column(
        enum_type(PublicationStatus, name="community_publication_status", length=24),
        nullable=False,
    )
    public_version_number: Mapped[int | None] = mapped_column(Integer)
    pending_version_number: Mapped[int | None] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    withdrawn_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    taken_down_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    project: Mapped["Project | None"] = relationship(back_populates="community_publication")


class CommunityPublicationVersion(IdMixin, Base):
    __tablename__ = "community_publication_versions"
    __table_args__ = (
        UniqueConstraint("publication_id", "version_number", name="uq_publication_version"),
        UniqueConstraint("publication_id", "request_key", name="uq_publication_request"),
        CheckConstraint("version_number >= 1", name="positive_version"),
        Index("ix_publication_version_submitted", "submitted_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )

    publication_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "community_publications.id",
            name="fk_publication_version_publication",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    project_updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    kind: Mapped[PublicationKind] = mapped_column(
        enum_type(PublicationKind, name="publication_version_kind", length=24),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[ProjectDifficulty] = mapped_column(
        enum_type(ProjectDifficulty, name="publication_project_difficulty", length=16),
        nullable=False,
    )
    project_status: Mapped[ProjectStatus] = mapped_column(
        enum_type(ProjectStatus, name="publication_project_status", length=20),
        nullable=False,
    )
    language: Mapped[str | None] = mapped_column(String(100))
    framework: Mapped[str | None] = mapped_column(String(100))
    frontend: Mapped[str | None] = mapped_column(String(100))
    backend: Mapped[str | None] = mapped_column(String(100))
    database: Mapped[str | None] = mapped_column("database", String(100), quote=True)
    repository_url: Mapped[str | None] = mapped_column(String(500))
    tag_names: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    attribution: Mapped[str | None] = mapped_column(String(160))
    source_license_statement: Mapped[str | None] = mapped_column(String(500))
    ai_assistance_statement: Mapped[str | None] = mapped_column(String(1_000))
    human_review_statement: Mapped[str | None] = mapped_column(String(1_000))
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class CommunityGovernanceAction(IdMixin, Base):
    __tablename__ = "community_governance_actions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["publication_id", "publication_version_number"],
            [
                "community_publication_versions.publication_id",
                "community_publication_versions.version_number",
            ],
            name="fk_governance_action_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(publication_id IS NOT NULL AND publication_version_number IS NOT NULL AND comment_id IS NULL) "
            "OR (publication_id IS NULL AND publication_version_number IS NULL AND comment_id IS NOT NULL)",
            name="single_target",
        ),
        Index("ix_governance_action_publication_time", "publication_id", "occurred_at", "id"),
        Index("ix_governance_action_comment_time", "comment_id", "occurred_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )

    actor_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_governance_action_actor", ondelete="RESTRICT"),
        nullable=False,
    )
    target_owner_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_governance_action_owner", ondelete="RESTRICT"),
        nullable=False,
    )
    publication_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    publication_version_number: Mapped[int | None] = mapped_column(Integer)
    comment_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("comments.id", name="fk_governance_action_comment", ondelete="RESTRICT"),
    )
    action: Mapped[GovernanceActionType] = mapped_column(
        enum_type(GovernanceActionType, name="community_governance_action", length=24),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    target_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class CommunityGovernanceCase(IdMixin, TimestampMixin, Base):
    __tablename__ = "community_governance_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["publication_id", "publication_version_number"],
            [
                "community_publication_versions.publication_id",
                "community_publication_versions.version_number",
            ],
            name="fk_governance_case_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(case_type = 'report' AND target_action_id IS NULL AND "
            "((publication_id IS NOT NULL AND publication_version_number IS NOT NULL AND comment_id IS NULL) "
            "OR (publication_id IS NULL AND publication_version_number IS NULL AND comment_id IS NOT NULL))) "
            "OR (case_type = 'appeal' AND publication_id IS NULL AND publication_version_number IS NULL "
            "AND comment_id IS NULL AND target_action_id IS NOT NULL)",
            name="case_target",
        ),
        UniqueConstraint(
            "opened_by_user_id", "case_type", "publication_id", "publication_version_number",
            name="uq_governance_case_publication",
        ),
        UniqueConstraint(
            "opened_by_user_id", "case_type", "comment_id",
            name="uq_governance_case_comment",
        ),
        UniqueConstraint(
            "opened_by_user_id", "case_type", "target_action_id",
            name="uq_governance_case_action",
        ),
        UniqueConstraint("opened_by_user_id", "request_key", name="uq_governance_case_request"),
        Index("ix_governance_case_status_created", "status", "created_at", "id"),
        Index("ix_governance_case_owner_created", "opened_by_user_id", "created_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )

    case_type: Mapped[GovernanceCaseType] = mapped_column(
        enum_type(GovernanceCaseType, name="community_governance_case_type", length=16),
        nullable=False,
    )
    opened_by_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_governance_case_opener", ondelete="RESTRICT"),
        nullable=False,
    )
    target_owner_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_governance_case_owner", ondelete="RESTRICT"),
        nullable=False,
    )
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    publication_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True))
    publication_version_number: Mapped[int | None] = mapped_column(Integer)
    comment_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("comments.id", name="fk_governance_case_comment", ondelete="RESTRICT"),
    )
    target_action_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "community_governance_actions.id",
            name="fk_governance_case_target_action",
            ondelete="RESTRICT",
        ),
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    target_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[GovernanceCaseStatus] = mapped_column(
        enum_type(GovernanceCaseStatus, name="community_governance_case_status", length=16),
        nullable=False,
        default=GovernanceCaseStatus.PENDING,
        server_default=GovernanceCaseStatus.PENDING.value,
    )
    resolution_reason: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_governance_case_reviewer", ondelete="RESTRICT"),
    )
    resolved_action_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "community_governance_actions.id",
            name="fk_governance_case_result_action",
            ondelete="RESTRICT",
        ),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
