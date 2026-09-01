from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.deps import CurrentUser, WorkspaceServiceDependency
from app.api.presenters import (
    to_learning_record_list_response,
    to_learning_record_response,
    to_task_list_response,
    to_task_response,
    to_workspace_dashboard_response,
    to_workspace_project_detail_response,
    to_workspace_project_list_response,
)
from app.schemas.workspace import (
    LearningRecordCreate,
    LearningRecordListResponse,
    LearningRecordResponse,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    WorkspaceDashboardResponse,
    WorkspaceProjectDetailResponse,
    WorkspaceProjectListResponse,
)
from app.services.workspace import LearningRecordCreateData, TaskCreateData

router = APIRouter(prefix="/workspace", tags=["workspace"])
TaskId = Annotated[int, Path(ge=1)]
ProjectId = Annotated[int, Path(ge=1)]


@router.get(
    "/dashboard",
    response_model=WorkspaceDashboardResponse,
    summary="获取个人工作台聚合数据",
)
async def get_workspace_dashboard(
    current_user: CurrentUser,
    service: WorkspaceServiceDependency,
    selected_date: Annotated[date, Query(alias="date")],
    utc_offset_minutes: Annotated[int, Query(ge=-840, le=840)] = 0,
) -> WorkspaceDashboardResponse:
    return to_workspace_dashboard_response(
        service.get_dashboard(
            current_user.id,
            selected_date=selected_date,
            utc_offset_minutes=utc_offset_minutes,
        )
    )


@router.get("/tasks", response_model=TaskListResponse, summary="获取个人任务")
async def list_tasks(
    current_user: CurrentUser,
    service: WorkspaceServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    scheduled_date: Annotated[date | None, Query(alias="date")] = None,
) -> TaskListResponse:
    return to_task_list_response(
        service.list_tasks(
            current_user.id,
            page=page,
            page_size=page_size,
            scheduled_date=scheduled_date,
        )
    )


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建个人任务",
)
async def create_task(
    payload: TaskCreate,
    current_user: CurrentUser,
    service: WorkspaceServiceDependency,
) -> TaskResponse:
    return to_task_response(
        service.create_task(current_user.id, TaskCreateData(**payload.model_dump()))
    )


@router.post(
    "/tasks/{task_id}/complete",
    response_model=TaskResponse,
    summary="完成个人任务",
)
async def complete_task(
    task_id: TaskId,
    current_user: CurrentUser,
    service: WorkspaceServiceDependency,
) -> TaskResponse:
    return to_task_response(service.complete_task(task_id, current_user.id))


@router.get(
    "/projects",
    response_model=WorkspaceProjectListResponse,
    summary="获取工作台项目进度",
)
async def list_workspace_projects(
    current_user: CurrentUser,
    service: WorkspaceServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WorkspaceProjectListResponse:
    return to_workspace_project_list_response(
        service.list_projects(current_user.id, page=page, page_size=page_size)
    )


@router.get(
    "/projects/{project_id}",
    response_model=WorkspaceProjectDetailResponse,
    summary="获取工作台项目详情",
)
async def get_workspace_project(
    project_id: ProjectId,
    current_user: CurrentUser,
    service: WorkspaceServiceDependency,
) -> WorkspaceProjectDetailResponse:
    return to_workspace_project_detail_response(
        service.get_project(project_id, current_user.id)
    )


@router.get(
    "/records",
    response_model=LearningRecordListResponse,
    summary="获取个人学习记录",
)
async def list_learning_records(
    current_user: CurrentUser,
    service: WorkspaceServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LearningRecordListResponse:
    return to_learning_record_list_response(
        service.list_records(current_user.id, page=page, page_size=page_size)
    )


@router.post(
    "/records",
    response_model=LearningRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="保存学习记录",
)
async def create_learning_record(
    payload: LearningRecordCreate,
    current_user: CurrentUser,
    service: WorkspaceServiceDependency,
) -> LearningRecordResponse:
    return to_learning_record_response(
        service.create_record(
            current_user.id,
            LearningRecordCreateData(**payload.model_dump()),
        )
    )
