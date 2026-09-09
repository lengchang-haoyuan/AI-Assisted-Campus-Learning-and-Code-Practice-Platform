from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models.campus import CampusMembership
from app.models.project import Project
from app.models.submission import Feedback, Notification, Submission, SubmissionStatus, SubmissionVersion
from app.models.teaching import (
    ClassMemberRole,
    ClassMembership,
    ClassMembershipStatus,
    TeachingAssignment,
    TeachingAssignmentStatus,
    TeachingClass,
    TeachingClassStatus,
)
from app.models.user import User


class SubmissionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("请求与现有提交或反馈数据冲突") from exc
        except BaseException:
            self._session.rollback()
            raise

    def add(self, value: object) -> None:
        self._session.add(value)
        self._session.flush()

    def campus_membership_for_user(self, user_id: int) -> CampusMembership | None:
        return self._session.scalar(
            select(CampusMembership)
            .where(CampusMembership.user_id == user_id)
            .execution_options(populate_existing=True)
        )

    def teaching_class(
        self, class_id: int, *, for_update: bool = False
    ) -> TeachingClass | None:
        statement = select(TeachingClass).where(TeachingClass.id == class_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

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

    def submission_for_student(
        self,
        assignment_id: int,
        student_membership_id: int,
        *,
        for_update: bool = False,
    ) -> Submission | None:
        statement = select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_membership_id == student_membership_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def submission(
        self, submission_id: int, *, for_update: bool = False
    ) -> Submission | None:
        statement = select(Submission).where(Submission.id == submission_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def version(
        self,
        submission_id: int,
        version_number: int,
        *,
        for_update: bool = False,
    ) -> SubmissionVersion | None:
        statement = select(SubmissionVersion).where(
            SubmissionVersion.submission_id == submission_id,
            SubmissionVersion.version_number == version_number,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def version_by_request_key(
        self,
        submission_id: int,
        request_key: str,
        *,
        for_update: bool = False,
    ) -> SubmissionVersion | None:
        statement = select(SubmissionVersion).where(
            SubmissionVersion.submission_id == submission_id,
            SubmissionVersion.request_key == request_key,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def feedback(
        self,
        submission_id: int,
        version_number: int,
        *,
        for_update: bool = False,
    ) -> Feedback | None:
        statement = select(Feedback).where(
            Feedback.submission_id == submission_id,
            Feedback.version_number == version_number,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(
            statement.execution_options(populate_existing=True)
        )

    def feedback_by_id(self, feedback_id: int) -> Feedback | None:
        return self._session.get(Feedback, feedback_id)

    def owned_project(self, project_id: int, user_id: int) -> Project | None:
        return self._session.scalar(
            select(Project).where(Project.id == project_id, Project.owner_id == user_id)
        )

    def submission_student(self, student_membership_id: int) -> tuple[int, str] | None:
        row = self._session.execute(
            select(User.id, User.username)
            .join(CampusMembership, CampusMembership.user_id == User.id)
            .join(
                ClassMembership,
                ClassMembership.campus_membership_id == CampusMembership.id,
            )
            .where(ClassMembership.id == student_membership_id)
        ).one_or_none()
        return (row[0], row[1]) if row is not None else None

    def submission_page(
        self,
        *,
        campus_membership: CampusMembership,
        teacher: bool,
        assignment_id: int | None,
        pending_only: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[Submission], int]:
        statement = select(Submission)
        count_statement = select(func.count(Submission.id))
        if teacher:
            statement = statement.join(
                ClassMembership,
                ClassMembership.class_id == Submission.class_id,
            ).where(
                ClassMembership.campus_membership_id == campus_membership.id,
                ClassMembership.member_role == ClassMemberRole.TEACHER,
                ClassMembership.status == ClassMembershipStatus.ACTIVE,
            )
            count_statement = count_statement.join(
                ClassMembership,
                ClassMembership.class_id == Submission.class_id,
            ).where(
                ClassMembership.campus_membership_id == campus_membership.id,
                ClassMembership.member_role == ClassMemberRole.TEACHER,
                ClassMembership.status == ClassMembershipStatus.ACTIVE,
            )
        else:
            statement = statement.where(
                Submission.student_membership_id.in_(
                    select(ClassMembership.id).where(
                        ClassMembership.campus_membership_id == campus_membership.id
                    )
                )
            )
            count_statement = count_statement.where(
                Submission.student_membership_id.in_(
                    select(ClassMembership.id).where(
                        ClassMembership.campus_membership_id == campus_membership.id
                    )
                )
            )
        if assignment_id is not None:
            statement = statement.where(Submission.assignment_id == assignment_id)
            count_statement = count_statement.where(
                Submission.assignment_id == assignment_id
            )
        if pending_only:
            pending = select(SubmissionVersion.submission_id).where(
                SubmissionVersion.submission_id == Submission.id,
                SubmissionVersion.version_number == Submission.latest_version_number,
                SubmissionVersion.status == SubmissionStatus.SUBMITTED,
            )
            statement = statement.where(pending.exists())
            count_statement = count_statement.where(pending.exists())
            reviewable = select(TeachingAssignment.id).join(
                TeachingClass, TeachingClass.id == TeachingAssignment.class_id
            ).where(
                TeachingAssignment.id == Submission.assignment_id,
                TeachingAssignment.status.in_(
                    (
                        TeachingAssignmentStatus.PUBLISHED,
                        TeachingAssignmentStatus.CLOSED,
                    )
                ),
                TeachingClass.status == TeachingClassStatus.ACTIVE,
            )
            statement = statement.where(reviewable.exists())
            count_statement = count_statement.where(reviewable.exists())
        total = int(self._session.scalar(count_statement) or 0)
        values = list(
            self._session.scalars(
                statement.order_by(Submission.updated_at.desc(), Submission.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return values, total

    def pending_assignment_page(
        self,
        *,
        campus_membership_id: int,
        now: datetime,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[TeachingAssignment, Submission | None, SubmissionVersion | None]], int]:
        joins = (
            (
                ClassMembership,
                and_(
                    ClassMembership.class_id == TeachingAssignment.class_id,
                    ClassMembership.campus_membership_id == campus_membership_id,
                ),
            ),
            (TeachingClass, TeachingClass.id == TeachingAssignment.class_id),
        )
        submission_join = and_(
            Submission.assignment_id == TeachingAssignment.id,
            Submission.student_membership_id == ClassMembership.id,
        )
        version_join = and_(
            SubmissionVersion.submission_id == Submission.id,
            SubmissionVersion.version_number == Submission.latest_version_number,
        )
        conditions = (
            ClassMembership.member_role == ClassMemberRole.STUDENT,
            ClassMembership.status == ClassMembershipStatus.ACTIVE,
            TeachingClass.status == TeachingClassStatus.ACTIVE,
            TeachingAssignment.status == TeachingAssignmentStatus.PUBLISHED,
            TeachingAssignment.due_at > now,
            or_(
                Submission.id.is_(None),
                SubmissionVersion.status == SubmissionStatus.RETURNED,
            ),
        )
        statement = select(TeachingAssignment, Submission, SubmissionVersion)
        count_statement = select(func.count(TeachingAssignment.id))
        for target, condition in joins:
            statement = statement.join(target, condition)
            count_statement = count_statement.join(target, condition)
        statement = statement.outerjoin(Submission, submission_join).outerjoin(
            SubmissionVersion, version_join
        )
        count_statement = count_statement.outerjoin(
            Submission, submission_join
        ).outerjoin(SubmissionVersion, version_join)
        total = int(self._session.scalar(count_statement.where(*conditions)) or 0)
        rows = self._session.execute(
            statement
            .where(*conditions)
            .order_by(TeachingAssignment.due_at.asc(), TeachingAssignment.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [(row[0], row[1], row[2]) for row in rows], total

    def version_page(
        self, submission_id: int, *, page: int, page_size: int
    ) -> tuple[list[SubmissionVersion], int]:
        total = int(
            self._session.scalar(
                select(func.count(SubmissionVersion.id)).where(
                    SubmissionVersion.submission_id == submission_id
                )
            )
            or 0
        )
        values = list(
            self._session.scalars(
                select(SubmissionVersion)
                .where(SubmissionVersion.submission_id == submission_id)
                .order_by(SubmissionVersion.version_number.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return values, total

    def notification_page(
        self,
        user_id: int,
        *,
        unread_only: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[Notification], int, int]:
        conditions = [Notification.recipient_user_id == user_id]
        if unread_only:
            conditions.append(Notification.read_at.is_(None))
        total = int(
            self._session.scalar(select(func.count(Notification.id)).where(*conditions))
            or 0
        )
        unread = int(
            self._session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.recipient_user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )
            or 0
        )
        values = list(
            self._session.scalars(
                select(Notification)
                .where(*conditions)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return values, total, unread

    def notification_for_user(
        self, notification_id: int, user_id: int, *, for_update: bool = False
    ) -> Notification | None:
        statement = select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)
