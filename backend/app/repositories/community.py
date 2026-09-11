from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import re

from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload, selectinload

from app.core.exceptions import ConflictError
from app.models.campus import CampusMembership
from app.models.community import (
    Comment,
    CommentModerationStatus,
    CommunityGovernanceAction,
    CommunityGovernanceCase,
    CommunityPublication,
    CommunityPublicationVersion,
    Favorite,
    GovernanceCaseStatus,
    Like,
    ProjectView,
)
from app.models.project import Project, Tag, project_tags
from app.models.submission import Notification


@dataclass(frozen=True, slots=True)
class CommunityProjectRecord:
    project: Project
    publication: CommunityPublication
    version: CommunityPublicationVersion
    comment_count: int
    like_count: int
    favorite_count: int
    liked: bool
    favorited: bool


@dataclass(frozen=True, slots=True)
class PublicationRecord:
    publication: CommunityPublication
    public_version: CommunityPublicationVersion | None
    pending_version: CommunityPublicationVersion | None


@dataclass(frozen=True, slots=True)
class TagRecord:
    tag: Tag
    project_count: int


class CommunityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def transaction(self) -> Iterator[None]:
        try:
            yield
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("请求与现有社区治理数据冲突") from exc
        except BaseException:
            self._session.rollback()
            raise

    def add(self, value: object) -> None:
        self._session.add(value)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()

    def campus_membership(
        self, user_id: int, *, for_update: bool = False
    ) -> CampusMembership | None:
        statement = select(CampusMembership).where(CampusMembership.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement.execution_options(populate_existing=True))

    def count_published(self, tag_slug: str | None = None) -> int:
        statement = (
            select(func.count(Project.id))
            .join(CommunityPublication, CommunityPublication.project_id == Project.id)
            .where(
                Project.is_published.is_(True),
                CommunityPublication.public_version_number.is_not(None),
            )
        )
        if tag_slug:
            statement = statement.where(Project.tags.any(Tag.slug == tag_slug))
        return int(self._session.scalar(statement) or 0)

    def list_published(
        self,
        viewer_id: int,
        *,
        offset: int,
        limit: int,
        tag_slug: str | None,
    ) -> list[CommunityProjectRecord]:
        statement = self._project_statement(viewer_id)
        if tag_slug:
            statement = statement.where(Project.tags.any(Tag.slug == tag_slug))
        rows = self._session.execute(
            statement.order_by(
                CommunityPublication.published_at.desc(), Project.id.desc()
            )
            .offset(offset)
            .limit(limit)
        )
        return [self._to_project_record(row) for row in rows]

    def get_published(
        self, project_id: int, viewer_id: int
    ) -> CommunityProjectRecord | None:
        row = self._session.execute(
            self._project_statement(viewer_id).where(Project.id == project_id)
        ).first()
        return self._to_project_record(row) if row else None

    def get_project(self, project_id: int, *, for_update: bool = False) -> Project | None:
        statement = (
            select(Project)
            .options(selectinload(Project.tags), joinedload(Project.owner))
            .where(Project.id == project_id)
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement.execution_options(populate_existing=True))

    def publication_by_project(
        self, project_id: int, *, for_update: bool = False
    ) -> CommunityPublication | None:
        statement = select(CommunityPublication).where(
            CommunityPublication.project_id == project_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement.execution_options(populate_existing=True))

    def publication(
        self, publication_id: int, *, for_update: bool = False
    ) -> CommunityPublication | None:
        statement = select(CommunityPublication).where(
            CommunityPublication.id == publication_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement.execution_options(populate_existing=True))

    def publication_record_by_project(self, project_id: int) -> PublicationRecord | None:
        row = self._session.execute(
            self._publication_record_statement().where(
                CommunityPublication.project_id == project_id
            )
        ).first()
        return self._to_publication_record(row) if row else None

    def publication_record(self, publication_id: int) -> PublicationRecord | None:
        row = self._session.execute(
            self._publication_record_statement().where(
                CommunityPublication.id == publication_id
            )
        ).first()
        return self._to_publication_record(row) if row else None

    def publication_version(
        self, publication_id: int, version_number: int
    ) -> CommunityPublicationVersion | None:
        return self._session.scalar(
            select(CommunityPublicationVersion).where(
                CommunityPublicationVersion.publication_id == publication_id,
                CommunityPublicationVersion.version_number == version_number,
            )
        )

    def publication_version_by_request(
        self, publication_id: int, request_key: str
    ) -> CommunityPublicationVersion | None:
        return self._session.scalar(
            select(CommunityPublicationVersion).where(
                CommunityPublicationVersion.publication_id == publication_id,
                CommunityPublicationVersion.request_key == request_key,
            )
        )

    def next_publication_version(self, publication_id: int) -> int:
        current = self._session.scalar(
            select(func.max(CommunityPublicationVersion.version_number)).where(
                CommunityPublicationVersion.publication_id == publication_id
            )
        )
        return int(current or 0) + 1

    def publication_page(
        self,
        *,
        owner_user_id: int | None,
        moderation_queue: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[PublicationRecord], int]:
        conditions = []
        if owner_user_id is not None:
            conditions.append(CommunityPublication.owner_user_id == owner_user_id)
        if moderation_queue:
            conditions.append(
                or_(
                    CommunityPublication.status == "legacy_review_required",
                    CommunityPublication.pending_version_number.is_not(None),
                )
            )
        total = int(
            self._session.scalar(
                select(func.count(CommunityPublication.id)).where(*conditions)
            )
            or 0
        )
        rows = self._session.execute(
            self._publication_record_statement()
            .where(*conditions)
            .order_by(
                CommunityPublication.submitted_at.desc(),
                CommunityPublication.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return [self._to_publication_record(row) for row in rows], total

    def publication_actions(
        self, publication_id: int, *, limit: int = 50
    ) -> list[CommunityGovernanceAction]:
        return list(
            self._session.scalars(
                select(CommunityGovernanceAction)
                .where(CommunityGovernanceAction.publication_id == publication_id)
                .order_by(
                    CommunityGovernanceAction.occurred_at.desc(),
                    CommunityGovernanceAction.id.desc(),
                )
                .limit(limit)
            )
        )

    def list_tags(self) -> list[TagRecord]:
        statement = (
            select(Tag, func.count(project_tags.c.project_id))
            .join(project_tags, project_tags.c.tag_id == Tag.id)
            .join(Project, Project.id == project_tags.c.project_id)
            .join(CommunityPublication, CommunityPublication.project_id == Project.id)
            .where(
                Project.is_published.is_(True),
                CommunityPublication.public_version_number.is_not(None),
            )
            .group_by(Tag.id)
            .order_by(func.count(project_tags.c.project_id).desc(), Tag.name.asc())
        )
        return [TagRecord(tag=row[0], project_count=int(row[1])) for row in self._session.execute(statement)]

    def set_project_tags(self, project: Project, tag_names: list[str]) -> None:
        project.tags = self._resolve_tags(tag_names)
        self._session.flush()

    def increment_view(self, project_id: int, user_id: int) -> int | None:
        result = self._session.execute(
            update(Project)
            .where(Project.id == project_id, Project.is_published.is_(True))
            .values(view_count=Project.view_count + 1)
        )
        if result.rowcount != 1:
            return None
        self._session.add(ProjectView(project_id=project_id, user_id=user_id))
        self._session.flush()
        return self._session.scalar(select(Project.view_count).where(Project.id == project_id))

    def count_comments(self, project_id: int) -> int:
        return int(
            self._session.scalar(
                select(func.count(Comment.id)).where(
                    Comment.project_id == project_id,
                    Comment.is_deleted.is_(False),
                    Comment.moderation_status == CommentModerationStatus.VISIBLE,
                )
            )
            or 0
        )

    def list_comments(self, project_id: int, *, offset: int, limit: int) -> list[Comment]:
        return list(
            self._session.scalars(
                select(Comment)
                .options(joinedload(Comment.user))
                .where(
                    Comment.project_id == project_id,
                    Comment.is_deleted.is_(False),
                    Comment.moderation_status == CommentModerationStatus.VISIBLE,
                )
                .order_by(Comment.created_at.asc(), Comment.id.asc())
                .offset(offset)
                .limit(limit)
            )
        )

    def comment(
        self,
        comment_id: int,
        *,
        visible_only: bool = False,
        for_update: bool = False,
    ) -> Comment | None:
        conditions = [Comment.id == comment_id, Comment.is_deleted.is_(False)]
        if visible_only:
            conditions.append(Comment.moderation_status == CommentModerationStatus.VISIBLE)
        statement = select(Comment).options(joinedload(Comment.user)).where(*conditions)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement.execution_options(populate_existing=True))

    def recent_comment_count(self, user_id: int, since: datetime) -> int:
        return int(
            self._session.scalar(
                select(func.count(Comment.id)).where(
                    Comment.user_id == user_id,
                    Comment.created_at >= since,
                    Comment.is_deleted.is_(False),
                )
            )
            or 0
        )

    def recent_case_count(self, user_id: int, since: datetime) -> int:
        return int(
            self._session.scalar(
                select(func.count(CommunityGovernanceCase.id)).where(
                    CommunityGovernanceCase.opened_by_user_id == user_id,
                    CommunityGovernanceCase.created_at >= since,
                )
            )
            or 0
        )

    def soft_delete_comment(self, comment: Comment, at: datetime) -> None:
        comment.is_deleted = True
        comment.deleted_at = at
        comment.revision += 1
        self._session.flush()

    def set_like(self, project_id: int, user_id: int, *, active: bool) -> int:
        self._set_interaction(Like, project_id, user_id, active=active)
        return self._count_interactions(Like, project_id)

    def set_favorite(self, project_id: int, user_id: int, *, active: bool) -> int:
        self._set_interaction(Favorite, project_id, user_id, active=active)
        return self._count_interactions(Favorite, project_id)

    def governance_case_by_request(
        self, user_id: int, request_key: str
    ) -> CommunityGovernanceCase | None:
        return self._session.scalar(
            select(CommunityGovernanceCase).where(
                CommunityGovernanceCase.opened_by_user_id == user_id,
                CommunityGovernanceCase.request_key == request_key,
            )
        )

    def governance_case(
        self, case_id: int, *, for_update: bool = False
    ) -> CommunityGovernanceCase | None:
        statement = select(CommunityGovernanceCase).where(
            CommunityGovernanceCase.id == case_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement.execution_options(populate_existing=True))

    def governance_case_page(
        self,
        *,
        viewer_id: int,
        administrator: bool,
        status: GovernanceCaseStatus | None,
        offset: int,
        limit: int,
    ) -> tuple[list[CommunityGovernanceCase], int]:
        conditions = []
        if not administrator:
            conditions.append(
                or_(
                    CommunityGovernanceCase.opened_by_user_id == viewer_id,
                    CommunityGovernanceCase.target_owner_user_id == viewer_id,
                )
            )
        if status is not None:
            conditions.append(CommunityGovernanceCase.status == status)
        total = int(
            self._session.scalar(
                select(func.count(CommunityGovernanceCase.id)).where(*conditions)
            )
            or 0
        )
        values = list(
            self._session.scalars(
                select(CommunityGovernanceCase)
                .where(*conditions)
                .order_by(
                    CommunityGovernanceCase.created_at.desc(),
                    CommunityGovernanceCase.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
        )
        return values, total

    def governance_action(self, action_id: int) -> CommunityGovernanceAction | None:
        return self._session.scalar(
            select(CommunityGovernanceAction).where(
                CommunityGovernanceAction.id == action_id
            )
        )

    def add_notification(self, notification: Notification) -> None:
        self.add(notification)

    def _project_statement(self, viewer_id: int):
        version = aliased(CommunityPublicationVersion)
        comment_count = (
            select(func.count(Comment.id))
            .where(
                Comment.project_id == Project.id,
                Comment.is_deleted.is_(False),
                Comment.moderation_status == CommentModerationStatus.VISIBLE,
            )
            .correlate(Project)
            .scalar_subquery()
        )
        like_count = select(func.count(Like.id)).where(Like.project_id == Project.id).correlate(Project).scalar_subquery()
        favorite_count = select(func.count(Favorite.id)).where(Favorite.project_id == Project.id).correlate(Project).scalar_subquery()
        liked = exists().where(Like.project_id == Project.id, Like.user_id == viewer_id)
        favorited = exists().where(Favorite.project_id == Project.id, Favorite.user_id == viewer_id)
        return (
            select(
                Project,
                CommunityPublication,
                version,
                comment_count,
                like_count,
                favorite_count,
                liked,
                favorited,
            )
            .join(CommunityPublication, CommunityPublication.project_id == Project.id)
            .join(
                version,
                and_(
                    version.publication_id == CommunityPublication.id,
                    version.version_number == CommunityPublication.public_version_number,
                ),
            )
            .where(
                Project.is_published.is_(True),
                CommunityPublication.public_version_number.is_not(None),
            )
            .options(joinedload(Project.owner), selectinload(Project.tags))
        )

    @staticmethod
    def _to_project_record(row) -> CommunityProjectRecord:
        return CommunityProjectRecord(
            project=row[0],
            publication=row[1],
            version=row[2],
            comment_count=int(row[3]),
            like_count=int(row[4]),
            favorite_count=int(row[5]),
            liked=bool(row[6]),
            favorited=bool(row[7]),
        )

    def _publication_record_statement(self):
        public_version = aliased(CommunityPublicationVersion)
        pending_version = aliased(CommunityPublicationVersion)
        return (
            select(CommunityPublication, public_version, pending_version)
            .outerjoin(
                public_version,
                and_(
                    public_version.publication_id == CommunityPublication.id,
                    public_version.version_number == CommunityPublication.public_version_number,
                ),
            )
            .outerjoin(
                pending_version,
                and_(
                    pending_version.publication_id == CommunityPublication.id,
                    pending_version.version_number == CommunityPublication.pending_version_number,
                ),
            )
        )

    @staticmethod
    def _to_publication_record(row) -> PublicationRecord:
        return PublicationRecord(
            publication=row[0], public_version=row[1], pending_version=row[2]
        )

    def _resolve_tags(self, tag_names: list[str]) -> list[Tag]:
        requested = [(name, self._slugify(name)) for name in tag_names]
        slugs = [slug for _, slug in requested]
        existing = (
            {tag.slug: tag for tag in self._session.scalars(select(Tag).where(Tag.slug.in_(slugs)))}
            if slugs
            else {}
        )
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
            raise ConflictError("标签不能为空")
        return slug[:64]

    def _set_interaction(self, model, project_id: int, user_id: int, *, active: bool) -> None:
        predicate = (model.project_id == project_id, model.user_id == user_id)
        existing_id = self._session.scalar(select(model.id).where(*predicate))
        if active and existing_id is None:
            self._session.add(model(project_id=project_id, user_id=user_id))
            self._session.flush()
        elif not active and existing_id is not None:
            self._session.execute(delete(model).where(model.id == existing_id))
            self._session.flush()

    def _count_interactions(self, model, project_id: int) -> int:
        return int(
            self._session.scalar(select(func.count(model.id)).where(model.project_id == project_id))
            or 0
        )
