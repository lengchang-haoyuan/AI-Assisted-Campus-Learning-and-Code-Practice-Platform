from dataclasses import asdict, dataclass, field
from datetime import datetime
from math import ceil
from typing import Any, Mapping

from app.core.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.enums import ProjectDifficulty, ProjectStatus
from app.models.project import Project
from app.repositories.project import (
    ProjectPersistenceConflictError,
    ProjectRepository,
)

PROJECT_MUTABLE_FIELDS = frozenset(
    {
        "name",
        "description",
        "difficulty",
        "language",
        "framework",
        "frontend",
        "backend",
        "database",
        "requirements",
        "output_requirement",
        "status",
    }
)


@dataclass(frozen=True, slots=True)
class ProjectCreateData:
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
    requirements: list[dict[str, Any]] | None
    output_requirement: str | None
    status: ProjectStatus


@dataclass(frozen=True, slots=True)
class ProjectUpdateData:
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.values or not self.values.keys() <= PROJECT_MUTABLE_FIELDS:
            raise ValueError("项目更新字段无效")


@dataclass(frozen=True, slots=True)
class ProjectOwner:
    id: int
    username: str


@dataclass(frozen=True, slots=True)
class ProjectData:
    id: int
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
    requirements: list[dict[str, Any]] | None
    output_requirement: str | None
    owner: ProjectOwner
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    tags: list[tuple[int, str, str]] = field(default_factory=list)
    is_published: bool = False
    published_at: datetime | None = None
    view_count: int = 0
    progress: int = 0


@dataclass(frozen=True, slots=True)
class ProjectPage:
    items: list[ProjectData]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProjectService:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def create_project(self, owner_id: int, data: ProjectCreateData) -> ProjectData:
        project = Project(owner_id=owner_id, **asdict(data))
        try:
            return self._to_data(self._repository.create(project))
        except ProjectPersistenceConflictError as exc:
            raise ConflictError("项目数据与当前状态冲突") from exc

    def list_projects(
        self, owner_id: int, *, page: int, page_size: int
    ) -> ProjectPage:
        total = self._repository.count_by_owner(owner_id)
        projects = self._repository.list_by_owner(
            owner_id, offset=(page - 1) * page_size, limit=page_size
        )
        return ProjectPage(
            items=[self._to_data(project) for project in projects],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_project(self, project_id: int, owner_id: int) -> ProjectData:
        return self._to_data(self._get_owned_project(project_id, owner_id))

    def update_project(
        self, project_id: int, owner_id: int, data: ProjectUpdateData
    ) -> ProjectData:
        project = self._get_owned_project(project_id, owner_id)
        for field_name, value in data.values.items():
            setattr(project, field_name, value)
        try:
            return self._to_data(self._repository.update(project))
        except ProjectPersistenceConflictError as exc:
            raise ConflictError("项目数据与当前状态冲突") from exc

    def delete_project(self, project_id: int, owner_id: int) -> None:
        project = self._get_owned_project(project_id, owner_id)
        try:
            self._repository.delete(project)
        except ProjectPersistenceConflictError as exc:
            raise ConflictError("项目仍被受限数据引用，暂时无法删除") from exc

    def _get_owned_project(self, project_id: int, owner_id: int) -> Project:
        project = self._repository.get_by_id(project_id)
        if project is None:
            raise ResourceNotFoundError("项目不存在")
        if project.owner_id != owner_id:
            raise PermissionDeniedError("无权操作该项目")
        return project

    @staticmethod
    def _to_data(project: Project) -> ProjectData:
        return ProjectData(
            id=project.id,
            name=project.name,
            description=project.description,
            difficulty=project.difficulty,
            language=project.language,
            framework=project.framework,
            frontend=project.frontend,
            backend=project.backend,
            database=project.database,
            requirements=project.requirements,
            output_requirement=project.output_requirement,
            owner=ProjectOwner(id=project.owner.id, username=project.owner.username),
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
            tags=[(tag.id, tag.name, tag.slug) for tag in project.tags],
            is_published=project.is_published,
            published_at=project.published_at,
            view_count=project.view_count,
            progress=project.progress,
        )
