from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.project import Project
from app.models.workflow import Workflow, WorkflowNode


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
            .options(
                selectinload(Project.workflows).selectinload(Workflow.nodes),
                selectinload(Project.workflows).selectinload(Workflow.edges),
            )
            .where(Project.id == project_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

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
