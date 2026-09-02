import asyncio
from datetime import UTC, datetime, timedelta
import json
from secrets import token_hex, token_urlsafe

from pwdlib import PasswordHash
from sqlalchemy import delete, select

from app.ai.client import AIClient
from app.ai.provider import (
    AICompletionRequest,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.context.context_manager import ContextManager
from app.context.context_schema import ContextSource, ContextSourceType
from app.context.project_context import ContextBuilder, ProjectContext, ProjectContextSeed
from app.core.database import get_session_factory
from app.models.ai import AIRequest
from app.models.enums import (
    AIRequestStatus,
    ProjectDifficulty,
    ProjectStatus,
    WorkflowNodeStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from app.models.project import Project
from app.models.user import User
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode, WorkflowRun
from app.repositories.workflow import WorkflowRepository
from app.repositories.workflow_execution import (
    WorkflowActiveRunError,
    WorkflowExecutionRepository,
)
from app.services.workflow import (
    WorkflowRunRequestData,
    WorkflowService,
)
from app.workflow.agents import (
    ArchitectureDesignWorkflowAgent,
    RequirementsAnalysisWorkflowAgent,
    TechStackAnalysisWorkflowAgent,
)
from app.workflow.engine import WorkflowEngine, WorkflowEngineLimits, WorkflowRunMode
from app.workflow.registry import WorkflowAgentRegistry


def requirements_result() -> str:
    return json.dumps(
        {
            "result_type": "requirements_analysis",
            "summary": "需求已整理为可验收结构。",
            "requirements": [
                {
                    "title": "Workflow 持久化",
                    "description": "节点结果和上下文必须写入 MySQL。",
                    "acceptance_criteria": ["刷新后仍能查询本次运行结果"],
                }
            ],
            "features": ["工作流运行", "结果查询"],
            "constraints": ["所有权必须由服务端验证"],
        },
        ensure_ascii=False,
    )


def tech_stack_result(language: str) -> str:
    backend = "Spring Boot" if language == "Java" else "FastAPI"
    return json.dumps(
        {
            "result_type": "tech_stack_analysis",
            "summary": "技术栈已确定。",
            "language": {"value": language, "reason": "符合本次验收场景。"},
            "framework": {"value": backend, "reason": "与语言一致。"},
            "frontend": {"value": "Vue 3", "reason": "沿用现有前端。"},
            "backend": {"value": backend, "reason": "沿用分层架构。"},
            "database": {"value": "MySQL", "reason": "复用既有持久化。"},
        },
        ensure_ascii=False,
    )


def architecture_result(backend: str) -> str:
    return json.dumps(
        {
            "result_type": "architecture_design",
            "summary": "架构已按当前技术栈重新生成。",
            "style": "分层模块化单体",
            "components": [
                {
                    "name": "API",
                    "responsibility": "处理认证、输入和响应映射。",
                    "technology": backend,
                    "dependencies": ["Service"],
                },
                {
                    "name": "Service",
                    "responsibility": "编排工作流和持久化边界。",
                    "technology": backend,
                    "dependencies": ["Repository", "MySQL"],
                },
            ],
            "data_flows": [
                {"source": "Vue 3", "target": "API", "data": "受认证 JSON"}
            ],
            "decisions": [
                {
                    "title": "事务边界",
                    "choice": "模型调用与数据库事务分离",
                    "reason": "避免长事务占用数据库连接。",
                }
            ],
        },
        ensure_ascii=False,
    )


class VerificationProvider(AIProvider):
    def __init__(self) -> None:
        self._results = [
            requirements_result(),
            tech_stack_result("Python"),
            architecture_result("FastAPI"),
            tech_stack_result("Java"),
            architecture_result("Spring Boot"),
        ]

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request: AICompletionRequest) -> AIProviderResult:
        return AIProviderResult(
            provider=self.name,
            model=request.model,
            content=self._results.pop(0),
            finish_reason="stop",
            usage=AIUsage(
                prompt_tokens=100,
                completion_tokens=80,
                total_tokens=180,
            ),
        )


def build_service(session) -> WorkflowService:
    provider = VerificationProvider()
    client = AIClient(
        provider,
        total_timeout_seconds=5,
        max_retries=0,
        retry_base_delay_seconds=0.1,
        max_retry_delay_seconds=1,
    )
    registry = WorkflowAgentRegistry()
    options = {"model": "fake-model", "temperature": 0.1}
    registry.register(
        "requirements_analysis",
        lambda max_tokens: RequirementsAnalysisWorkflowAgent(
            client, max_tokens=max_tokens, **options
        ),
    )
    registry.register(
        "tech_stack_analysis",
        lambda max_tokens: TechStackAnalysisWorkflowAgent(
            client, max_tokens=max_tokens, **options
        ),
    )
    registry.register(
        "architecture_design",
        lambda max_tokens: ArchitectureDesignWorkflowAgent(
            client, max_tokens=max_tokens, **options
        ),
    )
    execution_repository = WorkflowExecutionRepository(session)
    engine = WorkflowEngine(
        execution_repository,
        registry,
        ContextManager(),
        WorkflowEngineLimits(
            max_nodes=12,
            max_rounds=12,
            max_node_tokens=1000,
            max_completion_tokens=5000,
            total_timeout_seconds=10,
            recovery_timeout_seconds=20,
            max_concurrency=1,
        ),
    )
    return WorkflowService(
        WorkflowRepository(session),
        execution_repository,
        engine,
    )


async def verify_runs(
    service: WorkflowService,
    session,
    user: User,
    project: Project,
    workflow: Workflow,
    tech_node: WorkflowNode,
    architecture_node: WorkflowNode,
) -> None:
    first = await service.run_workflow(
        workflow.id,
        user.id,
        WorkflowRunRequestData(workflow.version, WorkflowRunMode.INCOMPLETE),
    )
    if first.status != WorkflowRunStatus.COMPLETED or len(first.nodes) != 3:
        raise RuntimeError("三节点 Workflow 首次运行结果不符合预期")
    if any(node.status != AIRequestStatus.COMPLETED for node in first.nodes):
        raise RuntimeError("三节点 Workflow 存在未完成的 AIRequest")

    session.expire_all()
    persisted_project = session.get(Project, project.id)
    persisted_architecture = session.get(WorkflowNode, architecture_node.id)
    if persisted_project is None or persisted_architecture is None:
        raise RuntimeError("Workflow 首次运行结果无法从 MySQL 重新加载")
    context = ProjectContext.from_storage(persisted_project.context_data)
    if (
        context.values.architecture is None
        or persisted_architecture.output_data is None
        or persisted_architecture.status != WorkflowNodeStatus.SUCCESS
    ):
        raise RuntimeError("架构结果或 ProjectContext 未正确持久化")

    persisted_tech = session.get(WorkflowNode, tech_node.id)
    if persisted_tech is None:
        raise RuntimeError("技术栈节点不存在")
    persisted_tech.status = WorkflowNodeStatus.STALE
    session.commit()

    second = await service.run_workflow(
        workflow.id,
        user.id,
        WorkflowRunRequestData(workflow.version, WorkflowRunMode.INCOMPLETE),
    )
    if second.status != WorkflowRunStatus.COMPLETED or len(second.nodes) != 2:
        raise RuntimeError("受影响节点重新生成结果不符合预期")

    session.expire_all()
    persisted_project = session.get(Project, project.id)
    persisted_tech = session.get(WorkflowNode, tech_node.id)
    persisted_architecture = session.get(WorkflowNode, architecture_node.id)
    if (
        persisted_project is None
        or persisted_tech is None
        or persisted_architecture is None
    ):
        raise RuntimeError("重新生成后的数据无法从 MySQL 加载")
    updated_context = ProjectContext.from_storage(persisted_project.context_data)
    if updated_context.values.language != "Java":
        raise RuntimeError("技术栈变化未写回 ProjectContext")
    if persisted_project.language != "Java" or persisted_project.backend != "Spring Boot":
        raise RuntimeError("技术栈变化未同步 Project 核心字段")
    if persisted_tech.status != WorkflowNodeStatus.SUCCESS:
        raise RuntimeError("技术栈节点重新生成后未恢复 success")
    if persisted_architecture.status != WorkflowNodeStatus.SUCCESS:
        raise RuntimeError("下游架构节点重新生成后未恢复 success")

    listed = service.list_runs(workflow.id, user.id, page=1, page_size=10)
    queried = service.get_run(workflow.id, second.id, user.id)
    if listed.total != 2 or queried.id != second.id or len(queried.nodes) != 2:
        raise RuntimeError("WorkflowRun 列表或详情查询结果不符合预期")


def verify_active_run_recovery(
    session,
    user: User,
    project: Project,
    workflow: Workflow,
    architecture_node: WorkflowNode,
) -> None:
    repository = WorkflowExecutionRepository(session)
    session.expire_all()
    persisted_project = session.get(Project, project.id)
    persisted_workflow = session.get(Workflow, workflow.id)
    persisted_node = session.get(WorkflowNode, architecture_node.id)
    if persisted_project is None or persisted_workflow is None or persisted_node is None:
        raise RuntimeError("恢复验收所需数据不存在")
    now = datetime.now(UTC)
    orphaned_run = WorkflowRun(
        workflow_id=persisted_workflow.id,
        started_by_id=user.id,
        status=WorkflowRunStatus.RUNNING,
        context_snapshot=persisted_project.context_data,
        started_at=now,
    )
    persisted_node.status = WorkflowNodeStatus.RUNNING
    persisted_workflow.status = WorkflowStatus.RUNNING
    session.add(orphaned_run)
    session.flush()
    orphaned_request = AIRequest(
        user_id=user.id,
        project_id=persisted_project.id,
        workflow_run_id=orphaned_run.id,
        provider="fake",
        model="fake-model",
        request_type="architecture_design",
        status=AIRequestStatus.RUNNING,
        input_hash="0" * 64,
        input_summary="architecture_design recovery verification",
        request_metadata={
            "context_version": 5,
            "input_bytes": 0,
            "agent_rounds": 1,
            "node_id": persisted_node.id,
            "node_key": persisted_node.node_key,
        },
    )
    session.add(orphaned_request)
    session.commit()

    try:
        repository.start_run(
            persisted_workflow.id,
            user.id,
            expected_version=persisted_workflow.version,
            context_snapshot=persisted_project.context_data,
            stale_before=now - timedelta(seconds=20),
        )
    except WorkflowActiveRunError:
        pass
    else:
        raise RuntimeError("未过期的活跃 WorkflowRun 必须拒绝重复运行")

    recovered_run = session.get(WorkflowRun, orphaned_run.id)
    if recovered_run is None:
        raise RuntimeError("待恢复 WorkflowRun 不存在")
    recovered_run.started_at = now - timedelta(seconds=30)
    session.commit()
    replacement = repository.start_run(
        persisted_workflow.id,
        user.id,
        expected_version=persisted_workflow.version,
        context_snapshot=persisted_project.context_data,
        stale_before=now - timedelta(seconds=20),
    )

    session.expire_all()
    recovered_run = session.get(WorkflowRun, orphaned_run.id)
    recovered_request = session.get(AIRequest, orphaned_request.id)
    recovered_node = session.get(WorkflowNode, persisted_node.id)
    if recovered_run is None or recovered_request is None or recovered_node is None:
        raise RuntimeError("WorkflowRun 恢复状态无法重新加载")
    if (
        recovered_run.status != WorkflowRunStatus.FAILED
        or recovered_run.error_code != "recovered_timeout"
        or recovered_request.status != AIRequestStatus.FAILED
        or recovered_node.status != WorkflowNodeStatus.STALE
    ):
        raise RuntimeError("过期 WorkflowRun、AIRequest 或节点未正确恢复")
    repository.fail_run(
        replacement.id,
        node_id=None,
        request_id=None,
        error_code="verification_cleanup",
        error_message="验收脚本终止替代运行",
    )


def main() -> None:
    session = get_session_factory()()
    user_id: int | None = None
    project_id: int | None = None
    try:
        suffix = token_hex(6)
        user = User(
            username=f"p13_verify_{suffix}",
            email=f"p13_verify_{suffix}@example.invalid",
            password_hash=PasswordHash.recommended().hash(token_urlsafe(32)),
        )
        project = Project(
            owner=user,
            name="P13 verification",
            difficulty=ProjectDifficulty.INTERMEDIATE,
            status=ProjectStatus.IN_PROGRESS,
            language="Python",
            framework="FastAPI",
            frontend="Vue 3",
            backend="FastAPI",
            database="MySQL",
            requirements=[{"title": "Workflow execution verification"}],
            output_requirement="Persisted workflow results",
        )
        workflow = Workflow(
            project=project,
            name="P13 verification workflow",
            status=WorkflowStatus.READY,
        )
        requirements_node = WorkflowNode(
            workflow=workflow,
            node_key="requirements",
            node_type="requirements_analysis",
            name="需求分析",
            position_x=0,
            position_y=0,
        )
        tech_node = WorkflowNode(
            workflow=workflow,
            node_key="tech-stack",
            node_type="tech_stack_analysis",
            name="技术栈分析",
            position_x=240,
            position_y=0,
        )
        architecture_node = WorkflowNode(
            workflow=workflow,
            node_key="architecture",
            node_type="architecture_design",
            name="架构设计",
            position_x=480,
            position_y=0,
        )
        session.add_all(
            [
                user,
                project,
                workflow,
                requirements_node,
                tech_node,
                architecture_node,
            ]
        )
        session.flush()
        user_id = user.id
        project_id = project.id
        project.context_data = ContextBuilder().build(
            ProjectContextSeed(
                project_name=project.name,
                language=project.language,
                framework=project.framework,
                frontend=project.frontend,
                backend=project.backend,
                database=project.database,
                difficulty=project.difficulty,
                requirements=project.requirements,
                output_requirement=project.output_requirement,
            ),
            source=ContextSource(type=ContextSourceType.PROJECT, id=project.id),
        ).to_storage()
        session.add_all(
            [
                WorkflowEdge(
                    workflow_id=workflow.id,
                    source_node_id=requirements_node.id,
                    target_node_id=tech_node.id,
                ),
                WorkflowEdge(
                    workflow_id=workflow.id,
                    source_node_id=tech_node.id,
                    target_node_id=architecture_node.id,
                ),
            ]
        )
        session.commit()

        asyncio.run(
            verify_runs(
                build_service(session),
                session,
                user,
                project,
                workflow,
                tech_node,
                architecture_node,
            )
        )

        verify_active_run_recovery(
            session,
            user,
            project,
            workflow,
            architecture_node,
        )

        requests = list(
            session.scalars(
                select(AIRequest)
                .where(AIRequest.user_id == user.id)
                .order_by(AIRequest.id)
            )
        )
        completed_requests = [
            item for item in requests if item.status == AIRequestStatus.COMPLETED
        ]
        recovered_requests = [
            item
            for item in requests
            if item.status == AIRequestStatus.FAILED
            and item.error_code == "recovered_timeout"
        ]
        if (
            len(completed_requests) != 5
            or len(recovered_requests) != 1
            or any(len(item.input_hash) != 64 for item in requests)
        ):
            raise RuntimeError("Workflow AIRequest 数量或输入哈希不符合预期")
        print(
            "P13 Workflow MySQL 验收通过：3 节点运行、5 条节点结果、"
            "技术栈变更、下游重新生成、重复拒绝和过期恢复均正确。"
        )
    finally:
        session.rollback()
        if user_id is not None:
            session.execute(
                delete(AIRequest)
                .where(AIRequest.user_id == user_id)
                .execution_options(synchronize_session=False)
            )
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
