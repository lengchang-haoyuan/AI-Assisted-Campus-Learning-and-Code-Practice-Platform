from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, MYSQL_TABLE_OPTIONS, TimestampMixin

if TYPE_CHECKING:
    from app.models.ai import AIRequest
    from app.models.community import Comment, Favorite, Like
    from app.models.course import Course
    from app.models.learning import DailyTask, LearningPlan, LearningRecord, LearningReport
    from app.models.project import Project
    from app.models.workflow import WorkflowRun


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = MYSQL_TABLE_OPTIONS

    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("1")
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="owner", passive_deletes=True
    )
    courses: Mapped[list["Course"]] = relationship(
        back_populates="owner", passive_deletes=True
    )
    learning_plans: Mapped[list["LearningPlan"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    daily_tasks: Mapped[list["DailyTask"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    learning_records: Mapped[list["LearningRecord"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    learning_reports: Mapped[list["LearningReport"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    likes: Mapped[list["Like"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="started_by", passive_deletes=True
    )
    ai_requests: Mapped[list["AIRequest"]] = relationship(
        back_populates="user", passive_deletes=True
    )

