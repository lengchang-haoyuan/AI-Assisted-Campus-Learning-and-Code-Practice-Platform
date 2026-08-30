from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.project import Project


class ProjectPersistenceConflictError(Exception):
    """项目写入与当前数据库约束冲突。"""


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_by_owner(self, owner_id: int) -> int:
        statement = select(func.count(Project.id)).where(Project.owner_id == owner_id)
        return self._session.scalar(statement) or 0

    def list_by_owner(
        self, owner_id: int, *, offset: int, limit: int
    ) -> list[Project]:
        statement = (
            select(Project)
            .options(joinedload(Project.owner))
            .where(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc(), Project.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def get_by_id(self, project_id: int) -> Project | None:
        statement = (
            select(Project)
            .options(joinedload(Project.owner))
            .where(Project.id == project_id)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def create(self, project: Project) -> Project:
        self._session.add(project)
        self._commit_or_raise_conflict()
        return self._reload(project.id)

    def update(self, project: Project) -> Project:
        self._commit_or_raise_conflict()
        return self._reload(project.id)

    def delete(self, project: Project) -> None:
        self._session.delete(project)
        self._commit_or_raise_conflict()

    def _reload(self, project_id: int) -> Project:
        project = self.get_by_id(project_id)
        if project is None:
            raise RuntimeError("项目写入后无法重新加载")
        return project

    def _commit_or_raise_conflict(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ProjectPersistenceConflictError from exc
