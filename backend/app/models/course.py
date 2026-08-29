from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, MYSQL_TABLE_OPTIONS, TimestampMixin
from app.models.enums import CourseStatus, enum_type

if TYPE_CHECKING:
    from app.models.learning import LearningPlan, LearningRecord
    from app.models.user import User


class Course(IdMixin, TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_courses_owner_name"),
        Index("ix_courses_owner_status", "owner_id", "status"),
        MYSQL_TABLE_OPTIONS,
    )

    owner_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    instructor: Mapped[str | None] = mapped_column(String(100))
    schedule_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[CourseStatus] = mapped_column(
        enum_type(CourseStatus, name="course_status", length=16),
        nullable=False,
        server_default=CourseStatus.ACTIVE.value,
    )

    owner: Mapped["User"] = relationship(back_populates="courses")
    learning_plans: Mapped[list["LearningPlan"]] = relationship(
        back_populates="course", passive_deletes=True
    )
    learning_records: Mapped[list["LearningRecord"]] = relationship(
        back_populates="course", passive_deletes=True
    )
