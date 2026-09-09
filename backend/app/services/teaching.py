from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any, Mapping

from app.core.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.campus import CampusMembership, CampusRole, MembershipStatus
from app.models.project import Project
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
from app.repositories.teaching import TeachingRepository
from app.services.auth import UserIdentity


@dataclass(frozen=True, slots=True)
class TeachingClassData:
    id: int
    name: str
    course_title: str
    term_label: str
    status: TeachingClassStatus
    revision: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    viewer_role: str
    viewer_member_id: int | None
    viewer_member_revision: int | None
    can_edit: bool
    can_view_members: bool
    can_manage_members: bool
    can_create_assignments: bool


@dataclass(frozen=True, slots=True)
class ClassMemberData:
    id: int
    campus_membership_id: int
    user_id: int
    username: str
    member_role: ClassMemberRole
    status: ClassMembershipStatus
    joined_at: datetime
    left_at: datetime | None
    revision: int


@dataclass(frozen=True, slots=True)
class TeachingAssignmentData:
    id: int
    class_id: int
    title: str
    instructions: str
    learning_objectives: list[str]
    acceptance_criteria: list[str]
    due_at: datetime | None
    status: TeachingAssignmentStatus
    source_project_snapshot: dict[str, Any] | None
    revision: int
    published_at: datetime | None
    closed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_publish: bool
    can_close: bool
    can_archive: bool


@dataclass(frozen=True, slots=True)
class PageData:
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class TeachingService:
    def __init__(self, repository: TeachingRepository) -> None:
        self._repository = repository

    def _actor(self, current_user: UserIdentity) -> CampusMembership:
        membership = self._repository.campus_membership_for_user(current_user.id)
        if membership is None or membership.status != MembershipStatus.ACTIVE:
            raise PermissionDeniedError("需要有效的校园身份")
        return membership

    def _scoped_class(
        self,
        class_id: int,
        actor: CampusMembership,
        *,
        for_update: bool = False,
        allow_admin: bool = True,
    ) -> tuple[TeachingClass, ClassMembership | None]:
        teaching_class = self._repository.teaching_class(
            class_id, for_update=for_update
        )
        if teaching_class is None:
            raise ResourceNotFoundError("教学班不存在")
        if actor.role == CampusRole.ADMINISTRATOR:
            if not allow_admin:
                raise PermissionDeniedError("管理员没有教学任务正文权限")
            return teaching_class, None
        member = self._repository.class_membership(
            class_id, actor.id, for_update=for_update
        )
        if member is None or member.status != ClassMembershipStatus.ACTIVE:
            raise ResourceNotFoundError("教学班不存在")
        return teaching_class, member

    @staticmethod
    def _teacher_can_manage(
        actor: CampusMembership,
        member: ClassMembership | None,
        teaching_class: TeachingClass,
    ) -> bool:
        return (
            TeachingService._is_class_teacher(actor, member)
            and teaching_class.status == TeachingClassStatus.ACTIVE
        )

    @staticmethod
    def _is_class_teacher(
        actor: CampusMembership, member: ClassMembership | None
    ) -> bool:
        return (
            actor.role == CampusRole.TEACHER
            and member is not None
            and member.member_role == ClassMemberRole.TEACHER
            and member.status == ClassMembershipStatus.ACTIVE
        )

    @classmethod
    def _class_data(
        cls,
        value: TeachingClass,
        actor: CampusMembership,
        member: ClassMembership | None,
    ) -> TeachingClassData:
        teacher_can_manage = cls._teacher_can_manage(actor, member, value)
        is_admin = actor.role == CampusRole.ADMINISTRATOR
        viewer_role = "administrator" if is_admin else str(member.member_role.value)
        return TeachingClassData(
            id=value.id,
            name=value.name,
            course_title=value.course_title,
            term_label=value.term_label,
            status=value.status,
            revision=value.revision,
            archived_at=value.archived_at,
            created_at=value.created_at,
            updated_at=value.updated_at,
            viewer_role=viewer_role,
            viewer_member_id=member.id if member is not None else None,
            viewer_member_revision=member.revision if member is not None else None,
            can_edit=teacher_can_manage,
            can_view_members=teacher_can_manage
            or is_admin
            or cls._is_class_teacher(actor, member),
            can_manage_members=(teacher_can_manage or is_admin)
            and value.status == TeachingClassStatus.ACTIVE,
            can_create_assignments=teacher_can_manage,
        )

    @staticmethod
    def _member_data(
        value: ClassMembership, campus_member: CampusMembership, user: User
    ) -> ClassMemberData:
        return ClassMemberData(
            id=value.id,
            campus_membership_id=campus_member.id,
            user_id=user.id,
            username=user.username,
            member_role=value.member_role,
            status=value.status,
            joined_at=value.joined_at,
            left_at=value.left_at,
            revision=value.revision,
        )

    @staticmethod
    def _assignment_data(
        value: TeachingAssignment, *, teacher_can_manage: bool
    ) -> TeachingAssignmentData:
        return TeachingAssignmentData(
            id=value.id,
            class_id=value.class_id,
            title=value.title,
            instructions=value.instructions,
            learning_objectives=list(value.learning_objectives),
            acceptance_criteria=list(value.acceptance_criteria),
            due_at=value.due_at,
            status=value.status,
            source_project_snapshot=value.source_project_snapshot,
            revision=value.revision,
            published_at=value.published_at,
            closed_at=value.closed_at,
            archived_at=value.archived_at,
            created_at=value.created_at,
            updated_at=value.updated_at,
            can_edit=teacher_can_manage
            and value.status
            in (TeachingAssignmentStatus.DRAFT, TeachingAssignmentStatus.PUBLISHED),
            can_publish=teacher_can_manage
            and value.status == TeachingAssignmentStatus.DRAFT,
            can_close=teacher_can_manage
            and value.status == TeachingAssignmentStatus.PUBLISHED,
            can_archive=teacher_can_manage
            and value.status == TeachingAssignmentStatus.CLOSED,
        )

    @staticmethod
    def _project_snapshot(project: Project) -> dict[str, Any]:
        return {
            "name": project.name,
            "description": project.description,
            "difficulty": project.difficulty.value,
            "language": project.language,
            "framework": project.framework,
            "frontend": project.frontend,
            "backend": project.backend,
            "database": project.database,
            "requirements": project.requirements,
            "output_requirement": project.output_requirement,
            "captured_at": datetime.now(UTC).isoformat(),
        }

    def _snapshot_for_project(
        self, project_id: int | None, owner_id: int
    ) -> tuple[int | None, dict[str, Any] | None]:
        if project_id is None:
            return None, None
        project = self._repository.owned_project(project_id, owner_id)
        if project is None:
            raise ResourceNotFoundError("可引用的项目模板不存在")
        return project.id, self._project_snapshot(project)

    @staticmethod
    def _validate_future_due(due_at: datetime | None, *, required: bool) -> None:
        if due_at is None:
            if required:
                raise ConflictError("发布任务前必须设置截止时间")
            return
        if due_at <= datetime.now(UTC):
            raise ConflictError("截止时间必须晚于当前时间")

    @staticmethod
    def _assert_revision(actual: int, expected: int) -> None:
        if actual != expected:
            raise ConflictError("资源已被更新，请刷新后重试")

    def create_class(
        self,
        current_user: UserIdentity,
        *,
        name: str,
        course_title: str,
        term_label: str,
    ) -> TeachingClassData:
        now = datetime.now(UTC)
        with self._repository.transaction():
            actor = self._actor(current_user)
            if actor.role != CampusRole.TEACHER:
                raise PermissionDeniedError("只有有效教师可以创建教学班")
            teaching_class = TeachingClass(
                name=name,
                course_title=course_title,
                term_label=term_label,
                status=TeachingClassStatus.ACTIVE,
                created_by_membership_id=actor.id,
                revision=1,
            )
            self._repository.add(teaching_class)
            owner_member = ClassMembership(
                class_id=teaching_class.id,
                campus_membership_id=actor.id,
                member_role=ClassMemberRole.TEACHER,
                status=ClassMembershipStatus.ACTIVE,
                joined_by_membership_id=actor.id,
                joined_at=now,
                revision=1,
            )
            self._repository.add(owner_member)
        return self._class_data(teaching_class, actor, owner_member)

    def classes(
        self, current_user: UserIdentity, *, page: int, page_size: int
    ) -> PageData:
        actor = self._actor(current_user)
        rows, total = self._repository.class_page(
            actor_membership=actor, page=page, page_size=page_size
        )
        return PageData(
            items=[self._class_data(value, actor, member) for value, member in rows],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_class(
        self, current_user: UserIdentity, *, class_id: int
    ) -> TeachingClassData:
        actor = self._actor(current_user)
        teaching_class, member = self._scoped_class(class_id, actor)
        return self._class_data(teaching_class, actor, member)

    def update_class(
        self,
        current_user: UserIdentity,
        *,
        class_id: int,
        expected_revision: int,
        values: Mapping[str, object],
    ) -> TeachingClassData:
        with self._repository.transaction():
            actor = self._actor(current_user)
            teaching_class, member = self._scoped_class(
                class_id, actor, for_update=True
            )
            self._assert_revision(teaching_class.revision, expected_revision)
            if teaching_class.status == TeachingClassStatus.ARCHIVED:
                raise ConflictError("已归档班级不能再修改")
            requested_status = values.get("status")
            content_fields = {"name", "course_title", "term_label"} & values.keys()
            if requested_status is not None and content_fields:
                raise ConflictError("归档与班级资料修改必须分开操作")
            if requested_status is not None:
                if requested_status != TeachingClassStatus.ARCHIVED:
                    raise ConflictError("班级只能从有效状态归档")
                if not (
                    actor.role == CampusRole.ADMINISTRATOR
                    or self._teacher_can_manage(actor, member, teaching_class)
                ):
                    raise PermissionDeniedError("无权归档该教学班")
                teaching_class.status = TeachingClassStatus.ARCHIVED
                teaching_class.archived_at = datetime.now(UTC)
            else:
                if not self._teacher_can_manage(actor, member, teaching_class):
                    raise PermissionDeniedError("只有本班有效教师可以编辑班级")
                for field_name in content_fields:
                    setattr(teaching_class, field_name, values[field_name])
            teaching_class.revision += 1
        return self._class_data(teaching_class, actor, member)

    def members(
        self,
        current_user: UserIdentity,
        *,
        class_id: int,
        page: int,
        page_size: int,
    ) -> PageData:
        actor = self._actor(current_user)
        teaching_class, member = self._scoped_class(class_id, actor)
        if not (
            actor.role == CampusRole.ADMINISTRATOR
            or self._is_class_teacher(actor, member)
        ):
            raise PermissionDeniedError("只有班级教师或管理员可以查看成员名单")
        rows, total = self._repository.class_member_page(
            class_id=class_id, page=page, page_size=page_size
        )
        return PageData(
            items=[self._member_data(*row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def add_member(
        self,
        current_user: UserIdentity,
        *,
        class_id: int,
        campus_membership_id: int,
        member_role: ClassMemberRole,
    ) -> ClassMemberData:
        with self._repository.transaction():
            actor = self._actor(current_user)
            teaching_class, actor_member = self._scoped_class(
                class_id, actor, for_update=True
            )
            if teaching_class.status != TeachingClassStatus.ACTIVE:
                raise ConflictError("已归档班级不能增加成员")
            is_admin = actor.role == CampusRole.ADMINISTRATOR
            is_teacher = self._teacher_can_manage(actor, actor_member, teaching_class)
            if not (is_admin or is_teacher):
                raise PermissionDeniedError("无权增加班级成员")
            if is_teacher and member_role != ClassMemberRole.STUDENT:
                raise PermissionDeniedError("教师只能向本班增加学生")
            target_row = self._repository.campus_member_with_user(
                campus_membership_id
            )
            if target_row is None:
                raise ResourceNotFoundError("校园成员不存在")
            target_membership, target_user = target_row
            if (
                target_membership.status != MembershipStatus.ACTIVE
                or not target_user.is_active
            ):
                raise ConflictError("目标校园成员当前不可用")
            expected_role = (
                CampusRole.TEACHER
                if member_role == ClassMemberRole.TEACHER
                else CampusRole.STUDENT
            )
            if target_membership.role != expected_role:
                raise ConflictError("班级角色必须与已核验校园身份一致")
            if self._repository.class_membership(
                class_id, campus_membership_id, for_update=True
            ) is not None:
                raise ConflictError("该成员已经加入过此班级")
            value = ClassMembership(
                class_id=class_id,
                campus_membership_id=campus_membership_id,
                member_role=member_role,
                status=ClassMembershipStatus.ACTIVE,
                joined_by_membership_id=actor.id,
                joined_at=datetime.now(UTC),
                revision=1,
            )
            self._repository.add(value)
        return self._member_data(value, target_membership, target_user)

    def update_member(
        self,
        current_user: UserIdentity,
        *,
        class_id: int,
        member_id: int,
        expected_revision: int,
        status: ClassMembershipStatus,
    ) -> ClassMemberData:
        with self._repository.transaction():
            actor = self._actor(current_user)
            teaching_class, actor_member = self._scoped_class(
                class_id, actor, for_update=True
            )
            if teaching_class.status != TeachingClassStatus.ACTIVE:
                raise ConflictError("已归档班级不能变更成员")
            target = self._repository.class_membership_by_id(
                class_id, member_id, for_update=True
            )
            if target is None:
                raise ResourceNotFoundError("班级成员不存在")
            self._assert_revision(target.revision, expected_revision)
            if target.status != ClassMembershipStatus.ACTIVE:
                raise ConflictError("该成员已经退出或被移除")
            is_self_leave = (
                actor_member is not None
                and actor_member.id == target.id
                and target.member_role == ClassMemberRole.STUDENT
                and status == ClassMembershipStatus.LEFT
            )
            is_admin_remove = (
                actor.role == CampusRole.ADMINISTRATOR
                and status == ClassMembershipStatus.REMOVED
            )
            is_teacher_remove = (
                self._teacher_can_manage(actor, actor_member, teaching_class)
                and target.member_role == ClassMemberRole.STUDENT
                and status == ClassMembershipStatus.REMOVED
            )
            if not (is_self_leave or is_admin_remove or is_teacher_remove):
                raise PermissionDeniedError("无权执行该成员状态变更")
            target.status = status
            target.left_at = datetime.now(UTC)
            target.revision += 1
            target_row = self._repository.campus_member_with_user(
                target.campus_membership_id
            )
            if target_row is None:
                raise RuntimeError("班级成员关联的校园身份不存在")
        return self._member_data(target, *target_row)

    def create_assignment(
        self,
        current_user: UserIdentity,
        *,
        class_id: int,
        title: str,
        instructions: str,
        learning_objectives: list[str],
        acceptance_criteria: list[str],
        due_at: datetime | None,
        source_project_id: int | None,
    ) -> TeachingAssignmentData:
        self._validate_future_due(due_at, required=False)
        with self._repository.transaction():
            actor = self._actor(current_user)
            teaching_class, member = self._scoped_class(
                class_id, actor, for_update=True, allow_admin=False
            )
            if not self._teacher_can_manage(actor, member, teaching_class):
                raise PermissionDeniedError("只有本班有效教师可以创建任务")
            project_id, snapshot = self._snapshot_for_project(
                source_project_id, current_user.id
            )
            value = TeachingAssignment(
                class_id=class_id,
                created_by_class_membership_id=member.id,
                title=title,
                instructions=instructions,
                learning_objectives=learning_objectives,
                acceptance_criteria=acceptance_criteria,
                due_at=due_at,
                status=TeachingAssignmentStatus.DRAFT,
                source_project_id=project_id,
                source_project_snapshot=snapshot,
                revision=1,
            )
            self._repository.add(value)
        return self._assignment_data(value, teacher_can_manage=True)

    def assignments(
        self,
        current_user: UserIdentity,
        *,
        class_id: int,
        page: int,
        page_size: int,
    ) -> PageData:
        actor = self._actor(current_user)
        teaching_class, member = self._scoped_class(
            class_id, actor, allow_admin=False
        )
        teacher_can_manage = self._teacher_can_manage(actor, member, teaching_class)
        teacher_can_view_drafts = self._is_class_teacher(actor, member)
        values, total = self._repository.assignment_page(
            class_id=class_id,
            include_drafts=teacher_can_view_drafts,
            page=page,
            page_size=page_size,
        )
        return PageData(
            items=[
                self._assignment_data(value, teacher_can_manage=teacher_can_manage)
                for value in values
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_assignment(
        self, current_user: UserIdentity, *, assignment_id: int
    ) -> TeachingAssignmentData:
        actor = self._actor(current_user)
        value = self._repository.assignment(assignment_id)
        if value is None:
            raise ResourceNotFoundError("教学任务不存在")
        teaching_class, member = self._scoped_class(
            value.class_id, actor, allow_admin=False
        )
        teacher_can_manage = self._teacher_can_manage(actor, member, teaching_class)
        if value.status == TeachingAssignmentStatus.DRAFT and not self._is_class_teacher(
            actor, member
        ):
            raise ResourceNotFoundError("教学任务不存在")
        return self._assignment_data(value, teacher_can_manage=teacher_can_manage)

    def update_assignment(
        self,
        current_user: UserIdentity,
        *,
        assignment_id: int,
        expected_revision: int,
        values: Mapping[str, object],
    ) -> TeachingAssignmentData:
        discovered = self._repository.assignment(assignment_id)
        if discovered is None:
            raise ResourceNotFoundError("教学任务不存在")
        with self._repository.transaction():
            actor = self._actor(current_user)
            teaching_class, member = self._scoped_class(
                discovered.class_id, actor, for_update=True, allow_admin=False
            )
            value = self._repository.assignment(assignment_id, for_update=True)
            if value is None or value.class_id != teaching_class.id:
                raise ResourceNotFoundError("教学任务不存在")
            if not self._teacher_can_manage(actor, member, teaching_class):
                raise PermissionDeniedError("只有本班有效教师可以修改任务")
            self._assert_revision(value.revision, expected_revision)
            if value.status == TeachingAssignmentStatus.DRAFT:
                if "due_at" in values:
                    self._validate_future_due(values["due_at"], required=False)  # type: ignore[arg-type]
                for field_name in (
                    "title",
                    "instructions",
                    "learning_objectives",
                    "acceptance_criteria",
                    "due_at",
                ):
                    if field_name in values:
                        setattr(value, field_name, values[field_name])
                if "source_project_id" in values:
                    project_id, snapshot = self._snapshot_for_project(
                        values["source_project_id"], current_user.id  # type: ignore[arg-type]
                    )
                    value.source_project_id = project_id
                    value.source_project_snapshot = snapshot
            elif value.status == TeachingAssignmentStatus.PUBLISHED:
                if set(values) != {"due_at"}:
                    raise ConflictError("发布后题意与验收标准已冻结，只能延长截止时间")
                due_at = values["due_at"]
                self._validate_future_due(due_at, required=True)  # type: ignore[arg-type]
                if value.due_at is not None and due_at <= value.due_at:  # type: ignore[operator]
                    raise ConflictError("发布后只能延长截止时间")
                value.due_at = due_at  # type: ignore[assignment]
            else:
                raise ConflictError("已关闭或归档任务不能修改")
            value.revision += 1
        return self._assignment_data(value, teacher_can_manage=True)

    def transition_assignment(
        self,
        current_user: UserIdentity,
        *,
        assignment_id: int,
        expected_revision: int,
        target_status: TeachingAssignmentStatus,
    ) -> TeachingAssignmentData:
        transitions = {
            TeachingAssignmentStatus.PUBLISHED: TeachingAssignmentStatus.DRAFT,
            TeachingAssignmentStatus.CLOSED: TeachingAssignmentStatus.PUBLISHED,
            TeachingAssignmentStatus.ARCHIVED: TeachingAssignmentStatus.CLOSED,
        }
        discovered = self._repository.assignment(assignment_id)
        if discovered is None:
            raise ResourceNotFoundError("教学任务不存在")
        with self._repository.transaction():
            actor = self._actor(current_user)
            teaching_class, member = self._scoped_class(
                discovered.class_id, actor, for_update=True, allow_admin=False
            )
            value = self._repository.assignment(assignment_id, for_update=True)
            if value is None or value.class_id != teaching_class.id:
                raise ResourceNotFoundError("教学任务不存在")
            if not self._teacher_can_manage(actor, member, teaching_class):
                raise PermissionDeniedError("只有本班有效教师可以变更任务状态")
            self._assert_revision(value.revision, expected_revision)
            if transitions.get(target_status) != value.status:
                raise ConflictError("任务状态不能执行该流转")
            now = datetime.now(UTC)
            if target_status == TeachingAssignmentStatus.PUBLISHED:
                self._validate_future_due(value.due_at, required=True)
                value.published_at = now
                self._repository.add_assignment_notifications(
                    value.id, value.class_id, now
                )
            elif target_status == TeachingAssignmentStatus.CLOSED:
                value.closed_at = now
            elif target_status == TeachingAssignmentStatus.ARCHIVED:
                value.archived_at = now
            value.status = target_status
            value.revision += 1
        return self._assignment_data(value, teacher_can_manage=True)

    def publish_assignment(
        self,
        current_user: UserIdentity,
        *,
        assignment_id: int,
        expected_revision: int,
    ) -> TeachingAssignmentData:
        return self.transition_assignment(
            current_user,
            assignment_id=assignment_id,
            expected_revision=expected_revision,
            target_status=TeachingAssignmentStatus.PUBLISHED,
        )

    def close_assignment(
        self,
        current_user: UserIdentity,
        *,
        assignment_id: int,
        expected_revision: int,
    ) -> TeachingAssignmentData:
        return self.transition_assignment(
            current_user,
            assignment_id=assignment_id,
            expected_revision=expected_revision,
            target_status=TeachingAssignmentStatus.CLOSED,
        )

    def archive_assignment(
        self,
        current_user: UserIdentity,
        *,
        assignment_id: int,
        expected_revision: int,
    ) -> TeachingAssignmentData:
        return self.transition_assignment(
            current_user,
            assignment_id=assignment_id,
            expected_revision=expected_revision,
            target_status=TeachingAssignmentStatus.ARCHIVED,
        )
