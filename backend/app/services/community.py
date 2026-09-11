from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil

from app.core.exceptions import (
    ConflictError,
    PermissionDeniedError,
    RateLimitError,
    ResourceNotFoundError,
)
from app.models.campus import CampusMembership, CampusRole, MembershipStatus
from app.models.community import (
    Comment,
    CommentModerationStatus,
    CommunityGovernanceAction,
    CommunityGovernanceCase,
    CommunityPublication,
    CommunityPublicationVersion,
    GovernanceActionType,
    GovernanceCaseStatus,
    GovernanceCaseType,
    PublicationKind,
    PublicationStatus,
)
from app.models.enums import ProjectDifficulty, ProjectStatus
from app.models.project import Project
from app.models.submission import Notification
from app.repositories.community import (
    CommunityProjectRecord,
    CommunityRepository,
    PublicationRecord,
)
from app.services.auth import UserIdentity


@dataclass(frozen=True, slots=True)
class TagData:
    id: int
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class TagSummaryData(TagData):
    project_count: int


@dataclass(frozen=True, slots=True)
class CommunityOwnerData:
    id: int
    username: str
    avatar_url: str | None


@dataclass(frozen=True, slots=True)
class CommunityProjectData:
    id: int
    publication_id: int
    publication_kind: PublicationKind
    publication_status: PublicationStatus
    publication_version: int
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    status: ProjectStatus
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
    repository_url: str | None
    attribution: str | None
    source_license_statement: str | None
    ai_assistance_statement: str | None
    human_review_statement: str | None
    owner: CommunityOwnerData
    tags: list[TagData]
    published_at: datetime
    updated_at: datetime
    view_count: int
    comment_count: int
    like_count: int
    favorite_count: int
    liked: bool
    favorited: bool


@dataclass(frozen=True, slots=True)
class CommunityProjectPage:
    items: list[CommunityProjectData]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class CommentAuthorData:
    id: int
    username: str
    avatar_url: str | None


@dataclass(frozen=True, slots=True)
class CommentData:
    id: int
    project_id: int
    author: CommentAuthorData
    content: str
    revision: int
    created_at: datetime
    updated_at: datetime
    can_delete: bool
    can_report: bool


@dataclass(frozen=True, slots=True)
class CommentPage:
    items: list[CommentData]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class InteractionData:
    active: bool
    count: int


class CommunityService:
    def __init__(self, repository: CommunityRepository) -> None:
        self._repository = repository

    def list_projects(
        self,
        current_user: UserIdentity,
        *,
        page: int,
        page_size: int,
        tag_slug: str | None,
    ) -> CommunityProjectPage:
        self._actor(current_user)
        total = self._repository.count_published(tag_slug)
        records = self._repository.list_published(
            current_user.id,
            offset=(page - 1) * page_size,
            limit=page_size,
            tag_slug=tag_slug,
        )
        return CommunityProjectPage(
            items=[self._to_project_data(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_project(
        self, project_id: int, current_user: UserIdentity
    ) -> CommunityProjectData:
        self._actor(current_user)
        return self._to_project_data(
            self._get_published(project_id, current_user.id)
        )

    def list_tags(self, current_user: UserIdentity) -> list[TagSummaryData]:
        self._actor(current_user)
        return [
            TagSummaryData(
                id=record.tag.id,
                name=record.tag.name,
                slug=record.tag.slug,
                project_count=record.project_count,
            )
            for record in self._repository.list_tags()
        ]

    def request_publication(
        self,
        current_user: UserIdentity,
        *,
        project_id: int,
        request_key: str,
        expected_project_updated_at: datetime,
        kind: PublicationKind,
        tag_names: list[str],
        attribution: str,
        source_license_statement: str,
        ai_assistance_statement: str,
        human_review_statement: str | None,
    ) -> dict[str, object]:
        publication_id = 0
        with self._repository.transaction():
            actor = self._actor(current_user, for_update=True)
            if kind == PublicationKind.PRACTICE_TEMPLATE and actor.role != CampusRole.TEACHER:
                raise PermissionDeniedError("只有有效教师可以申请实践项目模板")
            project = self._owned_project(project_id, current_user.id, for_update=True)
            publication = self._repository.publication_by_project(project_id, for_update=True)
            existing = (
                self._repository.publication_version_by_request(publication.id, request_key)
                if publication is not None
                else None
            )
            if existing is not None:
                if not self._same_request(
                    existing,
                    expected_project_updated_at=expected_project_updated_at,
                    kind=kind,
                    tag_names=tag_names,
                    attribution=attribution,
                    source_license_statement=source_license_statement,
                    ai_assistance_statement=ai_assistance_statement,
                    human_review_statement=human_review_statement,
                ):
                    raise ConflictError("请求键已用于不同的发布申请")
                publication_id = existing.publication_id
            else:
                if project.updated_at != expected_project_updated_at.astimezone(UTC):
                    raise ConflictError("项目已更新，请刷新后重新确认公开内容")
                created_new = publication is None
                if publication is None:
                    publication = CommunityPublication(
                        project_id=project.id,
                        owner_user_id=current_user.id,
                        kind=kind,
                        status=PublicationStatus.PENDING_REVIEW,
                        revision=1,
                    )
                    self._repository.add(publication)
                elif publication.pending_version_number is not None:
                    raise ConflictError("已有版本正在等待审核")
                version_number = self._repository.next_publication_version(publication.id)
                now = datetime.now(UTC)
                version = CommunityPublicationVersion(
                    publication_id=publication.id,
                    version_number=version_number,
                    request_key=request_key,
                    project_updated_at=project.updated_at,
                    kind=kind,
                    name=project.name,
                    description=project.description,
                    difficulty=project.difficulty,
                    project_status=project.status,
                    language=project.language,
                    framework=project.framework,
                    frontend=project.frontend,
                    backend=project.backend,
                    database=project.database,
                    repository_url=project.repository_url,
                    tag_names=tag_names,
                    attribution=attribution,
                    source_license_statement=source_license_statement,
                    ai_assistance_statement=ai_assistance_statement,
                    human_review_statement=human_review_statement,
                    submitted_at=now,
                )
                self._repository.add(version)
                previous_status = publication.status.value
                publication.kind = kind
                publication.status = PublicationStatus.PENDING_REVIEW
                publication.pending_version_number = version_number
                publication.submitted_at = now
                publication.reviewed_at = None
                if not created_new:
                    publication.revision += 1
                self._repository.add(
                    self._action(
                        actor_user_id=current_user.id,
                        target_owner_user_id=current_user.id,
                        publication_id=publication.id,
                        version_number=version_number,
                        action=GovernanceActionType.APPLY,
                        from_status=previous_status,
                        to_status=PublicationStatus.PENDING_REVIEW.value,
                        reason="作者提交公开申请",
                        excerpt=project.name,
                        now=now,
                    )
                )
                publication_id = publication.id
        return self._publication_response(publication_id, current_user)

    def reject_legacy_publish(self) -> None:
        raise ConflictError("社区已启用人工审核，请使用发布申请入口")

    def withdraw_by_project(
        self, current_user: UserIdentity, *, project_id: int
    ) -> None:
        publication = self._repository.publication_by_project(project_id)
        if publication is None:
            raise ResourceNotFoundError("发布记录不存在")
        self.withdraw_publication(
            current_user,
            publication_id=publication.id,
            expected_revision=publication.revision,
            reason="作者通过兼容入口撤回",
        )

    def get_publication(
        self, current_user: UserIdentity, *, project_id: int
    ) -> dict[str, object]:
        record = self._repository.publication_record_by_project(project_id)
        if record is None:
            raise ResourceNotFoundError("发布记录不存在")
        self._can_view_publication(current_user, record.publication)
        return self._publication_data(
            record,
            actions=self._repository.publication_actions(record.publication.id),
            reveal_actor=self._is_admin(current_user),
        )

    def publication_list(
        self,
        current_user: UserIdentity,
        *,
        moderation_queue: bool,
        page: int,
        page_size: int,
    ) -> dict[str, object]:
        actor = self._actor(current_user)
        if moderation_queue and actor.role != CampusRole.ADMINISTRATOR:
            raise PermissionDeniedError("需要管理员权限")
        records, total = self._repository.publication_page(
            owner_user_id=None if moderation_queue else current_user.id,
            moderation_queue=moderation_queue,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": [
                self._publication_data(record, actions=[], reveal_actor=moderation_queue)
                for record in records
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def withdraw_publication(
        self,
        current_user: UserIdentity,
        *,
        publication_id: int,
        expected_revision: int,
        reason: str,
    ) -> dict[str, object]:
        with self._repository.transaction():
            self._actor(current_user, for_update=True)
            publication = self._repository.publication(publication_id, for_update=True)
            if publication is None or publication.owner_user_id != current_user.id:
                raise ResourceNotFoundError("发布记录不存在")
            if publication.revision != expected_revision:
                raise ConflictError("发布状态已变化，请刷新后重试")
            target_version = publication.pending_version_number or publication.public_version_number
            if target_version is None:
                raise ConflictError("当前没有可撤回的申请或公开版本")
            now = datetime.now(UTC)
            previous_status = publication.status.value
            project: Project | None = None
            publication.public_version_number = None
            publication.pending_version_number = None
            publication.status = PublicationStatus.WITHDRAWN
            publication.withdrawn_at = now
            publication.revision += 1
            if project is None and publication.project_id is not None:
                project = self._repository.get_project(
                    publication.project_id, for_update=True
                )
            if project is not None:
                project.is_published = False
                project.published_at = None
            version = self._required_version(publication.id, target_version)
            self._repository.add(
                self._action(
                    actor_user_id=current_user.id,
                    target_owner_user_id=current_user.id,
                    publication_id=publication.id,
                    version_number=target_version,
                    action=GovernanceActionType.WITHDRAW,
                    from_status=previous_status,
                    to_status=PublicationStatus.WITHDRAWN.value,
                    reason=reason,
                    excerpt=version.name,
                    now=now,
                )
            )
        return self._publication_response(publication_id, current_user)

    def decide_publication(
        self,
        current_user: UserIdentity,
        *,
        publication_id: int,
        expected_revision: int,
        decision: str,
        reason: str,
    ) -> dict[str, object]:
        with self._repository.transaction():
            self._administrator(current_user, for_update=True)
            publication = self._repository.publication(publication_id, for_update=True)
            if publication is None:
                raise ResourceNotFoundError("发布记录不存在")
            if publication.revision != expected_revision:
                raise ConflictError("发布状态已变化，请刷新后重试")
            now = datetime.now(UTC)
            previous_status = publication.status.value
            project: Project | None = None
            if decision == "take_down":
                version_number = publication.public_version_number
                if version_number is None:
                    raise ConflictError("当前作品没有可下架的公开版本")
                publication.public_version_number = None
                publication.pending_version_number = None
                publication.status = PublicationStatus.TAKEN_DOWN
                publication.taken_down_at = now
                action_type = GovernanceActionType.TAKE_DOWN
            else:
                version_number = publication.pending_version_number
                if version_number is None:
                    raise ConflictError("当前没有待审核版本")
                if decision == "approve":
                    project = self._publication_project(publication, for_update=True)
                    version = self._required_version(publication.id, version_number)
                    self._repository.set_project_tags(project, version.tag_names)
                    project.is_published = True
                    project.published_at = now
                    publication.public_version_number = version_number
                    publication.pending_version_number = None
                    publication.status = PublicationStatus.APPROVED
                    publication.published_at = now
                    action_type = GovernanceActionType.APPROVE
                elif decision == "return":
                    publication.pending_version_number = None
                    publication.status = PublicationStatus.RETURNED
                    if (
                        previous_status == PublicationStatus.LEGACY_REVIEW_REQUIRED.value
                        and publication.public_version_number == version_number
                    ):
                        publication.public_version_number = None
                    action_type = GovernanceActionType.RETURN
                else:
                    raise ConflictError("不支持的审核决定")
            if project is None and publication.project_id is not None:
                project = self._repository.get_project(
                    publication.project_id, for_update=True
                )
            if decision == "take_down" and project is not None:
                project.is_published = False
                project.published_at = None
            if decision == "return" and publication.public_version_number is None and project is not None:
                project.is_published = False
                project.published_at = None
            publication.reviewed_at = now
            publication.revision += 1
            version = self._required_version(publication.id, version_number)
            action = self._action(
                actor_user_id=current_user.id,
                target_owner_user_id=publication.owner_user_id,
                publication_id=publication.id,
                version_number=version_number,
                action=action_type,
                from_status=previous_status,
                to_status=publication.status.value,
                reason=reason,
                excerpt=version.name,
                now=now,
            )
            self._repository.add(action)
            self._publication_notification(publication, action.id, now)
        return self._publication_response(publication_id, current_user)

    def record_view(self, project_id: int, current_user: UserIdentity) -> int:
        with self._repository.transaction():
            self._actor(current_user, for_update=True)
            self._locked_visible_publication(project_id)
            view_count = self._repository.increment_view(project_id, current_user.id)
            if view_count is None:
                raise ResourceNotFoundError("已发布项目不存在")
        return view_count

    def list_comments(
        self,
        project_id: int,
        current_user: UserIdentity,
        *,
        page: int,
        page_size: int,
    ) -> CommentPage:
        self._actor(current_user)
        self._get_published(project_id, current_user.id)
        total = self._repository.count_comments(project_id)
        comments = self._repository.list_comments(
            project_id, offset=(page - 1) * page_size, limit=page_size
        )
        return CommentPage(
            items=[self._to_comment_data(comment, current_user.id) for comment in comments],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def create_comment(
        self, project_id: int, current_user: UserIdentity, content: str
    ) -> CommentData:
        comment_id = 0
        with self._repository.transaction():
            self._actor(current_user, for_update=True)
            self._locked_visible_publication(project_id)
            if self._repository.recent_comment_count(
                current_user.id, datetime.now(UTC) - timedelta(hours=1)
            ) >= 20:
                raise RateLimitError("每小时最多发表评论 20 条")
            comment = Comment(project_id=project_id, user_id=current_user.id, content=content)
            self._repository.add(comment)
            comment_id = comment.id
        saved = self._repository.comment(comment_id)
        if saved is None:
            raise RuntimeError("评论写入后无法重新加载")
        return self._to_comment_data(saved, current_user.id)

    def delete_comment(self, comment_id: int, current_user: UserIdentity) -> None:
        with self._repository.transaction():
            self._actor(current_user, for_update=True)
            comment = self._repository.comment(comment_id, for_update=True)
            if comment is None:
                raise ResourceNotFoundError("评论不存在")
            if comment.user_id != current_user.id:
                raise PermissionDeniedError("只能删除自己的评论")
            self._repository.soft_delete_comment(comment, datetime.now(UTC))

    def set_like(
        self, project_id: int, current_user: UserIdentity, *, active: bool
    ) -> InteractionData:
        with self._repository.transaction():
            self._actor(current_user, for_update=True)
            self._locked_visible_publication(project_id)
            count = self._repository.set_like(project_id, current_user.id, active=active)
        return InteractionData(active=active, count=count)

    def set_favorite(
        self, project_id: int, current_user: UserIdentity, *, active: bool
    ) -> InteractionData:
        with self._repository.transaction():
            self._actor(current_user, for_update=True)
            self._locked_visible_publication(project_id)
            count = self._repository.set_favorite(project_id, current_user.id, active=active)
        return InteractionData(active=active, count=count)

    def report(
        self,
        current_user: UserIdentity,
        *,
        request_key: str,
        target_type: str,
        target_id: int,
        reason: str,
    ) -> dict[str, object]:
        case_id = 0
        with self._repository.transaction():
            self._actor(current_user, for_update=True)
            existing = self._repository.governance_case_by_request(current_user.id, request_key)
            if existing is not None:
                target_matches = existing.comment_id == target_id if target_type == "comment" else False
                if target_type == "project":
                    publication = self._repository.publication_by_project(target_id)
                    target_matches = publication is not None and existing.publication_id == publication.id
                if (
                    existing.case_type != GovernanceCaseType.REPORT
                    or not target_matches
                    or existing.reason != reason
                ):
                    raise ConflictError("请求键已用于不同的举报")
                case_id = existing.id
            else:
                self._check_case_rate(current_user.id)
                publication_id: int | None = None
                version_number: int | None = None
                comment_id: int | None = None
                if target_type == "project":
                    record = self._get_published(target_id, current_user.id)
                    publication_id = record.publication.id
                    version_number = record.version.version_number
                    target_owner = record.publication.owner_user_id
                    excerpt = record.version.name
                elif target_type == "comment":
                    comment = self._repository.comment(target_id, visible_only=True)
                    if comment is None:
                        raise ResourceNotFoundError("举报目标不存在")
                    self._get_published(comment.project_id, current_user.id)
                    comment_id = comment.id
                    target_owner = comment.user_id
                    excerpt = comment.content[:500]
                else:
                    raise ConflictError("不支持的举报目标")
                if target_owner == current_user.id:
                    raise ConflictError("不能举报自己发布的内容")
                case = CommunityGovernanceCase(
                    case_type=GovernanceCaseType.REPORT,
                    opened_by_user_id=current_user.id,
                    target_owner_user_id=target_owner,
                    request_key=request_key,
                    publication_id=publication_id,
                    publication_version_number=version_number,
                    comment_id=comment_id,
                    reason=reason,
                    target_excerpt=excerpt,
                    status=GovernanceCaseStatus.PENDING,
                    revision=1,
                )
                self._repository.add(case)
                case_id = case.id
        return self._case_response(case_id, current_user)

    def appeal(
        self,
        current_user: UserIdentity,
        *,
        action_id: int,
        request_key: str,
        reason: str,
    ) -> dict[str, object]:
        case_id = 0
        with self._repository.transaction():
            self._actor(current_user, for_update=True)
            action = self._repository.governance_action(action_id)
            if (
                action is None
                or action.target_owner_user_id != current_user.id
                or action.action not in {GovernanceActionType.TAKE_DOWN, GovernanceActionType.HIDE_COMMENT}
            ):
                raise ResourceNotFoundError("可复核的治理动作不存在")
            existing = self._repository.governance_case_by_request(current_user.id, request_key)
            if existing is not None:
                if existing.target_action_id != action_id or existing.reason != reason:
                    raise ConflictError("请求键已用于不同的复核申请")
                case_id = existing.id
            else:
                self._check_case_rate(current_user.id)
                case = CommunityGovernanceCase(
                    case_type=GovernanceCaseType.APPEAL,
                    opened_by_user_id=current_user.id,
                    target_owner_user_id=current_user.id,
                    request_key=request_key,
                    target_action_id=action.id,
                    reason=reason,
                    target_excerpt=action.target_excerpt,
                    status=GovernanceCaseStatus.PENDING,
                    revision=1,
                )
                self._repository.add(case)
                case_id = case.id
        return self._case_response(case_id, current_user)

    def case_list(
        self,
        current_user: UserIdentity,
        *,
        status: GovernanceCaseStatus | None,
        page: int,
        page_size: int,
    ) -> dict[str, object]:
        actor = self._actor(current_user)
        administrator = actor.role == CampusRole.ADMINISTRATOR
        values, total = self._repository.governance_case_page(
            viewer_id=current_user.id,
            administrator=administrator,
            status=status,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return {
            "items": [self._case_data(value, current_user, administrator) for value in values],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size) if total else 0,
        }

    def decide_case(
        self,
        current_user: UserIdentity,
        *,
        case_id: int,
        expected_revision: int,
        decision: str,
        reason: str,
    ) -> dict[str, object]:
        with self._repository.transaction():
            self._administrator(current_user, for_update=True)
            case = self._repository.governance_case(case_id, for_update=True)
            if case is None:
                raise ResourceNotFoundError("治理案件不存在")
            if case.revision != expected_revision:
                raise ConflictError("案件状态已变化，请刷新后重试")
            if case.status != GovernanceCaseStatus.PENDING:
                raise ConflictError("案件已经处理")
            now = datetime.now(UTC)
            action = None
            if decision == "accept":
                action = self._accept_case(current_user.id, case, reason, now)
                case.status = GovernanceCaseStatus.ACCEPTED
            elif decision == "reject":
                case.status = GovernanceCaseStatus.REJECTED
            else:
                raise ConflictError("不支持的案件决定")
            if action is not None:
                self._repository.add(action)
                case.resolved_action_id = action.id
            case.resolution_reason = reason
            case.reviewed_by_user_id = current_user.id
            case.resolved_at = now
            case.revision += 1
            self._case_notification(case, case.opened_by_user_id, now)
            if (
                case.status == GovernanceCaseStatus.ACCEPTED
                and case.target_owner_user_id != case.opened_by_user_id
            ):
                self._case_notification(case, case.target_owner_user_id, now)
        return self._case_response(case_id, current_user)

    def _accept_case(
        self,
        actor_user_id: int,
        case: CommunityGovernanceCase,
        reason: str,
        now: datetime,
    ) -> CommunityGovernanceAction:
        if case.case_type == GovernanceCaseType.REPORT and case.publication_id is not None:
            publication = self._repository.publication(case.publication_id, for_update=True)
            if publication is None or publication.public_version_number != case.publication_version_number:
                raise ConflictError("被举报的公开版本已经变化")
            version = self._required_version(publication.id, case.publication_version_number)
            previous_status = publication.status.value
            publication.public_version_number = None
            publication.pending_version_number = None
            publication.status = PublicationStatus.TAKEN_DOWN
            publication.taken_down_at = now
            publication.revision += 1
            project = self._publication_project(publication, for_update=True)
            project.is_published = False
            project.published_at = None
            return self._action(
                actor_user_id=actor_user_id,
                target_owner_user_id=publication.owner_user_id,
                publication_id=publication.id,
                version_number=version.version_number,
                action=GovernanceActionType.TAKE_DOWN,
                from_status=previous_status,
                to_status=PublicationStatus.TAKEN_DOWN.value,
                reason=reason,
                excerpt=version.name,
                now=now,
            )
        if case.case_type == GovernanceCaseType.REPORT and case.comment_id is not None:
            comment = self._repository.comment(case.comment_id, for_update=True)
            if comment is None or comment.moderation_status != CommentModerationStatus.VISIBLE:
                raise ConflictError("被举报评论已经不可见")
            comment.moderation_status = CommentModerationStatus.HIDDEN
            comment.moderated_at = now
            comment.revision += 1
            return self._action(
                actor_user_id=actor_user_id,
                target_owner_user_id=comment.user_id,
                comment_id=comment.id,
                action=GovernanceActionType.HIDE_COMMENT,
                from_status=CommentModerationStatus.VISIBLE.value,
                to_status=CommentModerationStatus.HIDDEN.value,
                reason=reason,
                excerpt=comment.content[:500],
                now=now,
            )
        if case.case_type == GovernanceCaseType.APPEAL and case.target_action_id is not None:
            target_action = self._repository.governance_action(case.target_action_id)
            if target_action is None:
                raise ResourceNotFoundError("原治理动作不存在")
            if target_action.action == GovernanceActionType.TAKE_DOWN:
                if target_action.publication_id is None or target_action.publication_version_number is None:
                    raise ConflictError("原下架动作缺少作品版本")
                publication = self._repository.publication(target_action.publication_id, for_update=True)
                if publication is None or publication.status != PublicationStatus.TAKEN_DOWN:
                    raise ConflictError("作品状态已经变化")
                version = self._required_version(publication.id, target_action.publication_version_number)
                project = self._publication_project(publication, for_update=True)
                publication.public_version_number = version.version_number
                publication.pending_version_number = None
                publication.status = PublicationStatus.APPROVED
                publication.published_at = now
                publication.revision += 1
                self._repository.set_project_tags(project, version.tag_names)
                project.is_published = True
                project.published_at = now
                return self._action(
                    actor_user_id=actor_user_id,
                    target_owner_user_id=publication.owner_user_id,
                    publication_id=publication.id,
                    version_number=version.version_number,
                    action=GovernanceActionType.RESTORE,
                    from_status=PublicationStatus.TAKEN_DOWN.value,
                    to_status=PublicationStatus.APPROVED.value,
                    reason=reason,
                    excerpt=version.name,
                    now=now,
                )
            if target_action.action == GovernanceActionType.HIDE_COMMENT:
                if target_action.comment_id is None:
                    raise ConflictError("原隐藏动作对应的评论已不存在")
                comment = self._repository.comment(target_action.comment_id, for_update=True)
                if comment is None or comment.moderation_status != CommentModerationStatus.HIDDEN:
                    raise ConflictError("评论状态已经变化")
                comment.moderation_status = CommentModerationStatus.VISIBLE
                comment.moderated_at = now
                comment.revision += 1
                return self._action(
                    actor_user_id=actor_user_id,
                    target_owner_user_id=comment.user_id,
                    comment_id=comment.id,
                    action=GovernanceActionType.RESTORE_COMMENT,
                    from_status=CommentModerationStatus.HIDDEN.value,
                    to_status=CommentModerationStatus.VISIBLE.value,
                    reason=reason,
                    excerpt=comment.content[:500],
                    now=now,
                )
        raise ConflictError("案件目标不支持当前处理")

    def _publication_response(
        self, publication_id: int, current_user: UserIdentity
    ) -> dict[str, object]:
        record = self._repository.publication_record(publication_id)
        if record is None:
            raise RuntimeError("发布记录写入后无法重新加载")
        return self._publication_data(
            record,
            actions=self._repository.publication_actions(publication_id),
            reveal_actor=self._is_admin(current_user),
        )

    def _case_response(
        self, case_id: int, current_user: UserIdentity
    ) -> dict[str, object]:
        value = self._repository.governance_case(case_id)
        if value is None:
            raise RuntimeError("治理案件写入后无法重新加载")
        administrator = self._is_admin(current_user)
        if not administrator and current_user.id not in {
            value.opened_by_user_id,
            value.target_owner_user_id,
        }:
            raise ResourceNotFoundError("治理案件不存在")
        return self._case_data(value, current_user, administrator)

    def _actor(
        self, current_user: UserIdentity, *, for_update: bool = False
    ) -> CampusMembership:
        value = self._repository.campus_membership(current_user.id, for_update=for_update)
        if value is None or value.status != MembershipStatus.ACTIVE:
            raise PermissionDeniedError("需要有效的校园身份")
        return value

    def _administrator(
        self, current_user: UserIdentity, *, for_update: bool = False
    ) -> CampusMembership:
        actor = self._actor(current_user, for_update=for_update)
        if actor.role != CampusRole.ADMINISTRATOR:
            raise PermissionDeniedError("需要管理员权限")
        return actor

    def _is_admin(self, current_user: UserIdentity) -> bool:
        value = self._repository.campus_membership(current_user.id)
        return bool(
            value is not None
            and value.status == MembershipStatus.ACTIVE
            and value.role == CampusRole.ADMINISTRATOR
        )

    def _can_view_publication(
        self, current_user: UserIdentity, publication: CommunityPublication
    ) -> None:
        actor = self._actor(current_user)
        if publication.owner_user_id != current_user.id and actor.role != CampusRole.ADMINISTRATOR:
            raise ResourceNotFoundError("发布记录不存在")

    def _owned_project(
        self, project_id: int, owner_id: int, *, for_update: bool
    ) -> Project:
        project = self._repository.get_project(project_id, for_update=for_update)
        if project is None:
            raise ResourceNotFoundError("项目不存在")
        if project.owner_id != owner_id:
            raise PermissionDeniedError("无权申请发布该项目")
        return project

    def _publication_project(
        self, publication: CommunityPublication, *, for_update: bool
    ) -> Project:
        if publication.project_id is None:
            raise ConflictError("原项目已删除，不能继续公开")
        project = self._repository.get_project(publication.project_id, for_update=for_update)
        if project is None or project.owner_id != publication.owner_user_id:
            raise ConflictError("发布记录与原项目不一致")
        return project

    def _locked_visible_publication(self, project_id: int) -> CommunityPublication:
        publication = self._repository.publication_by_project(project_id, for_update=True)
        if publication is None or publication.public_version_number is None:
            raise ResourceNotFoundError("已发布项目不存在")
        return publication

    def _get_published(self, project_id: int, viewer_id: int) -> CommunityProjectRecord:
        project = self._repository.get_published(project_id, viewer_id)
        if project is None:
            raise ResourceNotFoundError("已发布项目不存在")
        return project

    def _required_version(
        self, publication_id: int, version_number: int | None
    ) -> CommunityPublicationVersion:
        if version_number is None:
            raise ConflictError("发布版本不存在")
        version = self._repository.publication_version(publication_id, version_number)
        if version is None:
            raise ConflictError("发布版本不存在")
        return version

    def _check_case_rate(self, user_id: int) -> None:
        if self._repository.recent_case_count(
            user_id, datetime.now(UTC) - timedelta(hours=24)
        ) >= 10:
            raise RateLimitError("每 24 小时最多提交 10 次举报或复核")

    @staticmethod
    def _same_request(
        version: CommunityPublicationVersion,
        *,
        expected_project_updated_at: datetime,
        kind: PublicationKind,
        tag_names: list[str],
        attribution: str,
        source_license_statement: str,
        ai_assistance_statement: str,
        human_review_statement: str | None,
    ) -> bool:
        return (
            version.project_updated_at == expected_project_updated_at.astimezone(UTC)
            and version.kind == kind
            and version.tag_names == tag_names
            and version.attribution == attribution
            and version.source_license_statement == source_license_statement
            and version.ai_assistance_statement == ai_assistance_statement
            and version.human_review_statement == human_review_statement
        )

    @staticmethod
    def _action(
        *,
        actor_user_id: int,
        target_owner_user_id: int,
        action: GovernanceActionType,
        from_status: str | None,
        to_status: str,
        reason: str,
        excerpt: str,
        now: datetime,
        publication_id: int | None = None,
        version_number: int | None = None,
        comment_id: int | None = None,
    ) -> CommunityGovernanceAction:
        return CommunityGovernanceAction(
            actor_user_id=actor_user_id,
            target_owner_user_id=target_owner_user_id,
            publication_id=publication_id,
            publication_version_number=version_number,
            comment_id=comment_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            target_excerpt=excerpt[:500],
            occurred_at=now,
        )

    def _publication_notification(
        self, publication: CommunityPublication, action_id: int, now: datetime
    ) -> None:
        self._repository.add_notification(
            Notification(
                recipient_user_id=publication.owner_user_id,
                event_key=f"community_publication_changed:{action_id}",
                kind="community_publication_changed",
                community_publication_id=publication.id,
                created_at=now,
            )
        )

    def _case_notification(
        self, case: CommunityGovernanceCase, recipient_user_id: int, now: datetime
    ) -> None:
        self._repository.add_notification(
            Notification(
                recipient_user_id=recipient_user_id,
                event_key=f"community_case_resolved:{case.id}:{recipient_user_id}",
                kind="community_case_resolved",
                community_case_id=case.id,
                created_at=now,
            )
        )

    @staticmethod
    def _to_project_data(record: CommunityProjectRecord) -> CommunityProjectData:
        project = record.project
        publication = record.publication
        version = record.version
        if publication.published_at is None:
            raise RuntimeError("公开版本缺少发布时间")
        return CommunityProjectData(
            id=project.id,
            publication_id=publication.id,
            publication_kind=version.kind,
            publication_status=publication.status,
            publication_version=version.version_number,
            name=version.name,
            description=version.description,
            difficulty=version.difficulty,
            status=version.project_status,
            language=version.language,
            framework=version.framework,
            frontend=version.frontend,
            backend=version.backend,
            database=version.database,
            repository_url=version.repository_url,
            attribution=version.attribution,
            source_license_statement=version.source_license_statement,
            ai_assistance_statement=version.ai_assistance_statement,
            human_review_statement=version.human_review_statement,
            owner=CommunityOwnerData(
                id=project.owner.id,
                username=project.owner.username,
                avatar_url=project.owner.avatar_url,
            ),
            tags=[TagData(id=tag.id, name=tag.name, slug=tag.slug) for tag in project.tags],
            published_at=publication.published_at,
            updated_at=version.submitted_at,
            view_count=project.view_count,
            comment_count=record.comment_count,
            like_count=record.like_count,
            favorite_count=record.favorite_count,
            liked=record.liked,
            favorited=record.favorited,
        )

    @staticmethod
    def _to_comment_data(comment: Comment, viewer_id: int) -> CommentData:
        return CommentData(
            id=comment.id,
            project_id=comment.project_id,
            author=CommentAuthorData(
                id=comment.user.id,
                username=comment.user.username,
                avatar_url=comment.user.avatar_url,
            ),
            content=comment.content,
            revision=comment.revision,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            can_delete=comment.user_id == viewer_id,
            can_report=comment.user_id != viewer_id,
        )

    @classmethod
    def _publication_data(
        cls,
        record: PublicationRecord,
        *,
        actions: list[CommunityGovernanceAction],
        reveal_actor: bool,
    ) -> dict[str, object]:
        value = record.publication
        return {
            "id": value.id,
            "project_id": value.project_id,
            "owner_user_id": value.owner_user_id,
            "kind": value.kind,
            "status": value.status,
            "public_version_number": value.public_version_number,
            "pending_version_number": value.pending_version_number,
            "revision": value.revision,
            "submitted_at": value.submitted_at,
            "reviewed_at": value.reviewed_at,
            "published_at": value.published_at,
            "withdrawn_at": value.withdrawn_at,
            "taken_down_at": value.taken_down_at,
            "public_version": cls._version_data(record.public_version),
            "pending_version": cls._version_data(record.pending_version),
            "actions": [cls._action_data(action, reveal_actor) for action in actions],
        }

    @staticmethod
    def _version_data(
        value: CommunityPublicationVersion | None,
    ) -> dict[str, object] | None:
        if value is None:
            return None
        return {
            "version_number": value.version_number,
            "kind": value.kind,
            "name": value.name,
            "description": value.description,
            "difficulty": value.difficulty,
            "project_status": value.project_status,
            "language": value.language,
            "framework": value.framework,
            "frontend": value.frontend,
            "backend": value.backend,
            "database": value.database,
            "repository_url": value.repository_url,
            "tags": value.tag_names,
            "attribution": value.attribution,
            "source_license_statement": value.source_license_statement,
            "ai_assistance_statement": value.ai_assistance_statement,
            "human_review_statement": value.human_review_statement,
            "submitted_at": value.submitted_at,
        }

    @staticmethod
    def _action_data(
        value: CommunityGovernanceAction, reveal_actor: bool
    ) -> dict[str, object]:
        return {
            "id": value.id,
            "action": value.action,
            "actor_user_id": value.actor_user_id if reveal_actor else None,
            "publication_id": value.publication_id,
            "publication_version_number": value.publication_version_number,
            "comment_id": value.comment_id,
            "from_status": value.from_status,
            "to_status": value.to_status,
            "reason": value.reason,
            "occurred_at": value.occurred_at,
        }

    @staticmethod
    def _case_data(
        value: CommunityGovernanceCase,
        current_user: UserIdentity,
        administrator: bool,
    ) -> dict[str, object]:
        opener_view = administrator or value.opened_by_user_id == current_user.id
        target_type = (
            "project"
            if value.publication_id is not None
            else "comment"
            if value.comment_id is not None
            else "action"
        )
        return {
            "id": value.id,
            "case_type": value.case_type,
            "opened_by_user_id": value.opened_by_user_id if opener_view else None,
            "target_owner_user_id": value.target_owner_user_id,
            "target_type": target_type,
            "publication_id": value.publication_id,
            "publication_version_number": value.publication_version_number,
            "comment_id": value.comment_id,
            "target_action_id": value.target_action_id,
            "reason": value.reason if opener_view else None,
            "target_excerpt": value.target_excerpt,
            "status": value.status,
            "resolution_reason": value.resolution_reason,
            "resolved_action_id": value.resolved_action_id,
            "revision": value.revision,
            "created_at": value.created_at,
            "resolved_at": value.resolved_at,
        }
