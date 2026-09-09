from datetime import UTC, datetime
from math import ceil
from typing import Any

from app.core.exceptions import ConflictError, PermissionDeniedError, ResourceNotFoundError
from app.models.campus import CampusMembership, CampusRole, MembershipStatus
from app.models.enums import RecordType
from app.models.learning import LearningRecord
from app.models.submission import (
    Feedback,
    FeedbackDecision,
    Notification,
    Submission,
    SubmissionStatus,
    SubmissionVersion,
)
from app.models.teaching import (
    ClassMemberRole,
    ClassMembership,
    ClassMembershipStatus,
    TeachingAssignment,
    TeachingAssignmentStatus,
    TeachingClass,
    TeachingClassStatus,
)
from app.repositories.submission import SubmissionRepository
from app.services.auth import UserIdentity


class SubmissionService:
    def __init__(self, repository: SubmissionRepository) -> None:
        self._repository = repository

    def _actor(self, current_user: UserIdentity) -> CampusMembership:
        value = self._repository.campus_membership_for_user(current_user.id)
        if value is None or value.status != MembershipStatus.ACTIVE:
            raise PermissionDeniedError("需要有效的校园身份")
        return value

    @staticmethod
    def _student_member(
        actor: CampusMembership, member: ClassMembership | None, *, active: bool
    ) -> ClassMembership:
        allowed = (
            actor.role == CampusRole.STUDENT
            and member is not None
            and member.member_role == ClassMemberRole.STUDENT
            and (not active or member.status == ClassMembershipStatus.ACTIVE)
        )
        if not allowed or member is None:
            raise ResourceNotFoundError("教学任务或提交不存在")
        return member

    @staticmethod
    def _teacher_member(
        actor: CampusMembership, member: ClassMembership | None
    ) -> ClassMembership:
        allowed = (
            actor.role == CampusRole.TEACHER
            and member is not None
            and member.member_role == ClassMemberRole.TEACHER
            and member.status == ClassMembershipStatus.ACTIVE
        )
        if not allowed or member is None:
            raise ResourceNotFoundError("提交不存在")
        return member

    @staticmethod
    def _assert_open_submission(
        teaching_class: TeachingClass,
        assignment: TeachingAssignment,
        now: datetime,
    ) -> None:
        if teaching_class.status != TeachingClassStatus.ACTIVE:
            raise ConflictError("教学班已归档，不能提交成果")
        if assignment.status != TeachingAssignmentStatus.PUBLISHED:
            raise ConflictError("教学任务当前不接受提交")
        if assignment.due_at is None or now >= assignment.due_at:
            raise ConflictError("教学任务已到截止时间")

    @staticmethod
    def _feedback_data(value: Feedback | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return {
            "id": value.id,
            "decision": value.decision,
            "comment": value.comment,
            "created_at": value.created_at,
        }

    def _version_data(self, value: SubmissionVersion) -> dict[str, Any]:
        return {
            "id": value.id,
            "version_number": value.version_number,
            "summary": value.summary,
            "repository_url": value.repository_url,
            "repository_ref": value.repository_ref,
            "source_project_title": value.source_project_title,
            "has_project_reference": value.source_project_id is not None,
            "status": value.status,
            "submitted_at": value.submitted_at,
            "reviewed_at": value.reviewed_at,
            "revision": value.revision,
            "feedback": self._feedback(value.submission_id, value.version_number),
        }

    def _feedback(self, submission_id: int, version_number: int) -> dict[str, Any] | None:
        return self._feedback_data(
            self._repository.feedback(submission_id, version_number)
        )

    def _submission_data(
        self,
        value: Submission,
        actor: CampusMembership,
    ) -> dict[str, Any]:
        latest = (
            self._repository.version(value.id, value.latest_version_number)
            if value.latest_version_number is not None
            else None
        )
        student = self._repository.submission_student(value.student_membership_id)
        member = self._repository.class_membership(value.class_id, actor.id)
        is_owner = (
            actor.role == CampusRole.STUDENT
            and member is not None
            and member.id == value.student_membership_id
        )
        teaching_class = self._repository.teaching_class(value.class_id)
        assignment = self._repository.assignment(value.assignment_id)
        can_review = (
            actor.role == CampusRole.TEACHER
            and member is not None
            and member.member_role == ClassMemberRole.TEACHER
            and member.status == ClassMembershipStatus.ACTIVE
            and latest is not None
            and latest.status == SubmissionStatus.SUBMITTED
            and teaching_class is not None
            and teaching_class.status == TeachingClassStatus.ACTIVE
            and assignment is not None
            and assignment.status
            in (TeachingAssignmentStatus.PUBLISHED, TeachingAssignmentStatus.CLOSED)
        )
        can_submit_next = False
        if is_owner and member is not None and member.status == ClassMembershipStatus.ACTIVE:
            can_submit_next = bool(
                teaching_class
                and teaching_class.status == TeachingClassStatus.ACTIVE
                and assignment
                and assignment.status == TeachingAssignmentStatus.PUBLISHED
                and assignment.due_at
                and datetime.now(UTC) < assignment.due_at
                and latest
                and latest.status == SubmissionStatus.RETURNED
            )
        return {
            "id": value.id,
            "class_id": value.class_id,
            "assignment_id": value.assignment_id,
            "assignment_title": value.assignment_title,
            "assignment_due_at": value.assignment_due_at,
            "student_username": student[1] if student is not None else "已停用账号",
            "latest_version_number": value.latest_version_number,
            "revision": value.revision,
            "created_at": value.created_at,
            "updated_at": value.updated_at,
            "latest_version": self._version_data(latest) if latest is not None else None,
            "can_review": can_review,
            "can_submit_next": can_submit_next,
            "is_owner": is_owner,
        }

    def submit(
        self,
        current_user: UserIdentity,
        *,
        assignment_id: int,
        request_key: str,
        expected_latest_version: int,
        summary: str,
        repository_url: str | None,
        repository_ref: str | None,
        source_project_id: int | None,
    ) -> tuple[dict[str, Any], bool]:
        discovered = self._repository.assignment(assignment_id)
        if discovered is None:
            raise ResourceNotFoundError("教学任务不存在")
        replayed = False
        with self._repository.transaction():
            actor = self._actor(current_user)
            teaching_class = self._repository.teaching_class(
                discovered.class_id, for_update=True
            )
            assignment = self._repository.assignment(assignment_id, for_update=True)
            if teaching_class is None or assignment is None:
                raise ResourceNotFoundError("教学任务不存在")
            member = self._repository.class_membership(
                assignment.class_id, actor.id, for_update=True
            )
            student_member = self._student_member(actor, member, active=True)
            now = datetime.now(UTC)
            self._assert_open_submission(teaching_class, assignment, now)

            project_title: str | None = None
            if source_project_id is not None:
                project = self._repository.owned_project(source_project_id, current_user.id)
                if project is None:
                    raise ResourceNotFoundError("关联项目不存在")
                project_title = project.name
            payload: dict[str, str | int | None] = {
                "summary": summary,
                "repository_url": repository_url,
                "repository_ref": repository_ref,
                "source_project_id": source_project_id,
            }
            submission = self._repository.submission_for_student(
                assignment.id, student_member.id, for_update=True
            )
            if submission is None:
                if expected_latest_version != 0:
                    raise ConflictError("提交版本已变化，请刷新后重试")
                if assignment.due_at is None:
                    raise ConflictError("任务没有有效截止时间")
                submission = Submission(
                    class_id=assignment.class_id,
                    assignment_id=assignment.id,
                    student_membership_id=student_member.id,
                    assignment_title=assignment.title,
                    assignment_due_at=assignment.due_at,
                    latest_version_number=None,
                    revision=1,
                )
                self._repository.add(submission)
            else:
                previous = self._repository.version_by_request_key(
                    submission.id, request_key, for_update=True
                )
                if previous is not None:
                    if previous.request_payload != payload:
                        raise ConflictError("相同请求标识不能提交不同内容")
                    replayed = True
                    return self._submission_data(submission, actor), replayed
                latest_number = submission.latest_version_number or 0
                if expected_latest_version != latest_number:
                    raise ConflictError("提交版本已变化，请刷新后重试")
                latest = self._repository.version(submission.id, latest_number)
                if latest is None or latest.status != SubmissionStatus.RETURNED:
                    raise ConflictError("当前版本尚未退回，不能追加新版本")

            version_number = (submission.latest_version_number or 0) + 1
            version = SubmissionVersion(
                submission_id=submission.id,
                version_number=version_number,
                request_key=request_key,
                request_payload=payload,
                summary=summary,
                repository_url=repository_url,
                repository_ref=repository_ref,
                source_project_id=source_project_id,
                source_project_title=project_title,
                status=SubmissionStatus.SUBMITTED,
                submitted_at=now,
                revision=1,
            )
            self._repository.add(version)
            submission.latest_version_number = version_number
            if version_number > 1:
                submission.revision += 1
        return self._submission_data(submission, actor), replayed

    def _authorize_submission(
        self, current_user: UserIdentity, submission: Submission
    ) -> CampusMembership:
        actor = self._actor(current_user)
        member = self._repository.class_membership(submission.class_id, actor.id)
        if actor.role == CampusRole.STUDENT:
            owner = self._student_member(actor, member, active=False)
            if owner.id != submission.student_membership_id:
                raise ResourceNotFoundError("提交不存在")
        elif actor.role == CampusRole.TEACHER:
            self._teacher_member(actor, member)
        else:
            raise ResourceNotFoundError("提交不存在")
        return actor

    def submissions(
        self,
        current_user: UserIdentity,
        *,
        assignment_id: int | None,
        pending_only: bool,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        actor = self._actor(current_user)
        if actor.role not in (CampusRole.STUDENT, CampusRole.TEACHER):
            raise PermissionDeniedError("当前校园角色没有教学提交权限")
        teacher = actor.role == CampusRole.TEACHER
        if assignment_id is not None:
            assignment = self._repository.assignment(assignment_id)
            if assignment is None:
                raise ResourceNotFoundError("教学任务不存在")
            member = self._repository.class_membership(assignment.class_id, actor.id)
            if teacher:
                self._teacher_member(actor, member)
            else:
                self._student_member(actor, member, active=True)
                if assignment.status == TeachingAssignmentStatus.DRAFT:
                    raise ResourceNotFoundError("教学任务不存在")
        values, total = self._repository.submission_page(
            campus_membership=actor,
            teacher=teacher,
            assignment_id=assignment_id,
            pending_only=pending_only if teacher else False,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._submission_data(value, actor) for value in values],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def get_submission(
        self, current_user: UserIdentity, *, submission_id: int
    ) -> dict[str, Any]:
        value = self._repository.submission(submission_id)
        if value is None:
            raise ResourceNotFoundError("提交不存在")
        actor = self._authorize_submission(current_user, value)
        return self._submission_data(value, actor)

    def pending_assignments(
        self,
        current_user: UserIdentity,
        *,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        actor = self._actor(current_user)
        if actor.role != CampusRole.STUDENT:
            raise PermissionDeniedError("只有学生可以查询待提交任务")
        values, total = self._repository.pending_assignment_page(
            campus_membership_id=actor.id,
            now=datetime.now(UTC),
            page=page,
            page_size=page_size,
        )
        return {
            "items": [
                {
                    "id": assignment.id,
                    "class_id": assignment.class_id,
                    "title": assignment.title,
                    "due_at": assignment.due_at,
                    "submission_id": submission.id if submission is not None else None,
                    "current_status": version.status if version is not None else None,
                }
                for assignment, submission, version in values
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def versions(
        self,
        current_user: UserIdentity,
        *,
        submission_id: int,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        submission = self._repository.submission(submission_id)
        if submission is None:
            raise ResourceNotFoundError("提交不存在")
        self._authorize_submission(current_user, submission)
        values, total = self._repository.version_page(
            submission_id, page=page, page_size=page_size
        )
        return {
            "items": [self._version_data(value) for value in values],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def feedback(
        self,
        current_user: UserIdentity,
        *,
        submission_id: int,
        version_number: int,
        expected_revision: int,
        decision: FeedbackDecision,
        comment: str,
    ) -> tuple[dict[str, Any], bool]:
        discovered = self._repository.submission(submission_id)
        if discovered is None:
            raise ResourceNotFoundError("提交不存在")
        with self._repository.transaction():
            actor = self._actor(current_user)
            teaching_class = self._repository.teaching_class(
                discovered.class_id, for_update=True
            )
            assignment = self._repository.assignment(
                discovered.assignment_id, for_update=True
            )
            if teaching_class is None or assignment is None:
                raise ResourceNotFoundError("提交不存在")
            member = self._repository.class_membership(
                discovered.class_id, actor.id, for_update=True
            )
            teacher = self._teacher_member(actor, member)
            submission = self._repository.submission(submission_id, for_update=True)
            if submission is None:
                raise ResourceNotFoundError("提交不存在")
            version = self._repository.version(
                submission.id, version_number, for_update=True
            )
            if version is None:
                raise ResourceNotFoundError("提交版本不存在")
            existing = self._repository.feedback(
                submission.id, version_number, for_update=True
            )
            if existing is not None:
                if existing.decision == decision and existing.comment == comment:
                    return self._feedback_data(existing) or {}, True
                raise ConflictError("该版本已经完成评阅")
            if submission.latest_version_number != version_number:
                raise ConflictError("只能评阅最新提交版本")
            if teaching_class.status != TeachingClassStatus.ACTIVE:
                raise ConflictError("教学班已归档，不能评阅")
            if assignment.status not in (
                TeachingAssignmentStatus.PUBLISHED,
                TeachingAssignmentStatus.CLOSED,
            ):
                raise ConflictError("教学任务当前不能评阅")
            if submission.revision != expected_revision:
                raise ConflictError("提交已被更新，请刷新后重试")
            if version.status != SubmissionStatus.SUBMITTED:
                raise ConflictError("该版本不是待评阅状态")

            now = datetime.now(UTC)
            learning_record_id: int | None = None
            student = self._repository.submission_student(
                submission.student_membership_id
            )
            if student is None:
                raise ConflictError("提交者账号关系不存在")
            if decision == FeedbackDecision.ACCEPT:
                record = LearningRecord(
                    user_id=student[0],
                    record_type=RecordType.TASK,
                    title=f"教学任务通过：{submission.assignment_title}",
                    content=f"教学提交 #{submission.id} V{version_number} 已由教师确认通过。",
                    duration_minutes=None,
                    occurred_at=now,
                    record_metadata={
                        "source": "teaching_submission",
                        "submission_id": submission.id,
                        "version_number": version_number,
                    },
                )
                self._repository.add(record)
                learning_record_id = record.id
                version.status = SubmissionStatus.ACCEPTED
            else:
                version.status = SubmissionStatus.RETURNED
            version.reviewed_at = now
            version.revision += 1
            submission.revision += 1
            result = Feedback(
                submission_id=submission.id,
                version_number=version_number,
                class_id=submission.class_id,
                teacher_membership_id=teacher.id,
                decision=decision,
                comment=comment,
                created_at=now,
                learning_record_id=learning_record_id,
            )
            self._repository.add(result)
            self._repository.add(
                Notification(
                    recipient_user_id=student[0],
                    event_key=f"feedback_created:{result.id}",
                    kind="feedback_created",
                    assignment_id=submission.assignment_id,
                    feedback_id=result.id,
                    created_at=now,
                )
            )
        return self._feedback_data(result) or {}, False

    def detach_project(
        self,
        current_user: UserIdentity,
        *,
        submission_id: int,
        version_number: int,
    ) -> None:
        discovered = self._repository.submission(submission_id)
        if discovered is None:
            raise ResourceNotFoundError("提交不存在")
        with self._repository.transaction():
            actor = self._actor(current_user)
            self._student_member(
                actor,
                self._repository.class_membership(discovered.class_id, actor.id),
                active=False,
            )
            submission = self._repository.submission(submission_id, for_update=True)
            if submission is None:
                raise ResourceNotFoundError("提交不存在")
            owner = self._repository.class_membership(submission.class_id, actor.id)
            if owner is None or owner.id != submission.student_membership_id:
                raise ResourceNotFoundError("提交不存在")
            version = self._repository.version(
                submission_id, version_number, for_update=True
            )
            if version is None:
                raise ResourceNotFoundError("提交版本不存在")
            version.source_project_id = None

    def notifications(
        self,
        current_user: UserIdentity,
        *,
        unread_only: bool,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        values, total, unread = self._repository.notification_page(
            current_user.id,
            unread_only=unread_only,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._notification_data(value) for value in values],
            "total": total,
            "unread_count": unread,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def read_notification(
        self, current_user: UserIdentity, *, notification_id: int
    ) -> dict[str, Any]:
        with self._repository.transaction():
            value = self._repository.notification_for_user(
                notification_id, current_user.id, for_update=True
            )
            if value is None:
                raise ResourceNotFoundError("通知不存在")
            if value.read_at is None:
                value.read_at = datetime.now(UTC)
        return self._notification_data(value)

    def _notification_data(self, value: Notification) -> dict[str, Any]:
        feedback = (
            self._repository.feedback_by_id(value.feedback_id)
            if value.feedback_id is not None
            else None
        )
        return {
            "id": value.id,
            "kind": value.kind,
            "assignment_id": value.assignment_id,
            "feedback_id": value.feedback_id,
            "submission_id": feedback.submission_id if feedback is not None else None,
            "created_at": value.created_at,
            "read_at": value.read_at,
        }
