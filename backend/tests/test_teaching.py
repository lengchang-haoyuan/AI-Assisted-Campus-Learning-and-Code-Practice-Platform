from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
import unittest

from app.api.deps import get_current_user, get_teaching_service
from app.core.exceptions import ConflictError, PermissionDeniedError, ResourceNotFoundError
from app.main import create_app
from app.models.campus import CampusMembership, CampusRole, MembershipStatus
from app.models.enums import ProjectDifficulty, ProjectStatus
from app.models.project import Project
from app.models.teaching import (
    ClassMemberRole,
    ClassMembership,
    ClassMembershipStatus,
    TeachingAssignment,
    TeachingAssignmentStatus,
    TeachingClass,
)
from app.models.user import User
from app.services.auth import UserIdentity
from app.services.teaching import TeachingService
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)


def make_user(user_id: int) -> User:
    return User(
        id=user_id,
        username=f"user_{user_id}",
        email=f"user_{user_id}@example.com",
        password_hash="not-used",
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
        is_active=user.is_active,
        created_at=user.created_at,
        auth_version=0,
    )


class FakeTeachingRepository:
    def __init__(self) -> None:
        self.users = {value.id: value for value in map(make_user, range(1, 6))}
        roles = {
            1: CampusRole.TEACHER,
            2: CampusRole.TEACHER,
            3: CampusRole.STUDENT,
            4: CampusRole.STUDENT,
            5: CampusRole.ADMINISTRATOR,
        }
        self.campus_memberships = {
            user_id: CampusMembership(
                id=100 + user_id,
                user_id=user_id,
                role=role,
                status=MembershipStatus.ACTIVE,
                verified_by_user_id=5,
                verified_at=NOW,
                revision=1,
                created_at=NOW,
                updated_at=NOW,
            )
            for user_id, role in roles.items()
        }
        self.classes: dict[int, TeachingClass] = {}
        self.members: dict[int, ClassMembership] = {}
        self.assignments: dict[int, TeachingAssignment] = {}
        self.projects: dict[int, Project] = {}
        self.next_id = 1000

    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield

    def add(self, value: object) -> None:
        if getattr(value, "id", None) is None:
            setattr(value, "id", self.next_id)
            self.next_id += 1
        if hasattr(value, "created_at") and getattr(value, "created_at", None) is None:
            setattr(value, "created_at", NOW)
            setattr(value, "updated_at", NOW)
        if isinstance(value, TeachingClass):
            self.classes[value.id] = value
        elif isinstance(value, ClassMembership):
            self.members[value.id] = value
        elif isinstance(value, TeachingAssignment):
            self.assignments[value.id] = value

    def campus_membership_for_user(self, user_id: int) -> CampusMembership | None:
        return self.campus_memberships.get(user_id)

    def campus_member_with_user(self, membership_id: int) -> tuple[CampusMembership, User] | None:
        membership = next(
            (value for value in self.campus_memberships.values() if value.id == membership_id),
            None,
        )
        return (membership, self.users[membership.user_id]) if membership else None

    def teaching_class(self, class_id: int, *, for_update: bool = False) -> TeachingClass | None:
        del for_update
        return self.classes.get(class_id)

    def class_membership(
        self,
        class_id: int,
        campus_membership_id: int,
        *,
        for_update: bool = False,
    ) -> ClassMembership | None:
        del for_update
        return next(
            (
                value
                for value in self.members.values()
                if value.class_id == class_id
                and value.campus_membership_id == campus_membership_id
            ),
            None,
        )

    def class_membership_by_id(
        self, class_id: int, member_id: int, *, for_update: bool = False
    ) -> ClassMembership | None:
        del for_update
        value = self.members.get(member_id)
        return value if value is not None and value.class_id == class_id else None

    def class_page(self, *, actor_membership: CampusMembership, page: int, page_size: int):
        if actor_membership.role == CampusRole.ADMINISTRATOR:
            rows = [(value, None) for value in self.classes.values()]
        else:
            rows = []
            for value in self.classes.values():
                member = self.class_membership(value.id, actor_membership.id)
                if member is not None and member.status == ClassMembershipStatus.ACTIVE:
                    rows.append((value, member))
        rows.sort(key=lambda row: row[0].id, reverse=True)
        start = (page - 1) * page_size
        return rows[start : start + page_size], len(rows)

    def class_member_page(self, *, class_id: int, page: int, page_size: int):
        rows = []
        for member in self.members.values():
            if member.class_id != class_id:
                continue
            campus_member, user = self.campus_member_with_user(member.campus_membership_id)
            rows.append((member, campus_member, user))
        rows.sort(key=lambda row: row[0].id)
        start = (page - 1) * page_size
        return rows[start : start + page_size], len(rows)

    def assignment(self, assignment_id: int, *, for_update: bool = False) -> TeachingAssignment | None:
        del for_update
        return self.assignments.get(assignment_id)

    def assignment_page(self, *, class_id: int, include_drafts: bool, page: int, page_size: int):
        values = [
            value
            for value in self.assignments.values()
            if value.class_id == class_id
            and (include_drafts or value.status != TeachingAssignmentStatus.DRAFT)
        ]
        values.sort(key=lambda value: (value.due_at is None, value.due_at or NOW, value.id))
        start = (page - 1) * page_size
        return values[start : start + page_size], len(values)

    def owned_project(self, project_id: int, owner_id: int) -> Project | None:
        value = self.projects.get(project_id)
        return value if value is not None and value.owner_id == owner_id else None


class TeachingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeTeachingRepository()
        self.service = TeachingService(self.repository)  # type: ignore[arg-type]
        self.teacher_a = identity(self.repository.users[1])
        self.teacher_b = identity(self.repository.users[2])
        self.student_a = identity(self.repository.users[3])
        self.student_b = identity(self.repository.users[4])
        self.admin = identity(self.repository.users[5])
        self.class_a = self.service.create_class(
            self.teacher_a,
            name="A 班",
            course_title="项目实践",
            term_label="2026 秋",
        )
        self.class_b = self.service.create_class(
            self.teacher_b,
            name="B 班",
            course_title="项目实践",
            term_label="2026 秋",
        )

    def add_student_a(self) -> ClassMembership:
        result = self.service.add_member(
            self.teacher_a,
            class_id=self.class_a.id,
            campus_membership_id=103,
            member_role=ClassMemberRole.STUDENT,
        )
        return self.repository.members[result.id]

    def create_draft(self) -> TeachingAssignment:
        result = self.service.create_assignment(
            self.teacher_a,
            class_id=self.class_a.id,
            title="实现字符串反转",
            instructions="编写函数并覆盖空字符串与中文输入。",
            learning_objectives=["理解切片"],
            acceptance_criteria=["测试通过", "说明复杂度"],
            due_at=datetime.now(UTC) + timedelta(days=2),
            source_project_id=None,
        )
        return self.repository.assignments[result.id]

    def test_two_teachers_and_students_are_isolated_by_class(self) -> None:
        self.add_student_a()
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_class(self.teacher_a, class_id=self.class_b.id)
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_class(self.student_b, class_id=self.class_a.id)
        with self.assertRaises(ResourceNotFoundError):
            self.service.create_assignment(
                self.teacher_a,
                class_id=self.class_b.id,
                title="越权任务",
                instructions="不应允许教师向其他班级布置任务。",
                learning_objectives=["无"],
                acceptance_criteria=["无"],
                due_at=datetime.now(UTC) + timedelta(days=1),
                source_project_id=None,
            )

    def test_member_role_duplicate_and_inactive_target_are_rejected(self) -> None:
        self.add_student_a()
        with self.assertRaises(ConflictError):
            self.service.add_member(
                self.teacher_a,
                class_id=self.class_a.id,
                campus_membership_id=103,
                member_role=ClassMemberRole.STUDENT,
            )
        with self.assertRaises(PermissionDeniedError):
            self.service.add_member(
                self.teacher_a,
                class_id=self.class_a.id,
                campus_membership_id=102,
                member_role=ClassMemberRole.TEACHER,
            )
        self.repository.campus_memberships[4].status = MembershipStatus.SUSPENDED
        with self.assertRaises(ConflictError):
            self.service.add_member(
                self.teacher_a,
                class_id=self.class_a.id,
                campus_membership_id=104,
                member_role=ClassMemberRole.STUDENT,
            )

    def test_draft_is_hidden_then_published_deadline_can_only_extend(self) -> None:
        self.add_student_a()
        assignment = self.create_draft()
        student_page = self.service.assignments(
            self.student_a, class_id=self.class_a.id, page=1, page_size=20
        )
        self.assertEqual(student_page.total, 0)

        published = self.service.publish_assignment(
            self.teacher_a,
            assignment_id=assignment.id,
            expected_revision=assignment.revision,
        )
        self.assertEqual(
            self.service.assignments(
                self.student_a, class_id=self.class_a.id, page=1, page_size=20
            ).total,
            1,
        )
        with self.assertRaises(ConflictError):
            self.service.update_assignment(
                self.teacher_a,
                assignment_id=assignment.id,
                expected_revision=published.revision,
                values={"title": "静默改题"},
            )
        with self.assertRaises(ConflictError):
            self.service.update_assignment(
                self.teacher_a,
                assignment_id=assignment.id,
                expected_revision=published.revision,
                values={"due_at": assignment.due_at - timedelta(hours=1)},
            )
        extended = self.service.update_assignment(
            self.teacher_a,
            assignment_id=assignment.id,
            expected_revision=published.revision,
            values={"due_at": assignment.due_at + timedelta(days=1)},
        )
        closed = self.service.close_assignment(
            self.teacher_a,
            assignment_id=assignment.id,
            expected_revision=extended.revision,
        )
        archived = self.service.archive_assignment(
            self.teacher_a,
            assignment_id=assignment.id,
            expected_revision=closed.revision,
        )
        self.assertEqual(archived.status, TeachingAssignmentStatus.ARCHIVED)

    def test_student_exit_and_class_archive_permissions(self) -> None:
        member = self.add_student_a()
        left = self.service.update_member(
            self.student_a,
            class_id=self.class_a.id,
            member_id=member.id,
            expected_revision=member.revision,
            status=ClassMembershipStatus.LEFT,
        )
        self.assertEqual(left.status, ClassMembershipStatus.LEFT)
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_class(self.student_a, class_id=self.class_a.id)
        with self.assertRaises(ConflictError):
            self.service.add_member(
                self.teacher_a,
                class_id=self.class_a.id,
                campus_membership_id=103,
                member_role=ClassMemberRole.STUDENT,
            )

        archived = self.service.update_class(
            self.teacher_a,
            class_id=self.class_a.id,
            expected_revision=self.class_a.revision,
            values={"status": "archived"},
        )
        self.assertEqual(archived.status.value, "archived")
        with self.assertRaises(ConflictError):
            self.service.add_member(
                self.admin,
                class_id=self.class_a.id,
                campus_membership_id=104,
                member_role=ClassMemberRole.STUDENT,
            )

    def test_private_project_is_snapshotted_with_a_whitelist(self) -> None:
        project = Project(
            id=700,
            owner_id=1,
            name="Python 模板",
            description="练习项目",
            difficulty=ProjectDifficulty.BEGINNER,
            status=ProjectStatus.NOT_STARTED,
            context_data={"private_note": "不得进入班级"},
            repository_url="https://example.com/private.git",
            created_at=NOW,
            updated_at=NOW,
        )
        self.repository.projects[project.id] = project
        result = self.service.create_assignment(
            self.teacher_a,
            class_id=self.class_a.id,
            title="模板任务",
            instructions="从经过筛选的项目模板快照开始练习。",
            learning_objectives=["阅读需求"],
            acceptance_criteria=["形成结果"],
            due_at=datetime.now(UTC) + timedelta(days=1),
            source_project_id=project.id,
        )
        self.assertEqual(result.source_project_snapshot["name"], "Python 模板")
        self.assertNotIn("context_data", result.source_project_snapshot)
        self.assertNotIn("repository_url", result.source_project_snapshot)

    def test_pagination_is_explicit_and_stable(self) -> None:
        page = self.service.classes(self.admin, page=2, page_size=1)
        self.assertEqual((page.total, page.total_pages, len(page.items)), (2, 2, 1))

    def test_invalid_or_suspended_teacher_and_past_due_are_rejected(self) -> None:
        with self.assertRaises(PermissionDeniedError):
            self.service.create_class(
                self.student_a,
                name="伪造教师班",
                course_title="项目实践",
                term_label="2026 秋",
            )
        with self.assertRaises(ConflictError):
            self.service.create_assignment(
                self.teacher_a,
                class_id=self.class_a.id,
                title="过期任务",
                instructions="这个任务的截止时间已经无效。",
                learning_objectives=["识别日期"],
                acceptance_criteria=["拒绝保存"],
                due_at=datetime.now(UTC) - timedelta(minutes=1),
                source_project_id=None,
            )
        self.repository.campus_memberships[1].status = MembershipStatus.SUSPENDED
        with self.assertRaises(PermissionDeniedError):
            self.service.get_class(self.teacher_a, class_id=self.class_a.id)


class TeachingAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=TeachingService)
        self.current_user = identity(make_user(1))
        self.app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.app.dependency_overrides[get_teaching_service] = lambda: self.service

    def test_bounds_and_timezone_are_validated_before_service(self) -> None:
        response = request(
            self.app,
            "GET",
            "/api/v1/campus/classes?page_size=101",
        )
        self.assertEqual(response.status_code, 422)
        response = request(
            self.app,
            "POST",
            "/api/v1/campus/classes/1/assignments",
            body={
                "title": "任务",
                "instructions": "一段足够长度的任务说明。",
                "learning_objectives": ["目标"],
                "acceptance_criteria": ["要求"],
                "due_at": "2026-09-10T12:00:00",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.service.create_assignment.assert_not_called()

    def test_routes_require_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_teaching_service] = lambda: self.service
        for method, path in (
            ("GET", "/api/v1/campus/classes"),
            ("GET", "/api/v1/campus/classes/1"),
            ("GET", "/api/v1/campus/assignments/1"),
        ):
            with self.subTest(path=path):
                self.assertEqual(request(app, method, path).status_code, 401)


if __name__ == "__main__":
    unittest.main()
