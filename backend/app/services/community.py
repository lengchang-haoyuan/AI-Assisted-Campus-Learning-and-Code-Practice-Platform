from dataclasses import dataclass
from datetime import datetime
from math import ceil

from app.core.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.community import Comment
from app.models.enums import ProjectDifficulty, ProjectStatus
from app.models.project import Project
from app.repositories.community import (
    CommunityPersistenceConflictError,
    CommunityProjectRecord,
    CommunityRepository,
)


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
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    status: ProjectStatus
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
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
    created_at: datetime
    updated_at: datetime
    can_delete: bool


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
        viewer_id: int,
        *,
        page: int,
        page_size: int,
        tag_slug: str | None,
    ) -> CommunityProjectPage:
        total = self._repository.count_published(tag_slug)
        records = self._repository.list_published(
            viewer_id,
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

    def get_project(self, project_id: int, viewer_id: int) -> CommunityProjectData:
        return self._to_project_data(self._get_published(project_id, viewer_id))

    def list_tags(self) -> list[TagSummaryData]:
        return [
            TagSummaryData(
                id=record.tag.id,
                name=record.tag.name,
                slug=record.tag.slug,
                project_count=record.project_count,
            )
            for record in self._repository.list_tags()
        ]

    def publish_project(
        self, project_id: int, owner_id: int, tag_names: list[str]
    ) -> CommunityProjectData:
        project = self._get_owned_project(project_id, owner_id)
        try:
            self._repository.publish(project, tag_names)
        except CommunityPersistenceConflictError as exc:
            raise ConflictError(str(exc) or "项目发布状态冲突") from exc
        return self.get_project(project_id, owner_id)

    def unpublish_project(self, project_id: int, owner_id: int) -> None:
        project = self._get_owned_project(project_id, owner_id)
        try:
            self._repository.unpublish(project)
        except CommunityPersistenceConflictError as exc:
            raise ConflictError("项目发布状态冲突") from exc

    def record_view(self, project_id: int, viewer_id: int) -> int:
        self._get_published(project_id, viewer_id)
        try:
            view_count = self._repository.increment_view(project_id, viewer_id)
        except CommunityPersistenceConflictError as exc:
            raise ConflictError("浏览量更新冲突") from exc
        if view_count is None:
            raise ResourceNotFoundError("已发布项目不存在")
        return view_count

    def list_comments(
        self,
        project_id: int,
        viewer_id: int,
        *,
        page: int,
        page_size: int,
    ) -> CommentPage:
        self._get_published(project_id, viewer_id)
        total = self._repository.count_comments(project_id)
        comments = self._repository.list_comments(
            project_id, offset=(page - 1) * page_size, limit=page_size
        )
        return CommentPage(
            items=[self._to_comment_data(comment, viewer_id) for comment in comments],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def create_comment(
        self, project_id: int, user_id: int, content: str
    ) -> CommentData:
        self._get_published(project_id, user_id)
        try:
            comment = self._repository.create_comment(
                Comment(project_id=project_id, user_id=user_id, content=content)
            )
        except CommunityPersistenceConflictError as exc:
            raise ConflictError("评论写入与当前项目状态冲突") from exc
        return self._to_comment_data(comment, user_id)

    def delete_comment(self, comment_id: int, user_id: int) -> None:
        comment = self._repository.get_comment(comment_id)
        if comment is None:
            raise ResourceNotFoundError("评论不存在")
        if comment.user_id != user_id:
            raise PermissionDeniedError("只能删除自己的评论")
        try:
            self._repository.soft_delete_comment(comment)
        except CommunityPersistenceConflictError as exc:
            raise ConflictError("评论删除状态冲突") from exc

    def set_like(
        self, project_id: int, user_id: int, *, active: bool
    ) -> InteractionData:
        self._get_published(project_id, user_id)
        try:
            count = self._repository.set_like(project_id, user_id, active=active)
        except CommunityPersistenceConflictError as exc:
            raise ConflictError("点赞状态更新冲突") from exc
        return InteractionData(active=active, count=count)

    def set_favorite(
        self, project_id: int, user_id: int, *, active: bool
    ) -> InteractionData:
        self._get_published(project_id, user_id)
        try:
            count = self._repository.set_favorite(project_id, user_id, active=active)
        except CommunityPersistenceConflictError as exc:
            raise ConflictError("收藏状态更新冲突") from exc
        return InteractionData(active=active, count=count)

    def _get_published(
        self, project_id: int, viewer_id: int
    ) -> CommunityProjectRecord:
        project = self._repository.get_published(project_id, viewer_id)
        if project is None:
            raise ResourceNotFoundError("已发布项目不存在")
        return project

    def _get_owned_project(self, project_id: int, owner_id: int) -> Project:
        project = self._repository.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError("项目不存在")
        if project.owner_id != owner_id:
            raise PermissionDeniedError("无权更改该项目的发布状态")
        return project

    @staticmethod
    def _to_project_data(record: CommunityProjectRecord) -> CommunityProjectData:
        project = record.project
        if project.published_at is None:
            raise RuntimeError("已发布项目缺少发布时间")
        return CommunityProjectData(
            id=project.id,
            name=project.name,
            description=project.description,
            difficulty=project.difficulty,
            status=project.status,
            language=project.language,
            framework=project.framework,
            frontend=project.frontend,
            backend=project.backend,
            database=project.database,
            owner=CommunityOwnerData(
                id=project.owner.id,
                username=project.owner.username,
                avatar_url=project.owner.avatar_url,
            ),
            tags=[TagData(id=tag.id, name=tag.name, slug=tag.slug) for tag in project.tags],
            published_at=project.published_at,
            updated_at=project.updated_at,
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
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            can_delete=comment.user_id == viewer_id,
        )
