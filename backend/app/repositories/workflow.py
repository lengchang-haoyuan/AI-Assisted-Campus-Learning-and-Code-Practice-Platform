from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.project import Project
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode
from app.models.enums import WorkflowNodeStatus, WorkflowStatus


class WorkflowPersistenceConflictError(Exception):
    """工作流写入与数据库约束或当前版本冲突。"""


class WorkflowVersionConflictError(Exception):
    """整图保存使用的版本已经过期。"""


@dataclass(frozen=True, slots=True)
class WorkflowNodeRecord:
    node_key: str
    node_type: str
    name: str
    position_x: float
    position_y: float
    config: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class WorkflowEdgeRecord:
    source_node_key: str
    target_node_key: str
    condition_data: dict[str, Any] | None


class WorkflowRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_by_owner(self, owner_id: int, project_id: int | None = None) -> int:
        statement = (
            select(func.count(Workflow.id))
            .join(Project, Workflow.project_id == Project.id)
            .where(Project.owner_id == owner_id)
        )
        if project_id is not None:
            statement = statement.where(Workflow.project_id == project_id)
        return self._session.scalar(statement) or 0

    def list_by_owner(
        self,
        owner_id: int,
        *,
        offset: int,
        limit: int,
        project_id: int | None = None,
    ) -> list[Workflow]:
        statement = (
            self._workflow_query()
            .join(Project, Workflow.project_id == Project.id)
            .where(Project.owner_id == owner_id)
            .order_by(Workflow.updated_at.desc(), Workflow.id.desc())
            .offset(offset)
            .limit(limit)
        )
        if project_id is not None:
            statement = statement.where(Workflow.project_id == project_id)
        return list(self._session.scalars(statement).unique())

    def get_project(self, project_id: int) -> Project | None:
        return self._session.get(Project, project_id)

    def get_workflow(self, workflow_id: int) -> Workflow | None:
        statement = (
            self._workflow_query()
            .where(Workflow.id == workflow_id)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def create_workflow(self, workflow: Workflow) -> Workflow:
        self._session.add(workflow)
        self._commit_or_raise()
        return self._reload_workflow(workflow.id)

    def update_workflow(self, workflow: Workflow) -> Workflow:
        self._commit_or_raise()
        return self._reload_workflow(workflow.id)

    def delete_workflow(self, workflow: Workflow) -> None:
        self._session.delete(workflow)
        self._commit_or_raise()

    def get_node(self, node_id: int) -> WorkflowNode | None:
        return self._session.get(WorkflowNode, node_id)

    def create_node(
        self, workflow: Workflow, node: WorkflowNode
    ) -> tuple[WorkflowNode, int]:
        self._session.add(node)
        workflow.version += 1
        self._commit_or_raise()
        return self._reload_node(node.id), workflow.version

    def update_node(
        self, workflow: Workflow, node: WorkflowNode
    ) -> tuple[WorkflowNode, int]:
        workflow.version += 1
        self._commit_or_raise()
        return self._reload_node(node.id), workflow.version

    def delete_node(self, workflow: Workflow, node: WorkflowNode) -> int:
        self._session.delete(node)
        workflow.version += 1
        self._commit_or_raise()
        return workflow.version

    def get_edge(self, edge_id: int) -> WorkflowEdge | None:
        return self._session.get(WorkflowEdge, edge_id)

    def create_edge(
        self, workflow: Workflow, edge: WorkflowEdge
    ) -> tuple[WorkflowEdge, int]:
        self._session.add(edge)
        workflow.version += 1
        self._commit_or_raise()
        return self._reload_edge(edge.id), workflow.version

    def update_edge(
        self, workflow: Workflow, edge: WorkflowEdge
    ) -> tuple[WorkflowEdge, int]:
        workflow.version += 1
        self._commit_or_raise()
        return self._reload_edge(edge.id), workflow.version

    def delete_edge(self, workflow: Workflow, edge: WorkflowEdge) -> int:
        self._session.delete(edge)
        workflow.version += 1
        self._commit_or_raise()
        return workflow.version

    def replace_graph(
        self,
        workflow: Workflow,
        *,
        expected_version: int,
        nodes: list[WorkflowNodeRecord],
        edges: list[WorkflowEdgeRecord],
    ) -> Workflow:
        try:
            current_version = self._session.scalar(
                select(Workflow.version)
                .where(Workflow.id == workflow.id)
                .with_for_update()
            )
            if current_version != expected_version:
                self._session.rollback()
                raise WorkflowVersionConflictError
            node_keys = {node.id: node.node_key for node in workflow.nodes}
            old_inputs = {
                node.node_key: {
                    node_keys[edge.source_node_id]
                    for edge in workflow.edges
                    if edge.target_node_id == node.id
                }
                for node in workflow.nodes
            }
            graph_changed = False
            for edge in list(workflow.edges):
                self._session.delete(edge)
            self._session.flush()

            existing_nodes = {node.node_key: node for node in workflow.nodes}
            requested_keys = {node.node_key for node in nodes}
            for node_key, node in existing_nodes.items():
                if node_key not in requested_keys:
                    self._session.delete(node)
            self._session.flush()

            nodes_by_key: dict[str, WorkflowNode] = {}
            for record in nodes:
                node = existing_nodes.get(record.node_key)
                if node is None:
                    graph_changed = True
                    node = WorkflowNode(
                        workflow_id=workflow.id,
                        node_key=record.node_key,
                        node_type=record.node_type,
                        name=record.name,
                    )
                    self._session.add(node)
                elif (
                    node.node_type != record.node_type
                    or node.config != record.config
                    or old_inputs[record.node_key] != {
                        edge.source_node_key for edge in edges
                        if edge.target_node_key == record.node_key
                    }
                ):
                    # 运行结果对应旧配置，继续运行时必须重新生成该节点及其后继。
                    node.status = WorkflowNodeStatus.STALE
                    graph_changed = True
                node.node_type = record.node_type
                node.name = record.name
                node.position_x = Decimal(str(record.position_x))
                node.position_y = Decimal(str(record.position_y))
                node.config = record.config
                nodes_by_key[record.node_key] = node
            self._session.flush()

            for record in edges:
                self._session.add(
                    WorkflowEdge(
                        workflow_id=workflow.id,
                        source_node_id=nodes_by_key[record.source_node_key].id,
                        target_node_id=nodes_by_key[record.target_node_key].id,
                        condition_data=record.condition_data,
                    )
                )
            workflow.version += 1
            if graph_changed and workflow.status != WorkflowStatus.DRAFT:
                workflow.status = WorkflowStatus.STALE
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkflowPersistenceConflictError from exc
        return self._reload_workflow(workflow.id)

    def _reload_workflow(self, workflow_id: int) -> Workflow:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            raise RuntimeError("工作流写入后无法重新加载")
        return workflow

    def _reload_node(self, node_id: int) -> WorkflowNode:
        node = self.get_node(node_id)
        if node is None:
            raise RuntimeError("工作流节点写入后无法重新加载")
        return node

    def _reload_edge(self, edge_id: int) -> WorkflowEdge:
        edge = self.get_edge(edge_id)
        if edge is None:
            raise RuntimeError("工作流边写入后无法重新加载")
        return edge

    @staticmethod
    def _workflow_query():
        return select(Workflow).options(
            joinedload(Workflow.project),
            selectinload(Workflow.nodes),
            selectinload(Workflow.edges),
        )

    def _commit_or_raise(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkflowPersistenceConflictError from exc
