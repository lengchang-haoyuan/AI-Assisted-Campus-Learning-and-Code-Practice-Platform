from dataclasses import dataclass
from datetime import UTC, datetime
import re

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.community import Comment, Favorite, Like
from app.models.project import Project, Tag, project_tags


class CommunityPersistenceConflictError(Exception):
    """社区数据写入与当前数据库状态冲突。"""


@dataclass(frozen=True, slots=True)
class CommunityProjectRecord:
    project: Project
    comment_count: int
    like_count: int
    favorite_count: int
    liked: bool
    favorited: bool


@dataclass(frozen=True, slots=True)
class TagRecord:
    tag: Tag
    project_count: int


class CommunityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_published(self, tag_slug: str | None = None) -> int:
        statement = select(func.count(Project.id)).where(Project.is_published.is_(True))
        if tag_slug:
            statement = statement.where(Project.tags.any(Tag.slug == tag_slug))
        return self._session.scalar(statement) or 0

    def list_published(
        self,
        viewer_id: int,
        *,
        offset: int,
        limit: int,
        tag_slug: str | None,
    ) -> list[CommunityProjectRecord]:
        statement = self._project_statement(viewer_id).where(
            Project.is_published.is_(True)
        )
        if tag_slug:
            statement = statement.where(Project.tags.any(Tag.slug == tag_slug))
        statement = statement.order_by(
            Project.published_at.desc(), Project.id.desc()
        ).offset(offset).limit(limit)
        return [self._to_project_record(row) for row in self._session.execute(statement)]

    def get_published(
        self, project_id: int, viewer_id: int
    ) -> CommunityProjectRecord | None:
        statement = self._project_statement(viewer_id).where(
            Project.id == project_id,
            Project.is_published.is_(True),
        )
        row = self._session.execute(statement).first()
        return self._to_project_record(row) if row else None

    def get_project(self, project_id: int) -> Project | None:
        statement = (
            select(Project)
            .options(selectinload(Project.tags))
            .where(Project.id == project_id)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def list_tags(self) -> list[TagRecord]:
        statement = (
            select(Tag, func.count(project_tags.c.project_id))
            .join(project_tags, project_tags.c.tag_id == Tag.id)
            .join(Project, Project.id == project_tags.c.project_id)
            .where(Project.is_published.is_(True))
            .group_by(Tag.id)
            .order_by(func.count(project_tags.c.project_id).desc(), Tag.name.asc())
        )
        return [TagRecord(tag=row[0], project_count=row[1]) for row in self._session.execute(statement)]

    def publish(self, project: Project, tag_names: list[str]) -> None:
        tags = self._resolve_tags(tag_names)
        project.tags = tags
        project.is_published = True
        if project.published_at is None:
            project.published_at = datetime.now(UTC)
        self._commit_or_raise_conflict()

    def unpublish(self, project: Project) -> None:
        project.is_published = False
        project.published_at = None
        self._commit_or_raise_conflict()

    def increment_view(self, project_id: int) -> int | None:
        statement = (
            update(Project)
            .where(Project.id == project_id, Project.is_published.is_(True))
            .values(view_count=Project.view_count + 1)
        )
        result = self._session.execute(statement)
        if result.rowcount != 1:
            self._session.rollback()
            return None
        self._commit_or_raise_conflict()
        return self._session.scalar(select(Project.view_count).where(Project.id == project_id))

    def count_comments(self, project_id: int) -> int:
        statement = select(func.count(Comment.id)).where(
            Comment.project_id == project_id,
            Comment.is_deleted.is_(False),
        )
        return self._session.scalar(statement) or 0

    def list_comments(
        self, project_id: int, *, offset: int, limit: int
    ) -> list[Comment]:
        statement = (
            select(Comment)
            .options(joinedload(Comment.user))
            .where(Comment.project_id == project_id, Comment.is_deleted.is_(False))
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def create_comment(self, comment: Comment) -> Comment:
        self._session.add(comment)
        self._commit_or_raise_conflict()
        statement = (
            select(Comment)
            .options(joinedload(Comment.user))
            .where(Comment.id == comment.id)
        )
        saved = self._session.scalar(statement)
        if saved is None:
            raise RuntimeError("评论写入后无法重新加载")
        return saved

    def get_comment(self, comment_id: int) -> Comment | None:
        return self._session.scalar(
            select(Comment).where(Comment.id == comment_id, Comment.is_deleted.is_(False))
        )

    def soft_delete_comment(self, comment: Comment) -> None:
        comment.is_deleted = True
        comment.deleted_at = datetime.now(UTC)
        self._commit_or_raise_conflict()

    def set_like(self, project_id: int, user_id: int, *, active: bool) -> int:
        self._set_interaction(Like, project_id, user_id, active=active)
        return self._count_interactions(Like, project_id)

    def set_favorite(self, project_id: int, user_id: int, *, active: bool) -> int:
        self._set_interaction(Favorite, project_id, user_id, active=active)
        return self._count_interactions(Favorite, project_id)

    def _project_statement(self, viewer_id: int):
        comment_count = (
            select(func.count(Comment.id))
            .where(Comment.project_id == Project.id, Comment.is_deleted.is_(False))
            .correlate(Project)
            .scalar_subquery()
        )
        like_count = (
            select(func.count(Like.id))
            .where(Like.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )
        favorite_count = (
            select(func.count(Favorite.id))
            .where(Favorite.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )
        liked = exists().where(Like.project_id == Project.id, Like.user_id == viewer_id)
        favorited = exists().where(
            Favorite.project_id == Project.id, Favorite.user_id == viewer_id
        )
        return select(
            Project,
            comment_count,
            like_count,
            favorite_count,
            liked,
            favorited,
        ).options(joinedload(Project.owner), selectinload(Project.tags))

    @staticmethod
    def _to_project_record(row) -> CommunityProjectRecord:
        return CommunityProjectRecord(
            project=row[0],
            comment_count=row[1],
            like_count=row[2],
            favorite_count=row[3],
            liked=bool(row[4]),
            favorited=bool(row[5]),
        )

    def _resolve_tags(self, tag_names: list[str]) -> list[Tag]:
        requested = [(name, self._slugify(name)) for name in tag_names]
        slugs = [slug for _, slug in requested]
        existing = {
            tag.slug: tag
            for tag in self._session.scalars(select(Tag).where(Tag.slug.in_(slugs)))
        } if slugs else {}
        tags: list[Tag] = []
        for name, slug in requested:
            tag = existing.get(slug)
            if tag is None:
                tag = Tag(name=name, slug=slug)
                self._session.add(tag)
                existing[slug] = tag
            tags.append(tag)
        return tags

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"\s+", "-", name.casefold(), flags=re.UNICODE).strip("-")
        if not slug:
            raise CommunityPersistenceConflictError("标签不能为空")
        return slug[:64]

    def _set_interaction(self, model, project_id: int, user_id: int, *, active: bool) -> None:
        predicate = (model.project_id == project_id, model.user_id == user_id)
        existing_id = self._session.scalar(select(model.id).where(*predicate))
        if active and existing_id is None:
            self._session.add(model(project_id=project_id, user_id=user_id))
            try:
                self._session.commit()
            except IntegrityError as exc:
                self._session.rollback()
                if self._session.scalar(select(model.id).where(*predicate)) is None:
                    raise CommunityPersistenceConflictError from exc
        elif not active and existing_id is not None:
            self._session.execute(delete(model).where(model.id == existing_id))
            self._commit_or_raise_conflict()

    def _count_interactions(self, model, project_id: int) -> int:
        return self._session.scalar(
            select(func.count(model.id)).where(model.project_id == project_id)
        ) or 0

    def _commit_or_raise_conflict(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise CommunityPersistenceConflictError from exc
