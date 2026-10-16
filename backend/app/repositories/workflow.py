from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.models.project import Project
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode, WorkflowRun
from app.models.enums import WorkflowNodeStatus, WorkflowRunStatus, WorkflowStatus


class WorkflowPersistenceConflictError(Exception):
    """工作流写入与数据库约束或当前版本冲突。"""


class WorkflowVersionConflictError(WorkflowPersistenceConflictError):
    """整图保存使用的版本已经过期。"""


class WorkflowEditConflictError(WorkflowPersistenceConflictError):
    """工作流正在执行，或编辑使用的状态已过期。"""


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

    def lock_for_edit(
        self, workflow: Workflow, *, allow_active_run: bool = False
    ) -> None:
        self._check_edit_boundary(workflow, allow_active_run=allow_active_run)
        # MySQL 的旧一致性快照可能早于等锁过程，必须使用锁定读取刷新整图。
        self._session.scalar(
            select(Workflow)
            .where(Workflow.id == workflow.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        nodes = list(
            self._session.scalars(
                select(WorkflowNode)
                .where(WorkflowNode.workflow_id == workflow.id)
                .order_by(WorkflowNode.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        edges = list(
            self._session.scalars(
                select(WorkflowEdge)
                .where(WorkflowEdge.workflow_id == workflow.id)
                .order_by(WorkflowEdge.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        set_committed_value(workflow, "nodes", nodes)
        set_committed_value(workflow, "edges", edges)

    def _check_edit_boundary(
        self, workflow: Workflow, *, allow_active_run: bool = False
    ) -> None:
        # 与执行路径、手动 Context 写入保持 Project -> Workflow -> Run 的锁序。
        # Repository 也可能收到已修改的 ORM 对象，检查前不能自动 flush。
        with self._session.no_autoflush:
            project_id = self._session.scalar(
                select(Project.id)
                .where(Project.id == workflow.project_id)
                .with_for_update()
            )
            current_version = self._session.scalar(
                select(Workflow.version)
                .where(Workflow.id == workflow.id)
                .with_for_update()
            )
            if project_id is None or current_version is None:
                self._session.rollback()
                raise WorkflowEditConflictError("工作流已被更新，请刷新后重试")
            if current_version != workflow.version:
                self._session.rollback()
                raise WorkflowVersionConflictError
            active_run_id = self._session.scalar(
                select(WorkflowRun.id)
                .where(
                    WorkflowRun.workflow_id == workflow.id,
                    WorkflowRun.status == WorkflowRunStatus.RUNNING,
                )
                .order_by(WorkflowRun.id)
                .limit(1)
                .with_for_update()
            )
            if active_run_id is not None and not allow_active_run:
                self._session.rollback()
                raise WorkflowEditConflictError("运行中的工作流不能修改执行图或删除")

    def update_workflow(self, workflow: Workflow) -> Workflow:
        self._check_edit_boundary(
            workflow,
            allow_active_run=not inspect(workflow).attrs.status.history.has_changes(),
        )
        self._commit_or_raise()
        return self._reload_workflow(workflow.id)

    def delete_workflow(self, workflow: Workflow) -> None:
        self._check_edit_boundary(workflow)
        self._session.delete(workflow)
        self._commit_or_raise()

    def get_node(self, node_id: int) -> WorkflowNode | None:
        return self._session.get(WorkflowNode, node_id)

    def create_node(
        self, workflow: Workflow, node: WorkflowNode
    ) -> tuple[WorkflowNode, int]:
        self._check_edit_boundary(workflow)
        self._session.add(node)
        if workflow.status != WorkflowStatus.DRAFT:
            workflow.status = WorkflowStatus.STALE
        workflow.version += 1
        self._commit_or_raise()
        return self._reload_node(node.id), workflow.version

    def update_node(
        self, workflow: Workflow, node: WorkflowNode
    ) -> tuple[WorkflowNode, int]:
        self._check_edit_boundary(workflow)
        state = inspect(node)
        old_type = (state.attrs.node_type.history.deleted or [node.node_type])[0]
        old_config = (state.attrs.config.history.deleted or [node.config])[0]
        if self._execution_input(old_type, old_config) != self._execution_input(
            node.node_type, node.config
        ):
            self._invalidate_nodes(workflow, {node.id})
        workflow.version += 1
        self._commit_or_raise()
        return self._reload_node(node.id), workflow.version

    def delete_node(self, workflow: Workflow, node: WorkflowNode) -> int:
        self._check_edit_boundary(workflow)
        self._invalidate_nodes(workflow, {
            edge.target_node_id for edge in workflow.edges if edge.source_node_id == node.id
        })
        self._session.delete(node)
        workflow.version += 1
        self._commit_or_raise()
        return workflow.version

    def get_edge(self, edge_id: int) -> WorkflowEdge | None:
        return self._session.get(WorkflowEdge, edge_id)

    def create_edge(
        self, workflow: Workflow, edge: WorkflowEdge
    ) -> tuple[WorkflowEdge, int]:
        self._check_edit_boundary(workflow)
        self._invalidate_nodes(workflow, {edge.target_node_id})
        self._session.add(edge)
        workflow.version += 1
        self._commit_or_raise()
        return self._reload_edge(edge.id), workflow.version

    def update_edge(
        self, workflow: Workflow, edge: WorkflowEdge
    ) -> tuple[WorkflowEdge, int]:
        self._check_edit_boundary(workflow)
        state = inspect(edge)
        changed = any(state.attrs[field].history.has_changes() for field in (
            "source_node_id", "target_node_id", "condition_data"
        ))
        if changed:
            old_target = (state.attrs.target_node_id.history.deleted or [edge.target_node_id])[0]
            self._invalidate_nodes(workflow, {old_target, edge.target_node_id})
        workflow.version += 1
        self._commit_or_raise()
        return self._reload_edge(edge.id), workflow.version

    def delete_edge(self, workflow: Workflow, edge: WorkflowEdge) -> int:
        self._check_edit_boundary(workflow)
        self._invalidate_nodes(workflow, {edge.target_node_id})
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
            self._check_edit_boundary(workflow)
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
                    node_keys[edge.source_node_id]: edge.condition_data
                    for edge in workflow.edges
                    if edge.target_node_id == node.id
                }
                for node in workflow.nodes
            }
            invalid_keys: set[str] = set()
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
                    invalid_keys.add(record.node_key)
                    node = WorkflowNode(
                        workflow_id=workflow.id,
                        node_key=record.node_key,
                        node_type=record.node_type,
                        name=record.name,
                    )
                    self._session.add(node)
                elif (
                    self._execution_input(node.node_type, node.config)
                    != self._execution_input(record.node_type, record.config)
                    or old_inputs[record.node_key] != {
                        edge.source_node_key: edge.condition_data for edge in edges
                        if edge.target_node_key == record.node_key
                    }
                ):
                    # 运行结果对应旧配置，继续运行时必须重新生成该节点及其后继。
                    invalid_keys.add(record.node_key)
                node.node_type = record.node_type
                node.name = record.name
                node.position_x = Decimal(str(record.position_x))
                node.position_y = Decimal(str(record.position_y))
                node.config = record.config
                nodes_by_key[record.node_key] = node
            self._session.flush()

            saved_edges = []
            for record in edges:
                edge = WorkflowEdge(
                        workflow_id=workflow.id,
                        source_node_id=nodes_by_key[record.source_node_key].id,
                        target_node_id=nodes_by_key[record.target_node_key].id,
                        condition_data=record.condition_data,
                    )
                self._session.add(edge)
                saved_edges.append(edge)
            self._invalidate_nodes(
                workflow, {nodes_by_key[key].id for key in invalid_keys},
                nodes=list(nodes_by_key.values()), edges=saved_edges,
            )
            workflow.version += 1
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkflowPersistenceConflictError from exc
        return self._reload_workflow(workflow.id)

    @staticmethod
    def _execution_input(node_type: str, config: dict[str, Any] | None) -> tuple:
        config = config or {}
        fields = ["instruction", "expected_output"]
        if node_type in {"exercise_hint", "code_explanation", "answer_review"}:
            fields.extend(("problem", "student_code"))
        # 权限未声明与显式空集合具有不同含义，不能用 get() 合并这两种配置。
        policies = tuple((key in config, config.get(key)) for key in (
            "context_reads", "context_writes"
        ))
        return node_type, tuple(config.get(key) for key in fields), policies

    @staticmethod
    def _invalidate_nodes(
        workflow: Workflow, roots: set[int], *,
        nodes: list[WorkflowNode] | None = None, edges: list[WorkflowEdge] | None = None,
    ) -> None:
        node_list = workflow.nodes if nodes is None else nodes
        edge_list = workflow.edges if edges is None else edges
        stale = set(roots)
        pending = list(roots)
        adjacency: dict[int, list[int]] = {}
        for edge in edge_list:
            adjacency.setdefault(edge.source_node_id, []).append(edge.target_node_id)
        while pending:
            for target in adjacency.get(pending.pop(), []):
                if target not in stale:
                    stale.add(target)
                    pending.append(target)
        for node in node_list:
            if node.id in stale:
                node.status = WorkflowNodeStatus.STALE
        if stale and workflow.status != WorkflowStatus.DRAFT:
            workflow.status = WorkflowStatus.STALE

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
