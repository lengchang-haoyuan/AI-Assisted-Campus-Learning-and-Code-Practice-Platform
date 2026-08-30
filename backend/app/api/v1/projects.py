from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import CurrentUser, ProjectServiceDependency
from app.api.presenters import to_project_list_response, to_project_response
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project import ProjectCreateData, ProjectUpdateData

router = APIRouter(prefix="/projects", tags=["projects"])

ProjectId = Annotated[int, Path(ge=1)]


@router.get("", response_model=ProjectListResponse, summary="获取当前用户的项目列表")
async def list_projects(
    current_user: CurrentUser,
    service: ProjectServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProjectListResponse:
    result = service.list_projects(current_user.id, page=page, page_size=page_size)
    return to_project_list_response(result)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建项目",
)
async def create_project(
    payload: ProjectCreate,
    current_user: CurrentUser,
    service: ProjectServiceDependency,
) -> ProjectResponse:
    data = ProjectCreateData(**payload.model_dump())
    return to_project_response(service.create_project(current_user.id, data))


@router.get("/{project_id}", response_model=ProjectResponse, summary="获取项目详情")
async def get_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: ProjectServiceDependency,
) -> ProjectResponse:
    return to_project_response(service.get_project(project_id, current_user.id))


@router.put("/{project_id}", response_model=ProjectResponse, summary="更新项目")
async def update_project(
    project_id: ProjectId,
    payload: ProjectUpdate,
    current_user: CurrentUser,
    service: ProjectServiceDependency,
) -> ProjectResponse:
    data = ProjectUpdateData(payload.model_dump(exclude_unset=True))
    return to_project_response(
        service.update_project(project_id, current_user.id, data)
    )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除项目",
)
async def delete_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: ProjectServiceDependency,
) -> Response:
    service.delete_project(project_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
