from app.schemas.project import (
    ProjectListResponse,
    ProjectOwnerResponse,
    ProjectResponse,
)
from app.schemas.user import UserResponse
from app.services.auth import UserIdentity
from app.services.project import ProjectData, ProjectPage


def to_user_response(user: UserIdentity) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        bio=user.bio,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def to_project_response(project: ProjectData) -> ProjectResponse:
    return ProjectResponse(
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
        owner=ProjectOwnerResponse(
            id=project.owner.id,
            username=project.owner.username,
        ),
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def to_project_list_response(page: ProjectPage) -> ProjectListResponse:
    return ProjectListResponse(
        items=[to_project_response(project) for project in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=page.total_pages,
    )
