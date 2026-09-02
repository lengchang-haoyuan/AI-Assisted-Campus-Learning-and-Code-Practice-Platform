from secrets import token_hex, token_urlsafe

from pwdlib import PasswordHash
from sqlalchemy import delete

from app.core.database import get_session_factory
from app.models.enums import (
    ProjectDifficulty,
    ProjectStatus,
    WorkflowNodeStatus,
    WorkflowStatus,
)
from app.models.project import Project
from app.models.user import User
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode
from app.repositories.project_context import ProjectContextRepository
from app.services.project_context import (
    NodeContextReadData,
    NodeContextWriteData,
    ProjectContextService,
    ProjectContextUpdateData,
)


def main() -> None:
    session = get_session_factory()()
    user_id: int | None = None
    project_id: int | None = None
    try:
        suffix = token_hex(6)
        user = User(
            username=f"p10_verify_{suffix}",
            email=f"p10_verify_{suffix}@example.invalid",
            password_hash=PasswordHash.recommended().hash(token_urlsafe(32)),
        )
        project = Project(
            owner=user,
            name="P10 verification",
            difficulty=ProjectDifficulty.INTERMEDIATE,
            status=ProjectStatus.IN_PROGRESS,
            language="Python",
            framework="FastAPI",
            frontend="Vue 3",
            backend="FastAPI",
            database="MySQL",
            requirements=[{"title": "ProjectContext verification"}],
            output_requirement="Persisted and reloadable context",
        )
        workflow = Workflow(
            project=project,
            name="P10 verification workflow",
            status=WorkflowStatus.DRAFT,
        )
        tech = WorkflowNode(
            workflow=workflow,
            node_key="tech",
            node_type="tech_stack_analysis",
            name="Tech stack",
            position_x=0,
            position_y=0,
        )
        structure = WorkflowNode(
            workflow=workflow,
            node_key="structure",
            node_type="project_structure",
            name="Project structure",
            position_x=200,
            position_y=0,
        )
        prompt = WorkflowNode(
            workflow=workflow,
            node_key="prompt",
            node_type="prompt",
            name="Prompt",
            position_x=400,
            position_y=0,
        )
        session.add_all([user, project, workflow, tech, structure, prompt])
        session.flush()
        session.add_all(
            [
                WorkflowEdge(
                    workflow_id=workflow.id,
                    source_node_id=tech.id,
                    target_node_id=structure.id,
                ),
                WorkflowEdge(
                    workflow_id=workflow.id,
                    source_node_id=structure.id,
                    target_node_id=prompt.id,
                ),
            ]
        )
        session.commit()
        user_id = user.id
        project_id = project.id

        service = ProjectContextService(ProjectContextRepository(session))
        created = service.create_context(project.id, user.id)
        if created.version != 1 or created.values.language != "Python":
            raise RuntimeError("ProjectContext 创建结果不符合预期")

        updated = service.update_context(
            project.id,
            user.id,
            ProjectContextUpdateData(1, {"language": "Java"}),
        )
        if updated.context.version != 2 or updated.stale_node_ids != [
            structure.id,
            prompt.id,
        ]:
            raise RuntimeError("ProjectContext 下游失效结果不符合预期")

        read_result = service.read_node_context(
            workflow.id,
            structure.id,
            user.id,
            NodeContextReadData(fields=["language", "framework"]),
        )
        if read_result.values["language"] != "Java" or not read_result.is_stale:
            raise RuntimeError("节点读取 ProjectContext 结果不符合预期")

        written = service.write_node_context(
            workflow.id,
            tech.id,
            user.id,
            NodeContextWriteData(2, {"framework": "Spring Boot"}),
        )
        reloaded = service.get_context(project.id, user.id)
        if (
            written.context.version != 3
            or reloaded.values.framework != "Spring Boot"
            or reloaded.source.node_key != "tech"
        ):
            raise RuntimeError("节点写入 ProjectContext 后的持久化结果不符合预期")

        saved_project = ProjectContextRepository(session).get_project(project.id)
        if saved_project is None:
            raise RuntimeError("ProjectContext 验收项目无法重新加载")
        statuses = {
            node.node_key: node.status
            for item in saved_project.workflows
            for node in item.nodes
        }
        if statuses.get("structure") != WorkflowNodeStatus.STALE:
            raise RuntimeError("项目结构节点未持久化为 stale")
        if statuses.get("prompt") != WorkflowNodeStatus.STALE:
            raise RuntimeError("Prompt 节点未持久化为 stale")

        print("ProjectContext MySQL 验收通过：版本 1→2→3，节点读写和 stale 持久化正确。")
    finally:
        session.rollback()
        if project_id is not None:
            session.execute(
                delete(Project)
                .where(Project.id == project_id)
                .execution_options(synchronize_session=False)
            )
        if user_id is not None:
            session.execute(
                delete(User)
                .where(User.id == user_id)
                .execution_options(synchronize_session=False)
            )
        session.commit()
        session.close()


if __name__ == "__main__":
    main()
