from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, SMALLINT
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
    from app.models.ai import AIRequest
    from app.models.community import Comment, Favorite, Like, ProjectView
    from app.models.learning import DailyTask, LearningPlan, LearningRecord
    from app.models.user import User
    from app.models.workflow import Workflow


project_tags = Table(
    "project_tags",
    Base.metadata,
    Column(
        "project_id",
        BIGINT(unsigned=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        BIGINT(unsigned=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        UTCDateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    ),
    **MYSQL_TABLE_OPTIONS,
)


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("progress BETWEEN 0 AND 100", name="progress_range"),
        Index("ix_projects_owner_status", "owner_id", "status"),
        Index("ix_projects_published_created", "is_published", "created_at"),
        Index("ix_projects_created_at", "created_at"),
        Index("ix_projects_completed_at", "completed_at"),
        Index("ix_projects_published_at", "published_at"),
        MYSQL_TABLE_OPTIONS,
    )

    owner_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[ProjectDifficulty] = mapped_column(
        enum_type(ProjectDifficulty, name="project_difficulty", length=16),
        nullable=False,
        server_default=ProjectDifficulty.BEGINNER.value,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        enum_type(ProjectStatus, name="project_status", length=20),
        nullable=False,
        server_default=ProjectStatus.NOT_STARTED.value,
    )
    language: Mapped[str | None] = mapped_column(String(100))
    framework: Mapped[str | None] = mapped_column(String(100))
    frontend: Mapped[str | None] = mapped_column(String(100))
    backend: Mapped[str | None] = mapped_column(String(100))
    database: Mapped[str | None] = mapped_column("database", String(100), quote=True)
    requirements: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    output_requirement: Mapped[str | None] = mapped_column(Text)
    context_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    cover_url: Mapped[str | None] = mapped_column(String(500))
    repository_url: Mapped[str | None] = mapped_column(String(500))
    result_summary: Mapped[str | None] = mapped_column(Text)
    progress: Mapped[int] = mapped_column(
        SMALLINT(unsigned=True), nullable=False, server_default=text("0")
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("0")
    )
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    view_count: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    tags: Mapped[list["Tag"]] = relationship(
        secondary=project_tags, back_populates="projects", passive_deletes=True
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    likes: Mapped[list["Like"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    views: Mapped[list["ProjectView"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    workflows: Mapped[list["Workflow"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    learning_plans: Mapped[list["LearningPlan"]] = relationship(
        back_populates="project", passive_deletes=True
    )
    daily_tasks: Mapped[list["DailyTask"]] = relationship(
        back_populates="project", passive_deletes=True
    )
    learning_records: Mapped[list["LearningRecord"]] = relationship(
        back_populates="project", passive_deletes=True
    )
    ai_requests: Mapped[list["AIRequest"]] = relationship(
        back_populates="project", passive_deletes=True
    )


class Tag(IdMixin, Base):
    __tablename__ = "tags"
    __table_args__ = MYSQL_TABLE_OPTIONS

    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )

    projects: Mapped[list[Project]] = relationship(
        secondary=project_tags, back_populates="tags", passive_deletes=True
    )
