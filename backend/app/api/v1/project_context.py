from typing import Annotated

from fastapi import APIRouter, Path, status

from app.api.deps import CurrentUser, ProjectContextServiceDependency
from app.api.presenters import (
    to_node_context_response,
    to_project_context_mutation_response,
    to_project_context_response,
)
from app.schemas.project_context import (
    NodeContextReadRequest,
    NodeContextResponse,
    NodeContextWriteRequest,
    ProjectContextMutationResponse,
    ProjectContextResponse,
    ProjectContextUpdateRequest,
)
from app.services.project_context import (
    NodeContextReadData,
    NodeContextWriteData,
    ProjectContextUpdateData,
)

router = APIRouter(tags=["project-context"])
ResourceId = Annotated[int, Path(ge=1)]


@router.post(
    "/projects/{project_id}/context",
    response_model=ProjectContextResponse,
    status_code=status.HTTP_201_CREATED,
    summary="从项目创建 ProjectContext",
)
def create_project_context(
    project_id: ResourceId,
    current_user: CurrentUser,
    service: ProjectContextServiceDependency,
) -> ProjectContextResponse:
    return to_project_context_response(
        service.create_context(project_id, current_user.id)
    )


@router.get(
    "/projects/{project_id}/context",
    response_model=ProjectContextResponse,
    summary="读取 ProjectContext",
)
def get_project_context(
    project_id: ResourceId,
    current_user: CurrentUser,
    service: ProjectContextServiceDependency,
) -> ProjectContextResponse:
    return to_project_context_response(service.get_context(project_id, current_user.id))


@router.put(
    "/projects/{project_id}/context",
    response_model=ProjectContextMutationResponse,
    summary="更新 ProjectContext 并标记依赖节点过期",
)
def update_project_context(
    project_id: ResourceId,
    payload: ProjectContextUpdateRequest,
    current_user: CurrentUser,
    service: ProjectContextServiceDependency,
) -> ProjectContextMutationResponse:
    return to_project_context_mutation_response(
        service.update_context(
            project_id,
            current_user.id,
            ProjectContextUpdateData(
                expected_version=payload.expected_version,
                values=payload.values.model_dump(exclude_unset=True),
            ),
        )
    )


@router.post(
    "/workflows/{workflow_id}/nodes/{node_id}/context/read",
    response_model=NodeContextResponse,
    summary="按节点权限读取 ProjectContext",
)
def read_workflow_node_context(
    workflow_id: ResourceId,
    node_id: ResourceId,
    payload: NodeContextReadRequest,
    current_user: CurrentUser,
    service: ProjectContextServiceDependency,
) -> NodeContextResponse:
    return to_node_context_response(
        service.read_node_context(
            workflow_id,
            node_id,
            current_user.id,
            NodeContextReadData(fields=payload.fields),
        )
    )


@router.post(
    "/workflows/{workflow_id}/nodes/{node_id}/context/write",
    response_model=ProjectContextMutationResponse,
    summary="按节点权限写入 ProjectContext",
)
def write_workflow_node_context(
    workflow_id: ResourceId,
    node_id: ResourceId,
    payload: NodeContextWriteRequest,
    current_user: CurrentUser,
    service: ProjectContextServiceDependency,
) -> ProjectContextMutationResponse:
    return to_project_context_mutation_response(
        service.write_node_context(
            workflow_id,
            node_id,
            current_user.id,
            NodeContextWriteData(
                expected_version=payload.expected_version,
                values=payload.values.model_dump(exclude_unset=True),
            ),
        )
    )
