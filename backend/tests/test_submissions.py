from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.api.deps import get_current_user, get_submission_service
from app.main import create_app
from app.models.campus import CampusMembership, CampusRole, MembershipStatus
from app.models.learning import LearningRecord
from app.models.project import Project
from app.models.submission import Feedback, FeedbackDecision, Notification, Submission, SubmissionStatus, SubmissionVersion
from app.models.teaching import ClassMemberRole, ClassMembership, ClassMembershipStatus, TeachingAssignment, TeachingAssignmentStatus, TeachingClass, TeachingClassStatus
from app.models.user import User
from app.schemas.submission import SubmissionCreateRequest
from app.services.auth import UserIdentity
from app.services.submission import SubmissionService
from tests.test_api_foundation import request

NOW = datetime.now(UTC)


def make_user(user_id: int) -> User:
    return User(
        id=user_id,
        username=f"p19_user_{user_id}",
        email=f"p19_{user_id}@example.com",
        password_hash="unused",
        auth_version=0,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )


def identity(user: User) -> UserIdentity:
    return UserIdentity(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_url=None,
        bio=None,
        is_active=True,
        created_at=NOW,
    )


class FakeSubmissionRepository:
    def __init__(self) -> None:
        self.users = {user_id: make_user(user_id) for user_id in range(1, 6)}
        roles = {
            1: CampusRole.TEACHER,
            2: CampusRole.TEACHER,
            3: CampusRole.STUDENT,
            4: CampusRole.STUDENT,
            5: CampusRole.ADMINISTRATOR,
        }
        self.campus = {
            user_id: CampusMembership(
                id=100 + user_id,
                user_id=user_id,
                role=role,
                status=MembershipStatus.ACTIVE,
                revision=1,
                created_at=NOW,
                updated_at=NOW,
            )
            for user_id, role in roles.items()
        }
        self.classes = {
            201: TeachingClass(
                id=201,
                name="A 班",
                course_title="项目实践",
                term_label="2026 秋",
                status=TeachingClassStatus.ACTIVE,
                created_by_membership_id=101,
                revision=1,
                created_at=NOW,
                updated_at=NOW,
            ),
            202: TeachingClass(
                id=202,
                name="B 班",
                course_title="项目实践",
                term_label="2026 秋",
                status=TeachingClassStatus.ACTIVE,
                created_by_membership_id=102,
                revision=1,
                created_at=NOW,
                updated_at=NOW,
            ),
        }
        self.members = {
            301: self._member(301, 201, 101, ClassMemberRole.TEACHER),
            302: self._member(302, 202, 102, ClassMemberRole.TEACHER),
            303: self._member(303, 201, 103, ClassMemberRole.STUDENT),
            304: self._member(304, 201, 104, ClassMemberRole.STUDENT),
        }
        self.assignments = {
            401: TeachingAssignment(
                id=401,
                class_id=201,
                created_by_class_membership_id=301,
                title="反转字符串",
                instructions="实现字符串反转并说明复杂度。",
                learning_objectives=["理解切片"],
                acceptance_criteria=["测试通过"],
                due_at=NOW + timedelta(days=2),
                status=TeachingAssignmentStatus.PUBLISHED,
                revision=2,
                published_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
        }
        self.projects = {
            501: Project(id=501, owner_id=3, name="本人项目"),
            502: Project(id=502, owner_id=4, name="他人项目"),
        }
        self.submission_values: dict[int, Submission] = {}
        self.version_values: dict[tuple[int, int], SubmissionVersion] = {}
        self.feedback_values: dict[tuple[int, int], Feedback] = {}
        self.notification_values: dict[int, Notification] = {}
        self.learning_records: dict[int, LearningRecord] = {}
        self.next_id = 1000

    @staticmethod
    def _member(
        member_id: int,
        class_id: int,
        campus_id: int,
        role: ClassMemberRole,
    ) -> ClassMembership:
        return ClassMembership(
            id=member_id,
            class_id=class_id,
            campus_membership_id=campus_id,
            member_role=role,
            status=ClassMembershipStatus.ACTIVE,
            joined_by_membership_id=101,
            joined_at=NOW,
            revision=1,
            created_at=NOW,
            updated_at=NOW,
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    def add(self, value: object) -> None:
        if getattr(value, "id", None) is None:
            setattr(value, "id", self.next_id)
            self.next_id += 1
        if isinstance(value, Submission):
            value.created_at = value.created_at or NOW
            value.updated_at = value.updated_at or NOW
            self.submission_values[value.id] = value
        elif isinstance(value, SubmissionVersion):
            self.version_values[(value.submission_id, value.version_number)] = value
        elif isinstance(value, Feedback):
            self.feedback_values[(value.submission_id, value.version_number)] = value
        elif isinstance(value, Notification):
            self.notification_values[value.id] = value
        elif isinstance(value, LearningRecord):
            value.created_at = value.created_at or NOW
            self.learning_records[value.id] = value

    def campus_membership_for_user(self, user_id: int):
        return self.campus.get(user_id)

    def teaching_class(self, class_id: int, *, for_update: bool = False):
        del for_update
        return self.classes.get(class_id)

    def assignment(self, assignment_id: int, *, for_update: bool = False):
        del for_update
        return self.assignments.get(assignment_id)

    def class_membership(self, class_id: int, campus_membership_id: int, *, for_update: bool = False):
        del for_update
        return next((item for item in self.members.values() if item.class_id == class_id and item.campus_membership_id == campus_membership_id), None)

    def submission_for_student(self, assignment_id: int, student_membership_id: int, *, for_update: bool = False):
        del for_update
        return next((item for item in self.submission_values.values() if item.assignment_id == assignment_id and item.student_membership_id == student_membership_id), None)

    def submission(self, submission_id: int, *, for_update: bool = False):
        del for_update
        return self.submission_values.get(submission_id)

    def version(self, submission_id: int, version_number: int, *, for_update: bool = False):
        del for_update
        return self.version_values.get((submission_id, version_number))

    def version_by_request_key(self, submission_id: int, request_key: str, *, for_update: bool = False):
        del for_update
        return next((item for (parent_id, _), item in self.version_values.items() if parent_id == submission_id and item.request_key == request_key), None)

    def feedback(self, submission_id: int, version_number: int, *, for_update: bool = False):
        del for_update
        return self.feedback_values.get((submission_id, version_number))

    def feedback_by_id(self, feedback_id: int):
        return next((item for item in self.feedback_values.values() if item.id == feedback_id), None)

    def owned_project(self, project_id: int, user_id: int):
        value = self.projects.get(project_id)
        return value if value is not None and value.owner_id == user_id else None

    def submission_student(self, student_membership_id: int):
        member = self.members.get(student_membership_id)
        if member is None:
            return None
        campus = next(item for item in self.campus.values() if item.id == member.campus_membership_id)
        user = self.users[campus.user_id]
        return user.id, user.username

    def submission_page(self, *, campus_membership: CampusMembership, teacher: bool, assignment_id: int | None, pending_only: bool, page: int, page_size: int):
        member_ids = {item.id for item in self.members.values() if item.campus_membership_id == campus_membership.id}
        class_ids = {item.class_id for item in self.members.values() if item.campus_membership_id == campus_membership.id and item.status == ClassMembershipStatus.ACTIVE}
        values = [item for item in self.submission_values.values() if (item.class_id in class_ids if teacher else item.student_membership_id in member_ids)]
        if assignment_id is not None:
            values = [item for item in values if item.assignment_id == assignment_id]
        if pending_only:
            values = [item for item in values if self.version(item.id, item.latest_version_number or 0).status == SubmissionStatus.SUBMITTED]
        values.sort(key=lambda item: item.id, reverse=True)
        start = (page - 1) * page_size
        return values[start:start + page_size], len(values)

    def pending_assignment_page(self, *, campus_membership_id: int, now: datetime, page: int, page_size: int):
        member = next(item for item in self.members.values() if item.campus_membership_id == campus_membership_id)
        values = []
        for assignment in self.assignments.values():
            if assignment.class_id != member.class_id or assignment.status != TeachingAssignmentStatus.PUBLISHED or not assignment.due_at or assignment.due_at <= now:
                continue
            submission = self.submission_for_student(assignment.id, member.id)
            version = self.version(submission.id, submission.latest_version_number or 0) if submission else None
            if submission is None or (version is not None and version.status == SubmissionStatus.RETURNED):
                values.append((assignment, submission, version))
        values.sort(key=lambda item: (item[0].due_at, item[0].id))
        start = (page - 1) * page_size
        return values[start:start + page_size], len(values)

    def version_page(self, submission_id: int, *, page: int, page_size: int):
        values = [item for (parent_id, _), item in self.version_values.items() if parent_id == submission_id]
        values.sort(key=lambda item: item.version_number, reverse=True)
        start = (page - 1) * page_size
        return values[start:start + page_size], len(values)

    def notification_page(self, user_id: int, *, unread_only: bool, page: int, page_size: int):
        all_values = [item for item in self.notification_values.values() if item.recipient_user_id == user_id]
        unread = sum(item.read_at is None for item in all_values)
        values = [item for item in all_values if item.read_at is None] if unread_only else all_values
        values.sort(key=lambda item: item.id, reverse=True)
        start = (page - 1) * page_size
        return values[start:start + page_size], len(values), unread

    def notification_for_user(self, notification_id: int, user_id: int, *, for_update: bool = False):
        del for_update
        value = self.notification_values.get(notification_id)
        return value if value is not None and value.recipient_user_id == user_id else None


class SubmissionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeSubmissionRepository()
        self.service = SubmissionService(self.repository)  # type: ignore[arg-type]
        self.teacher_a = identity(self.repository.users[1])
        self.teacher_b = identity(self.repository.users[2])
        self.student_a = identity(self.repository.users[3])
        self.student_b = identity(self.repository.users[4])

    def submit(self, key: str, expected: int = 0, summary: str = "完成字符串反转"):
        return self.service.submit(
            self.student_a,
            assignment_id=401,
            request_key=key,
            expected_latest_version=expected,
            summary=summary,
            repository_url="https://github.com/example/reverse-string",
            repository_ref="main",
            source_project_id=501,
        )

    def test_return_resubmit_accept_and_notifications_keep_history(self) -> None:
        pending = self.service.pending_assignments(self.student_a, page=1, page_size=20)
        self.assertEqual(pending["total"], 1)
        v1, replayed = self.submit("request_v1")
        self.assertFalse(replayed)
        same, replayed = self.submit("request_v1", 0)
        self.assertTrue(replayed)
        self.assertEqual(same["id"], v1["id"])
        returned, replayed = self.service.feedback(
            self.teacher_a,
            submission_id=v1["id"],
            version_number=1,
            expected_revision=v1["revision"],
            decision=FeedbackDecision.RETURN,
            comment="请补充空字符串测试",
        )
        self.assertFalse(replayed)
        self.assertEqual(returned["decision"], FeedbackDecision.RETURN)
        pending = self.service.pending_assignments(self.student_a, page=1, page_size=20)
        self.assertEqual(pending["items"][0]["current_status"], SubmissionStatus.RETURNED)
        v2, _ = self.submit("request_v2", 1, "补充空字符串和中文测试")
        accepted, replayed = self.service.feedback(
            self.teacher_a,
            submission_id=v2["id"],
            version_number=2,
            expected_revision=v2["revision"],
            decision=FeedbackDecision.ACCEPT,
            comment="符合交付要求",
        )
        self.assertFalse(replayed)
        self.assertEqual(accepted["decision"], FeedbackDecision.ACCEPT)
        self.assertEqual(self.service.pending_assignments(self.student_a, page=1, page_size=20)["total"], 0)
        history = self.service.versions(
            self.student_a, submission_id=v2["id"], page=1, page_size=20
        )
        self.assertEqual([item["status"] for item in history["items"]], [SubmissionStatus.ACCEPTED, SubmissionStatus.RETURNED])
        self.assertEqual(len(self.repository.learning_records), 1)
        record = next(iter(self.repository.learning_records.values()))
        self.assertIsNone(record.duration_minutes)
        self.assertIsNone(record.task_id)
        notifications = self.service.notifications(
            self.student_a, unread_only=False, page=1, page_size=20
        )
        self.assertEqual(notifications["unread_count"], 2)
        read = self.service.read_notification(
            self.student_a, notification_id=notifications["items"][0]["id"]
        )
        self.assertIsNotNone(read["read_at"])

    def test_cross_class_student_project_and_old_version_are_rejected(self) -> None:
        value, _ = self.submit("request_v1", 0)
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_submission(self.teacher_b, submission_id=value["id"])
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_submission(self.student_b, submission_id=value["id"])
        with self.assertRaises(ResourceNotFoundError):
            self.service.submit(
                self.student_a,
                assignment_id=401,
                request_key="wrong_project",
                expected_latest_version=1,
                summary="非法来源",
                repository_url=None,
                repository_ref=None,
                source_project_id=502,
            )
        with self.assertRaises(ResourceNotFoundError):
            self.service.feedback(
                self.teacher_a,
                submission_id=value["id"],
                version_number=2,
                expected_revision=value["revision"],
                decision=FeedbackDecision.ACCEPT,
                comment="不存在版本",
            )

    def test_closed_allows_pending_feedback_but_archived_rejects_it(self) -> None:
        value, _ = self.submit("request_v1", 0)
        self.repository.assignments[401].status = TeachingAssignmentStatus.CLOSED
        result, replayed = self.service.feedback(
            self.teacher_a,
            submission_id=value["id"],
            version_number=1,
            expected_revision=value["revision"],
            decision=FeedbackDecision.RETURN,
            comment="任务关闭后完成评阅",
        )
        self.assertFalse(replayed)
        self.assertEqual(result["decision"], FeedbackDecision.RETURN)

        self.repository.assignments[401].status = TeachingAssignmentStatus.PUBLISHED
        second, _ = self.submit("request_v2", 1)
        self.repository.assignments[401].status = TeachingAssignmentStatus.ARCHIVED
        with self.assertRaises(ConflictError):
            self.service.feedback(
                self.teacher_a,
                submission_id=second["id"],
                version_number=2,
                expected_revision=second["revision"],
                decision=FeedbackDecision.ACCEPT,
                comment="不应成功",
            )

    def test_repository_url_boundary(self) -> None:
        valid = SubmissionCreateRequest(
            request_key="request_01",
            expected_latest_version=0,
            summary="完成",
            repository_url="https://GitHub.com/example/demo/",
        )
        self.assertEqual(valid.repository_url, "https://github.com/example/demo")
        for value in (
            "javascript:alert(1)",
            "http://github.com/example/demo",
            "https://user:pass@github.com/example/demo",
            "https://127.0.0.1/example/demo",
            "https://github.com/example/demo?token=secret",
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                SubmissionCreateRequest(
                    request_key="request_01",
                    expected_latest_version=0,
                    summary="完成",
                    repository_url=value,
                )

    def test_notification_is_recipient_scoped(self) -> None:
        value, _ = self.submit("request_v1", 0)
        self.service.feedback(
            self.teacher_a,
            submission_id=value["id"],
            version_number=1,
            expected_revision=value["revision"],
            decision=FeedbackDecision.RETURN,
            comment="修改后再交",
        )
        notification_id = next(iter(self.repository.notification_values))
        with self.assertRaises(ResourceNotFoundError):
            self.service.read_notification(
                self.student_b, notification_id=notification_id
            )


class SubmissionAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=SubmissionService)
        self.current_user = identity(make_user(3))
        self.app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.app.dependency_overrides[get_submission_service] = lambda: self.service

    @staticmethod
    def response_data() -> dict[str, object]:
        return {
            "id": 1,
            "class_id": 2,
            "assignment_id": 3,
            "assignment_title": "反转字符串",
            "assignment_due_at": NOW + timedelta(days=1),
            "student_username": "student",
            "latest_version_number": 1,
            "revision": 1,
            "created_at": NOW,
            "updated_at": NOW,
            "latest_version": {
                "id": 4,
                "version_number": 1,
                "summary": "完成",
                "repository_url": None,
                "repository_ref": None,
                "source_project_title": None,
                "has_project_reference": False,
                "status": "submitted",
                "submitted_at": NOW,
                "reviewed_at": None,
                "revision": 1,
                "feedback": None,
            },
            "can_review": False,
            "can_submit_next": False,
            "is_owner": True,
        }

    def test_create_and_replay_status_codes(self) -> None:
        self.service.submit.return_value = (self.response_data(), False)
        body = {
            "request_key": "request_01",
            "expected_latest_version": 0,
            "summary": "完成",
        }
        created = request(
            self.app,
            "POST",
            "/api/v1/campus/assignments/3/submissions",
            body=body,
        )
        self.assertEqual(created.status_code, 201)
        self.service.submit.return_value = (self.response_data(), True)
        replayed = request(
            self.app,
            "POST",
            "/api/v1/campus/assignments/3/submissions",
            body=body,
        )
        self.assertEqual(replayed.status_code, 200)

    def test_feedback_create_and_replay_status_codes(self) -> None:
        result = {
            "id": 8,
            "decision": "return",
            "comment": "补充边界测试",
            "created_at": NOW,
        }
        body = {
            "expected_revision": 1,
            "decision": "return",
            "comment": "补充边界测试",
        }
        self.service.feedback.return_value = (result, False)
        created = request(
            self.app,
            "POST",
            "/api/v1/campus/submissions/1/versions/1/feedback",
            body=body,
        )
        self.assertEqual(created.status_code, 201)

        self.service.feedback.return_value = (result, True)
        replayed = request(
            self.app,
            "POST",
            "/api/v1/campus/submissions/1/versions/1/feedback",
            body=body,
        )
        self.assertEqual(replayed.status_code, 200)

    def test_invalid_url_and_pagination_stop_at_boundary(self) -> None:
        invalid = request(
            self.app,
            "POST",
            "/api/v1/campus/assignments/3/submissions",
            body={
                "request_key": "request_01",
                "expected_latest_version": 0,
                "summary": "完成",
                "repository_url": "http://127.0.0.1/private",
            },
        )
        self.assertEqual(invalid.status_code, 422)
        bounded = request(
            self.app,
            "GET",
            "/api/v1/campus/submissions?page_size=101",
        )
        self.assertEqual(bounded.status_code, 422)
        self.service.submit.assert_not_called()
        self.service.submissions.assert_not_called()

    def test_routes_require_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_submission_service] = lambda: self.service
        for method, path in (
            ("GET", "/api/v1/campus/submissions"),
            ("GET", "/api/v1/campus/submissions/1"),
            ("GET", "/api/v1/notifications"),
        ):
            with self.subTest(path=path):
                self.assertEqual(request(app, method, path).status_code, 401)


if __name__ == "__main__":
    unittest.main()
