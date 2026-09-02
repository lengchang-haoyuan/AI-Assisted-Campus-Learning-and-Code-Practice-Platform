from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Any, Mapping, cast

from pydantic import ValidationError

from app.core.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.enums import (
    AIRequestStatus,
    WorkflowNodeStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from app.models.project import Project
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode, WorkflowRun
from app.repositories.workflow import (
    WorkflowEdgeRecord,
    WorkflowNodeRecord,
    WorkflowPersistenceConflictError,
    WorkflowRepository,
    WorkflowVersionConflictError,
)
from app.repositories.workflow_execution import WorkflowExecutionRepository
from app.workflow.engine import WorkflowEngine, WorkflowRunMode
from app.workflow.schemas import (
    WORKFLOW_NODE_RESULT_SCHEMAS,
    WorkflowNodeResult,
)

MAX_GRAPH_NODES = 100
MAX_GRAPH_EDGES = 300
WORKFLOW_MUTABLE_FIELDS = frozenset({"name", "description", "status"})
NODE_MUTABLE_FIELDS = frozenset(
    {"node_key", "node_type", "name", "position_x", "position_y", "config"}
)
EDGE_MUTABLE_FIELDS = frozenset(
    {"source_node_id", "target_node_id", "condition_data"}
)


@dataclass(frozen=True, slots=True)
class WorkflowCreateData:
    project_id: int
    name: str
    description: str | None
    status: WorkflowStatus


@dataclass(frozen=True, slots=True)
class WorkflowUpdateData:
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.values or not self.values.keys() <= WORKFLOW_MUTABLE_FIELDS:
            raise ValueError("工作流更新字段无效")


@dataclass(frozen=True, slots=True)
class WorkflowProjectData:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class WorkflowData:
    id: int
    project: WorkflowProjectData
    name: str
    description: str | None
    status: WorkflowStatus
    version: int
    node_count: int
    edge_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowPage:
    items: list[WorkflowData]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class WorkflowNodeCreateData:
    node_key: str
    node_type: str
    name: str
    position_x: float
    position_y: float
    config: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class WorkflowNodeUpdateData:
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.values or not self.values.keys() <= NODE_MUTABLE_FIELDS:
            raise ValueError("节点更新字段无效")


@dataclass(frozen=True, slots=True)
class WorkflowNodeData:
    id: int
    workflow_id: int
    node_key: str
    node_type: str
    name: str
    position_x: float
    position_y: float
    config: dict[str, Any] | None
    status: WorkflowNodeStatus
    context_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowEdgeCreateData:
    source_node_id: int
    target_node_id: int
    condition_data: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class WorkflowEdgeUpdateData:
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.values or not self.values.keys() <= EDGE_MUTABLE_FIELDS:
            raise ValueError("边更新字段无效")


@dataclass(frozen=True, slots=True)
class WorkflowEdgeData:
    id: int
    workflow_id: int
    source_node_id: int
    target_node_id: int
    source_node_key: str
    target_node_key: str
    condition_data: dict[str, Any] | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowGraphNodeData:
    node_key: str
    node_type: str
    name: str
    position_x: float
    position_y: float
    config: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class WorkflowGraphEdgeData:
    source_node_key: str
    target_node_key: str
    condition_data: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class WorkflowGraphUpdateData:
    version: int
    nodes: list[WorkflowGraphNodeData]
    edges: list[WorkflowGraphEdgeData]


@dataclass(frozen=True, slots=True)
class WorkflowGraphData:
    workflow: WorkflowData
    nodes: list[WorkflowNodeData]
    edges: list[WorkflowEdgeData]


@dataclass(frozen=True, slots=True)
class WorkflowRunRequestData:
    expected_version: int
    mode: WorkflowRunMode


@dataclass(frozen=True, slots=True)
class WorkflowRunErrorData:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class WorkflowRunNodeData:
    request_id: int
    node_id: int
    node_key: str
    node_type: str
    status: AIRequestStatus
    result: WorkflowNodeResult | None
    error: WorkflowRunErrorData | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None
    requested_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class WorkflowRunData:
    id: int
    workflow_id: int
    status: WorkflowRunStatus
    context_version: int
    error: WorkflowRunErrorData | None
    nodes: list[WorkflowRunNodeData]
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowRunPage:
    items: list[WorkflowRunData]
    total: int
    page: int
    page_size: int
    total_pages: int


class WorkflowService:
    def __init__(
        self,
        repository: WorkflowRepository,
        execution_repository: WorkflowExecutionRepository | None = None,
        engine: WorkflowEngine | None = None,
    ) -> None:
        self._repository = repository
        self._execution_repository = execution_repository
        self._engine = engine

    async def run_workflow(
        self,
        workflow_id: int,
        owner_id: int,
        data: WorkflowRunRequestData,
    ) -> WorkflowRunData:
        if self._engine is None:
            raise RuntimeError("WorkflowEngine 未配置")
        run = await self._engine.run(
            workflow_id,
            owner_id,
            expected_version=data.expected_version,
            mode=data.mode,
        )
        return self._to_run_data(run)

    def list_runs(
        self,
        workflow_id: int,
        owner_id: int,
        *,
        page: int,
        page_size: int,
    ) -> WorkflowRunPage:
        self._get_owned_workflow(workflow_id, owner_id)
        repository = self._require_execution_repository()
        total = repository.count_runs(workflow_id)
        runs = repository.list_runs(
            workflow_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return WorkflowRunPage(
            items=[self._to_run_data(run) for run in runs],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_run(
        self, workflow_id: int, run_id: int, owner_id: int
    ) -> WorkflowRunData:
        self._get_owned_workflow(workflow_id, owner_id)
        run = self._require_execution_repository().get_run(workflow_id, run_id)
        if run is None:
            raise ResourceNotFoundError("WorkflowRun 不存在")
        return self._to_run_data(run)

    def list_workflows(
        self,
        owner_id: int,
        *,
        page: int,
        page_size: int,
        project_id: int | None,
    ) -> WorkflowPage:
        if project_id is not None:
            self._get_owned_project(project_id, owner_id)
        total = self._repository.count_by_owner(owner_id, project_id)
        workflows = self._repository.list_by_owner(
            owner_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            project_id=project_id,
        )
        return WorkflowPage(
            items=[self._to_workflow_data(workflow) for workflow in workflows],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def create_workflow(
        self, owner_id: int, data: WorkflowCreateData
    ) -> WorkflowData:
        project = self._get_owned_project(data.project_id, owner_id)
        if data.status != WorkflowStatus.DRAFT:
            raise ConflictError("新工作流必须从草稿状态开始")
        workflow = Workflow(
            project_id=project.id,
            name=data.name,
            description=data.description,
            status=data.status,
            version=1,
        )
        try:
            return self._to_workflow_data(
                self._repository.create_workflow(workflow)
            )
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("同一项目下的工作流名称不能重复") from exc

    def get_workflow(self, workflow_id: int, owner_id: int) -> WorkflowData:
        return self._to_workflow_data(
            self._get_owned_workflow(workflow_id, owner_id)
        )

    def update_workflow(
        self, workflow_id: int, owner_id: int, data: WorkflowUpdateData
    ) -> WorkflowData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        if data.values.get("status") == WorkflowStatus.READY and not workflow.nodes:
            raise ConflictError("空工作流不能标记为就绪")
        for field_name, value in data.values.items():
            setattr(workflow, field_name, value)
        try:
            return self._to_workflow_data(
                self._repository.update_workflow(workflow)
            )
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("同一项目下的工作流名称不能重复") from exc

    def delete_workflow(self, workflow_id: int, owner_id: int) -> None:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        try:
            self._repository.delete_workflow(workflow)
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("工作流当前无法删除") from exc

    def get_graph(self, workflow_id: int, owner_id: int) -> WorkflowGraphData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        return self._to_graph_data(workflow)

    def replace_graph(
        self, workflow_id: int, owner_id: int, data: WorkflowGraphUpdateData
    ) -> WorkflowGraphData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        if data.version != workflow.version:
            raise ConflictError("工作流已被更新，请刷新后重试")
        if workflow.status == WorkflowStatus.READY and not data.nodes:
            raise ConflictError("就绪工作流至少需要一个节点")
        self._validate_key_graph(data.nodes, data.edges)
        node_records = [
            WorkflowNodeRecord(
                node_key=node.node_key,
                node_type=node.node_type,
                name=node.name,
                position_x=node.position_x,
                position_y=node.position_y,
                config=node.config,
            )
            for node in data.nodes
        ]
        edge_records = [
            WorkflowEdgeRecord(
                source_node_key=edge.source_node_key,
                target_node_key=edge.target_node_key,
                condition_data=edge.condition_data,
            )
            for edge in data.edges
        ]
        try:
            saved = self._repository.replace_graph(
                workflow,
                expected_version=data.version,
                nodes=node_records,
                edges=edge_records,
            )
        except WorkflowVersionConflictError as exc:
            raise ConflictError("工作流已被更新，请刷新后重试") from exc
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("工作流图与当前数据冲突") from exc
        return self._to_graph_data(saved)

    def list_nodes(self, workflow_id: int, owner_id: int) -> list[WorkflowNodeData]:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        return [
            self._to_node_data(node)
            for node in sorted(workflow.nodes, key=lambda item: item.id)
        ]

    def create_node(
        self,
        workflow_id: int,
        owner_id: int,
        data: WorkflowNodeCreateData,
    ) -> WorkflowNodeData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        if len(workflow.nodes) >= MAX_GRAPH_NODES:
            raise ConflictError(f"工作流节点不能超过 {MAX_GRAPH_NODES} 个")
        if any(node.node_key == data.node_key for node in workflow.nodes):
            raise ConflictError("节点 key 不能重复")
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_key=data.node_key,
            node_type=data.node_type,
            name=data.name,
            position_x=data.position_x,
            position_y=data.position_y,
            config=data.config,
        )
        try:
            saved, _ = self._repository.create_node(workflow, node)
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("节点与当前工作流数据冲突") from exc
        return self._to_node_data(saved)

    def get_node(
        self, workflow_id: int, node_id: int, owner_id: int
    ) -> WorkflowNodeData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        return self._to_node_data(self._get_workflow_node(workflow, node_id))

    def update_node(
        self,
        workflow_id: int,
        node_id: int,
        owner_id: int,
        data: WorkflowNodeUpdateData,
    ) -> WorkflowNodeData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        node = self._get_workflow_node(workflow, node_id)
        requested_key = data.values.get("node_key")
        if requested_key is not None and any(
            item.id != node.id and item.node_key == requested_key
            for item in workflow.nodes
        ):
            raise ConflictError("节点 key 不能重复")
        for field_name, value in data.values.items():
            setattr(node, field_name, value)
        try:
            saved, _ = self._repository.update_node(workflow, node)
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("节点与当前工作流数据冲突") from exc
        return self._to_node_data(saved)

    def delete_node(
        self, workflow_id: int, node_id: int, owner_id: int
    ) -> None:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        node = self._get_workflow_node(workflow, node_id)
        if workflow.status == WorkflowStatus.READY and len(workflow.nodes) == 1:
            raise ConflictError("就绪工作流至少需要一个节点")
        try:
            self._repository.delete_node(workflow, node)
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("节点当前无法删除") from exc

    def list_edges(self, workflow_id: int, owner_id: int) -> list[WorkflowEdgeData]:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        return [
            self._to_edge_data(edge, workflow.nodes)
            for edge in sorted(workflow.edges, key=lambda item: item.id)
        ]

    def create_edge(
        self,
        workflow_id: int,
        owner_id: int,
        data: WorkflowEdgeCreateData,
    ) -> WorkflowEdgeData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        if len(workflow.edges) >= MAX_GRAPH_EDGES:
            raise ConflictError(f"工作流边不能超过 {MAX_GRAPH_EDGES} 条")
        node_ids = {node.id for node in workflow.nodes}
        pairs = [
            (edge.source_node_id, edge.target_node_id) for edge in workflow.edges
        ]
        pairs.append((data.source_node_id, data.target_node_id))
        self._validate_graph(node_ids, pairs)
        edge = WorkflowEdge(
            workflow_id=workflow.id,
            source_node_id=data.source_node_id,
            target_node_id=data.target_node_id,
            condition_data=data.condition_data,
        )
        try:
            saved, _ = self._repository.create_edge(workflow, edge)
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("边与当前工作流数据冲突") from exc
        return self._to_edge_data(saved, workflow.nodes)

    def get_edge(
        self, workflow_id: int, edge_id: int, owner_id: int
    ) -> WorkflowEdgeData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        edge = self._get_workflow_edge(workflow, edge_id)
        return self._to_edge_data(edge, workflow.nodes)

    def update_edge(
        self,
        workflow_id: int,
        edge_id: int,
        owner_id: int,
        data: WorkflowEdgeUpdateData,
    ) -> WorkflowEdgeData:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        edge = self._get_workflow_edge(workflow, edge_id)
        source_id = int(data.values.get("source_node_id", edge.source_node_id))
        target_id = int(data.values.get("target_node_id", edge.target_node_id))
        pairs = [
            (item.source_node_id, item.target_node_id)
            for item in workflow.edges
            if item.id != edge.id
        ]
        pairs.append((source_id, target_id))
        self._validate_graph({node.id for node in workflow.nodes}, pairs)
        for field_name, value in data.values.items():
            setattr(edge, field_name, value)
        try:
            saved, _ = self._repository.update_edge(workflow, edge)
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("边与当前工作流数据冲突") from exc
        return self._to_edge_data(saved, workflow.nodes)

    def delete_edge(
        self, workflow_id: int, edge_id: int, owner_id: int
    ) -> None:
        workflow = self._get_owned_workflow(workflow_id, owner_id)
        edge = self._get_workflow_edge(workflow, edge_id)
        try:
            self._repository.delete_edge(workflow, edge)
        except WorkflowPersistenceConflictError as exc:
            raise ConflictError("边当前无法删除") from exc

    def _get_owned_project(self, project_id: int, owner_id: int) -> Project:
        project = self._repository.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError("项目不存在")
        if project.owner_id != owner_id:
            raise PermissionDeniedError("不能为其他用户的项目管理工作流")
        return project

    def _get_owned_workflow(self, workflow_id: int, owner_id: int) -> Workflow:
        workflow = self._repository.get_workflow(workflow_id)
        if workflow is None:
            raise ResourceNotFoundError("工作流不存在")
        if workflow.project.owner_id != owner_id:
            raise PermissionDeniedError("无权操作该工作流")
        return workflow

    def _require_execution_repository(self) -> WorkflowExecutionRepository:
        if self._execution_repository is None:
            raise RuntimeError("WorkflowExecutionRepository 未配置")
        return self._execution_repository

    @staticmethod
    def _get_workflow_node(workflow: Workflow, node_id: int) -> WorkflowNode:
        node = next((item for item in workflow.nodes if item.id == node_id), None)
        if node is None:
            raise ResourceNotFoundError("工作流节点不存在")
        return node

    @staticmethod
    def _get_workflow_edge(workflow: Workflow, edge_id: int) -> WorkflowEdge:
        edge = next((item for item in workflow.edges if item.id == edge_id), None)
        if edge is None:
            raise ResourceNotFoundError("工作流边不存在")
        return edge

    @classmethod
    def _validate_key_graph(
        cls,
        nodes: list[WorkflowGraphNodeData],
        edges: list[WorkflowGraphEdgeData],
    ) -> None:
        cls._validate_graph(
            {node.node_key for node in nodes},
            [(edge.source_node_key, edge.target_node_key) for edge in edges],
        )

    @staticmethod
    def _validate_graph(
        node_ids: set[int] | set[str],
        edge_pairs: list[tuple[int, int]] | list[tuple[str, str]],
    ) -> None:
        normalized_nodes = {str(node_id) for node_id in node_ids}
        normalized_pairs = [(str(source), str(target)) for source, target in edge_pairs]
        if len(normalized_pairs) != len(set(normalized_pairs)):
            raise ConflictError("工作流不能包含重复边")

        adjacency = {node_id: [] for node_id in normalized_nodes}
        in_degree = {node_id: 0 for node_id in normalized_nodes}
        for source, target in normalized_pairs:
            if source not in normalized_nodes or target not in normalized_nodes:
                raise ConflictError("边引用了不存在的节点")
            if source == target:
                raise ConflictError("工作流不允许节点连接自身")
            adjacency[source].append(target)
            in_degree[target] += 1

        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        visited = 0
        while queue:
            node_id = queue.pop()
            visited += 1
            for target in adjacency[node_id]:
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)
        if visited != len(normalized_nodes):
            raise ConflictError("工作流不允许形成循环")

    @staticmethod
    def _to_workflow_data(workflow: Workflow) -> WorkflowData:
        return WorkflowData(
            id=workflow.id,
            project=WorkflowProjectData(
                id=workflow.project.id, name=workflow.project.name
            ),
            name=workflow.name,
            description=workflow.description,
            status=workflow.status,
            version=workflow.version,
            node_count=len(workflow.nodes),
            edge_count=len(workflow.edges),
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

    @staticmethod
    def _to_node_data(node: WorkflowNode) -> WorkflowNodeData:
        return WorkflowNodeData(
            id=node.id,
            workflow_id=node.workflow_id,
            node_key=node.node_key,
            node_type=node.node_type,
            name=node.name,
            position_x=float(node.position_x),
            position_y=float(node.position_y),
            config=node.config,
            status=node.status,
            context_version=node.context_version,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    @staticmethod
    def _to_edge_data(
        edge: WorkflowEdge, nodes: list[WorkflowNode]
    ) -> WorkflowEdgeData:
        keys_by_id = {node.id: node.node_key for node in nodes}
        return WorkflowEdgeData(
            id=edge.id,
            workflow_id=edge.workflow_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            source_node_key=keys_by_id[edge.source_node_id],
            target_node_key=keys_by_id[edge.target_node_id],
            condition_data=edge.condition_data,
            created_at=edge.created_at,
        )

    @classmethod
    def _to_graph_data(cls, workflow: Workflow) -> WorkflowGraphData:
        nodes = sorted(workflow.nodes, key=lambda item: item.id)
        edges = sorted(workflow.edges, key=lambda item: item.id)
        return WorkflowGraphData(
            workflow=cls._to_workflow_data(workflow),
            nodes=[cls._to_node_data(node) for node in nodes],
            edges=[cls._to_edge_data(edge, nodes) for edge in edges],
        )

    @staticmethod
    def _to_run_data(run: WorkflowRun) -> WorkflowRunData:
        snapshot = run.context_snapshot
        context_version = snapshot.get("version") if isinstance(snapshot, dict) else None
        if not isinstance(context_version, int) or context_version < 1:
            raise ConflictError("WorkflowRun 缺少有效 Context 快照")

        node_results: list[WorkflowRunNodeData] = []
        for request in sorted(run.ai_requests, key=lambda item: item.id):
            metadata = request.request_metadata or {}
            node_id = metadata.get("node_id")
            node_key = metadata.get("node_key")
            if not isinstance(node_id, int) or not isinstance(node_key, str):
                raise ConflictError("WorkflowRun 节点记录元数据无效")
            result: WorkflowNodeResult | None = None
            if request.result is not None:
                raw_result = request.result.structured_result
                schema = WORKFLOW_NODE_RESULT_SCHEMAS.get(request.request_type)
                if schema is None or not isinstance(raw_result, dict):
                    raise ConflictError("WorkflowRun 节点结果格式无效")
                try:
                    parsed = schema.model_validate(raw_result)
                except ValidationError as exc:
                    raise ConflictError("WorkflowRun 节点结果格式无效") from exc
                result = cast(WorkflowNodeResult, parsed)
            elif request.status == AIRequestStatus.COMPLETED:
                raise ConflictError("已完成节点缺少结构化结果")

            total_tokens = metadata.get("total_tokens")
            if total_tokens is not None and not isinstance(total_tokens, int):
                raise ConflictError("WorkflowRun Token 元数据无效")
            error = None
            if request.error_code is not None:
                error = WorkflowRunErrorData(
                    code=request.error_code,
                    message=request.error_message or "Workflow 节点执行失败",
                )
            node_results.append(
                WorkflowRunNodeData(
                    request_id=request.id,
                    node_id=node_id,
                    node_key=node_key,
                    node_type=request.request_type,
                    status=request.status,
                    result=result,
                    error=error,
                    prompt_tokens=request.prompt_tokens,
                    completion_tokens=request.completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=request.latency_ms,
                    requested_at=request.requested_at,
                    finished_at=request.finished_at,
                )
            )

        run_error = None
        if run.error_code is not None:
            run_error = WorkflowRunErrorData(
                code=run.error_code,
                message=run.error_message or "WorkflowRun 执行失败",
            )
        return WorkflowRunData(
            id=run.id,
            workflow_id=run.workflow_id,
            status=run.status,
            context_version=context_version,
            error=run_error,
            nodes=node_results,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
        )
