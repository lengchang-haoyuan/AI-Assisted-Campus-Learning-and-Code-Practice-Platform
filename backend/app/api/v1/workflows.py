from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import CurrentUser, WorkflowServiceDependency
from app.api.presenters import (
    to_workflow_edge_list_response,
    to_workflow_edge_response,
    to_workflow_graph_response,
    to_workflow_list_response,
    to_workflow_node_list_response,
    to_workflow_node_response,
    to_workflow_response,
)
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowEdgeCreate,
    WorkflowEdgeListResponse,
    WorkflowEdgeResponse,
    WorkflowEdgeUpdate,
    WorkflowGraphResponse,
    WorkflowGraphUpdate,
    WorkflowListResponse,
    WorkflowNodeCreate,
    WorkflowNodeListResponse,
    WorkflowNodeResponse,
    WorkflowNodeUpdate,
    WorkflowResponse,
    WorkflowUpdate,
)
from app.services.workflow import (
    WorkflowCreateData,
    WorkflowEdgeCreateData,
    WorkflowEdgeUpdateData,
    WorkflowGraphEdgeData,
    WorkflowGraphNodeData,
    WorkflowGraphUpdateData,
    WorkflowNodeCreateData,
    WorkflowNodeUpdateData,
    WorkflowUpdateData,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])

ResourceId = Annotated[int, Path(ge=1)]


@router.get("", response_model=WorkflowListResponse, summary="获取当前用户的工作流列表")
async def list_workflows(
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    project_id: Annotated[int | None, Query(ge=1)] = None,
) -> WorkflowListResponse:
    return to_workflow_list_response(
        service.list_workflows(
            current_user.id,
            page=page,
            page_size=page_size,
            project_id=project_id,
        )
    )


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建工作流",
)
async def create_workflow(
    payload: WorkflowCreate,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowResponse:
    return to_workflow_response(
        service.create_workflow(
            current_user.id, WorkflowCreateData(**payload.model_dump())
        )
    )


@router.get(
    "/{workflow_id}/graph",
    response_model=WorkflowGraphResponse,
    summary="读取完整工作流图",
)
async def get_workflow_graph(
    workflow_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowGraphResponse:
    return to_workflow_graph_response(
        service.get_graph(workflow_id, current_user.id)
    )


@router.put(
    "/{workflow_id}/graph",
    response_model=WorkflowGraphResponse,
    summary="原子保存完整工作流图",
)
async def replace_workflow_graph(
    workflow_id: ResourceId,
    payload: WorkflowGraphUpdate,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowGraphResponse:
    data = WorkflowGraphUpdateData(
        version=payload.version,
        nodes=[
            WorkflowGraphNodeData(**node.model_dump()) for node in payload.nodes
        ],
        edges=[
            WorkflowGraphEdgeData(**edge.model_dump()) for edge in payload.edges
        ],
    )
    return to_workflow_graph_response(
        service.replace_graph(workflow_id, current_user.id, data)
    )


@router.get(
    "/{workflow_id}/nodes",
    response_model=WorkflowNodeListResponse,
    summary="获取工作流节点列表",
)
async def list_workflow_nodes(
    workflow_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowNodeListResponse:
    return to_workflow_node_list_response(
        service.list_nodes(workflow_id, current_user.id)
    )


@router.post(
    "/{workflow_id}/nodes",
    response_model=WorkflowNodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建工作流节点",
)
async def create_workflow_node(
    workflow_id: ResourceId,
    payload: WorkflowNodeCreate,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowNodeResponse:
    return to_workflow_node_response(
        service.create_node(
            workflow_id,
            current_user.id,
            WorkflowNodeCreateData(**payload.model_dump()),
        )
    )


@router.get(
    "/{workflow_id}/nodes/{node_id}",
    response_model=WorkflowNodeResponse,
    summary="获取工作流节点详情",
)
async def get_workflow_node(
    workflow_id: ResourceId,
    node_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowNodeResponse:
    return to_workflow_node_response(
        service.get_node(workflow_id, node_id, current_user.id)
    )


@router.put(
    "/{workflow_id}/nodes/{node_id}",
    response_model=WorkflowNodeResponse,
    summary="更新工作流节点",
)
async def update_workflow_node(
    workflow_id: ResourceId,
    node_id: ResourceId,
    payload: WorkflowNodeUpdate,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowNodeResponse:
    return to_workflow_node_response(
        service.update_node(
            workflow_id,
            node_id,
            current_user.id,
            WorkflowNodeUpdateData(payload.model_dump(exclude_unset=True)),
        )
    )


@router.delete(
    "/{workflow_id}/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除工作流节点",
)
async def delete_workflow_node(
    workflow_id: ResourceId,
    node_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> Response:
    service.delete_node(workflow_id, node_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{workflow_id}/edges",
    response_model=WorkflowEdgeListResponse,
    summary="获取工作流边列表",
)
async def list_workflow_edges(
    workflow_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowEdgeListResponse:
    return to_workflow_edge_list_response(
        service.list_edges(workflow_id, current_user.id)
    )


@router.post(
    "/{workflow_id}/edges",
    response_model=WorkflowEdgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建工作流边",
)
async def create_workflow_edge(
    workflow_id: ResourceId,
    payload: WorkflowEdgeCreate,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowEdgeResponse:
    return to_workflow_edge_response(
        service.create_edge(
            workflow_id,
            current_user.id,
            WorkflowEdgeCreateData(**payload.model_dump()),
        )
    )


@router.get(
    "/{workflow_id}/edges/{edge_id}",
    response_model=WorkflowEdgeResponse,
    summary="获取工作流边详情",
)
async def get_workflow_edge(
    workflow_id: ResourceId,
    edge_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowEdgeResponse:
    return to_workflow_edge_response(
        service.get_edge(workflow_id, edge_id, current_user.id)
    )


@router.put(
    "/{workflow_id}/edges/{edge_id}",
    response_model=WorkflowEdgeResponse,
    summary="更新工作流边",
)
async def update_workflow_edge(
    workflow_id: ResourceId,
    edge_id: ResourceId,
    payload: WorkflowEdgeUpdate,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowEdgeResponse:
    return to_workflow_edge_response(
        service.update_edge(
            workflow_id,
            edge_id,
            current_user.id,
            WorkflowEdgeUpdateData(payload.model_dump(exclude_unset=True)),
        )
    )


@router.delete(
    "/{workflow_id}/edges/{edge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除工作流边",
)
async def delete_workflow_edge(
    workflow_id: ResourceId,
    edge_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> Response:
    service.delete_edge(workflow_id, edge_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="获取工作流详情",
)
async def get_workflow(
    workflow_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowResponse:
    return to_workflow_response(service.get_workflow(workflow_id, current_user.id))


@router.put(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="更新工作流",
)
async def update_workflow(
    workflow_id: ResourceId,
    payload: WorkflowUpdate,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> WorkflowResponse:
    return to_workflow_response(
        service.update_workflow(
            workflow_id,
            current_user.id,
            WorkflowUpdateData(payload.model_dump(exclude_unset=True)),
        )
    )


@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除工作流",
)
async def delete_workflow(
    workflow_id: ResourceId,
    current_user: CurrentUser,
    service: WorkflowServiceDependency,
) -> Response:
    service.delete_workflow(workflow_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
