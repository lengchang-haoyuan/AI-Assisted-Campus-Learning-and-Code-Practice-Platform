from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models.campus import CampusMembership, CampusRole
from app.models.project import Project
from app.models.teaching import (
    ClassMembership,
    ClassMembershipStatus,
    TeachingAssignment,
    TeachingAssignmentStatus,
    TeachingClass,
)
from app.models.user import User


class TeachingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("请求与现有班级或任务数据冲突") from exc
        except BaseException:
            self._session.rollback()
            raise

    def add(self, value: object) -> None:
        self._session.add(value)
        self._session.flush()

    def campus_membership_for_user(
        self, user_id: int
    ) -> CampusMembership | None:
        return self._session.scalar(
            select(CampusMembership)
            .where(CampusMembership.user_id == user_id)
            .execution_options(populate_existing=True)
        )

    def campus_member_with_user(
        self, membership_id: int
    ) -> tuple[CampusMembership, User] | None:
        row = self._session.execute(
            select(CampusMembership, User)
            .join(User, User.id == CampusMembership.user_id)
            .where(CampusMembership.id == membership_id)
            .execution_options(populate_existing=True)
        ).one_or_none()
        return (row[0], row[1]) if row is not None else None

    def teaching_class(
        self, class_id: int, *, for_update: bool = False
    ) -> TeachingClass | None:
        statement = select(TeachingClass).where(TeachingClass.id == class_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def class_membership(
        self,
        class_id: int,
        campus_membership_id: int,
        *,
        for_update: bool = False,
    ) -> ClassMembership | None:
        statement = select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.campus_membership_id == campus_membership_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def class_membership_by_id(
        self, class_id: int, member_id: int, *, for_update: bool = False
    ) -> ClassMembership | None:
        statement = select(ClassMembership).where(
            ClassMembership.id == member_id,
            ClassMembership.class_id == class_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def class_page(
        self,
        *,
        actor_membership: CampusMembership,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[TeachingClass, ClassMembership | None]], int]:
        offset = (page - 1) * page_size
        if actor_membership.role == CampusRole.ADMINISTRATOR:
            total = int(
                self._session.scalar(select(func.count(TeachingClass.id))) or 0
            )
            classes = list(
                self._session.scalars(
                    select(TeachingClass)
                    .order_by(TeachingClass.created_at.desc(), TeachingClass.id.desc())
                    .offset(offset)
                    .limit(page_size)
                )
            )
            return [(value, None) for value in classes], total

        active_member = ClassMembershipStatus.ACTIVE
        condition = (
            ClassMembership.campus_membership_id == actor_membership.id,
            ClassMembership.status == active_member,
        )
        total = int(
            self._session.scalar(
                select(func.count(TeachingClass.id))
                .join(ClassMembership, ClassMembership.class_id == TeachingClass.id)
                .where(*condition)
            )
            or 0
        )
        rows = self._session.execute(
            select(TeachingClass, ClassMembership)
            .join(ClassMembership, ClassMembership.class_id == TeachingClass.id)
            .where(*condition)
            .order_by(TeachingClass.created_at.desc(), TeachingClass.id.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
        return [(row[0], row[1]) for row in rows], total

    def class_member_page(
        self, *, class_id: int, page: int, page_size: int
    ) -> tuple[list[tuple[ClassMembership, CampusMembership, User]], int]:
        total = int(
            self._session.scalar(
                select(func.count(ClassMembership.id)).where(
                    ClassMembership.class_id == class_id
                )
            )
            or 0
        )
        rows = self._session.execute(
            select(ClassMembership, CampusMembership, User)
            .join(
                CampusMembership,
                CampusMembership.id == ClassMembership.campus_membership_id,
            )
            .join(User, User.id == CampusMembership.user_id)
            .where(ClassMembership.class_id == class_id)
            .order_by(ClassMembership.joined_at.asc(), ClassMembership.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [(row[0], row[1], row[2]) for row in rows], total

    def assignment(
        self, assignment_id: int, *, for_update: bool = False
    ) -> TeachingAssignment | None:
        statement = select(TeachingAssignment).where(
            TeachingAssignment.id == assignment_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def assignment_page(
        self,
        *,
        class_id: int,
        include_drafts: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[TeachingAssignment], int]:
        conditions = [TeachingAssignment.class_id == class_id]
        if not include_drafts:
            conditions.append(
                TeachingAssignment.status != TeachingAssignmentStatus.DRAFT
            )
        total = int(
            self._session.scalar(
                select(func.count(TeachingAssignment.id)).where(*conditions)
            )
            or 0
        )
        values = list(
            self._session.scalars(
                select(TeachingAssignment)
                .where(*conditions)
                .order_by(
                    case((TeachingAssignment.due_at.is_(None), 1), else_=0),
                    TeachingAssignment.due_at.asc(),
                    TeachingAssignment.id.asc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return values, total

    def owned_project(self, project_id: int, owner_id: int) -> Project | None:
        return self._session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == owner_id,
            )
        )
