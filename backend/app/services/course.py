from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Any

from app.core.exceptions import ConflictError, PermissionDeniedError, ResourceNotFoundError
from app.models.course import Course
from app.models.enums import CourseStatus
from app.repositories.course import CoursePersistenceConflictError, CourseRepository


@dataclass(frozen=True, slots=True)
class CourseCreateData:
    name: str
    code: str | None
    description: str | None
    instructor: str | None
    schedule_data: dict[str, Any] | None
    status: CourseStatus


@dataclass(frozen=True, slots=True)
class CourseUpdateData:
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CourseData:
    id: int
    name: str
    code: str | None
    description: str | None
    instructor: str | None
    schedule_data: dict[str, Any] | None
    status: CourseStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CoursePage:
    items: list[CourseData]
    total: int
    page: int
    page_size: int
    total_pages: int


class CourseService:
    def __init__(self, repository: CourseRepository) -> None:
        self._repository = repository

    def list_courses(self, owner_id: int, *, page: int, page_size: int) -> CoursePage:
        total = self._repository.count_by_owner(owner_id)
        courses = self._repository.list_by_owner(
            owner_id, offset=(page - 1) * page_size, limit=page_size
        )
        return CoursePage(
            items=[self._to_data(course) for course in courses],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_course(self, course_id: int, owner_id: int) -> CourseData:
        return self._to_data(self._get_owned(course_id, owner_id))

    def create_course(self, owner_id: int, data: CourseCreateData) -> CourseData:
        course = Course(
            owner_id=owner_id,
            name=data.name,
            code=data.code,
            description=data.description,
            instructor=data.instructor,
            schedule_data=data.schedule_data,
            status=data.status,
        )
        try:
            return self._to_data(self._repository.create(course))
        except CoursePersistenceConflictError as exc:
            raise ConflictError("课程名称已存在或数据冲突") from exc

    def update_course(
        self, course_id: int, owner_id: int, data: CourseUpdateData
    ) -> CourseData:
        course = self._get_owned(course_id, owner_id)
        for field_name, value in data.changes.items():
            setattr(course, field_name, value)
        try:
            return self._to_data(self._repository.update(course))
        except CoursePersistenceConflictError as exc:
            raise ConflictError("课程名称已存在或数据冲突") from exc

    def delete_course(self, course_id: int, owner_id: int) -> None:
        course = self._get_owned(course_id, owner_id)
        try:
            self._repository.delete(course)
        except CoursePersistenceConflictError as exc:
            raise ConflictError("课程当前无法删除") from exc

    def _get_owned(self, course_id: int, owner_id: int) -> Course:
        course = self._repository.get_by_id(course_id)
        if course is None:
            raise ResourceNotFoundError("课程不存在")
        if course.owner_id != owner_id:
            raise PermissionDeniedError("无权访问该课程")
        return course

    @staticmethod
    def _to_data(course: Course) -> CourseData:
        return CourseData(
            id=course.id,
            name=course.name,
            code=course.code,
            description=course.description,
            instructor=course.instructor,
            schedule_data=course.schedule_data,
            status=course.status,
            created_at=course.created_at,
            updated_at=course.updated_at,
        )
