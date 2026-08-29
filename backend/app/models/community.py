from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    IdMixin,
    MYSQL_TABLE_OPTIONS,
    TimestampMixin,
    UTCDateTime,
)

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Comment(IdMixin, TimestampMixin, Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_project_created", "project_id", "created_at"),
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

    project: Mapped["Project"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="comments")


class Like(IdMixin, Base):
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_likes_user_project"),
        Index("ix_likes_project_created", "project_id", "created_at"),
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

