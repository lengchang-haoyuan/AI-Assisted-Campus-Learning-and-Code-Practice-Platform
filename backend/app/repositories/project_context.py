from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.models.project import Project
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge


class ProjectContextPersistenceError(Exception):
    """ProjectContext 与当前数据库状态冲突。"""


class ProjectContextRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_project(
        self, project_id: int, *, for_update: bool = False
    ) -> Project | None:
        statement = (
            select(Project)
            .where(Project.id == project_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        else:
            statement = statement.options(
                selectinload(Project.workflows).selectinload(Workflow.nodes),
                selectinload(Project.workflows).selectinload(Workflow.edges),
            )
        project = self._session.scalar(statement)
        if project is not None and for_update:
            self.lock_workflow_graphs(project)
        return project

    def lock_workflow_graphs(self, project: Project) -> list[Workflow]:
        # 调用方已持有 Project 锁；使用当前读取刷新所有图，避开旧一致性快照。
        with self._session.no_autoflush:
            workflows = list(self._session.scalars(
                select(Workflow).where(Workflow.project_id == project.id)
                .order_by(Workflow.id).with_for_update()
                .execution_options(populate_existing=True)
            ))
            ids = [workflow.id for workflow in workflows]
            nodes = list(self._session.scalars(
                select(WorkflowNode).where(WorkflowNode.workflow_id.in_(ids))
                .order_by(WorkflowNode.id).with_for_update()
                .execution_options(populate_existing=True)
            ))
            edges = list(self._session.scalars(
                select(WorkflowEdge).where(WorkflowEdge.workflow_id.in_(ids))
                .order_by(WorkflowEdge.id).with_for_update()
                .execution_options(populate_existing=True)
            ))
            for workflow in workflows:
                set_committed_value(workflow, "nodes", [n for n in nodes if n.workflow_id == workflow.id])
                set_committed_value(workflow, "edges", [e for e in edges if e.workflow_id == workflow.id])
            set_committed_value(project, "workflows", workflows)
            return workflows

    def get_node(self, workflow_id: int, node_id: int) -> WorkflowNode | None:
        statement = (
            select(WorkflowNode)
            .join(Workflow, WorkflowNode.workflow_id == Workflow.id)
            .options(
                joinedload(WorkflowNode.workflow).joinedload(Workflow.project)
            )
            .where(
                WorkflowNode.id == node_id,
                WorkflowNode.workflow_id == workflow_id,
            )
        )
        return self._session.scalar(statement)

    def save(self, project: Project) -> Project:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ProjectContextPersistenceError from exc
        saved = self.get_project(project.id)
        if saved is None:
            raise RuntimeError("ProjectContext 保存后无法重新加载项目")
        return saved
