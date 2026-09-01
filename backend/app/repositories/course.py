from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course import Course


class CoursePersistenceConflictError(Exception):
    """课程写入与当前数据库约束冲突。"""


class CourseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_by_owner(self, owner_id: int) -> int:
        return self._session.scalar(
            select(func.count(Course.id)).where(Course.owner_id == owner_id)
        ) or 0

    def list_by_owner(self, owner_id: int, *, offset: int, limit: int) -> list[Course]:
        return list(
            self._session.scalars(
                select(Course)
                .where(Course.owner_id == owner_id)
                .order_by(Course.updated_at.desc(), Course.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )

    def get_by_id(self, course_id: int) -> Course | None:
        return self._session.get(Course, course_id)

    def create(self, course: Course) -> Course:
        self._session.add(course)
        self._commit_or_raise()
        self._session.refresh(course)
        return course

    def update(self, course: Course) -> Course:
        self._commit_or_raise()
        self._session.refresh(course)
        return course

    def delete(self, course: Course) -> None:
        self._session.delete(course)
        self._commit_or_raise()

    def _commit_or_raise(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise CoursePersistenceConflictError from exc
