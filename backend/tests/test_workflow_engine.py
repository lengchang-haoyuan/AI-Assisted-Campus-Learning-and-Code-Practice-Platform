import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import json
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.ai.client import AIClient
from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.api.deps import get_current_user, get_workflow_execution_service
from app.context.context_manager import ContextManager
from app.context.context_schema import ContextSource, ContextSourceType
from app.context.project_context import ContextBuilder, ProjectContextSeed
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.main import create_app
from app.models.ai import AIRequest, AIResult
from app.models.enums import (
    AIRequestStatus,
    ProjectDifficulty,
    ProjectStatus,
    WorkflowNodeStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from app.models.project import Project
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode, WorkflowRun
from app.repositories.workflow import WorkflowRepository
from app.services.auth import UserIdentity
from app.services.workflow import (
    WorkflowRunData,
    WorkflowRunPage,
    WorkflowService,
)
from app.workflow.agents import (
    ArchitectureDesignWorkflowAgent,
    RequirementsAnalysisWorkflowAgent,
    TechStackAnalysisWorkflowAgent,
)
from app.workflow.engine import (
    WorkflowEngine,
    WorkflowEngineLimits,
    WorkflowRunMode,
)
from app.workflow.registry import WorkflowAgentRegistry
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def requirements_json() -> str:
    return json.dumps(
        {
            "result_type": "requirements_analysis",
            "summary": "需求已经规范化。",
            "requirements": [
                {
                    "title": "项目隔离",
                    "description": "用户只能访问自己的项目。",
                    "acceptance_criteria": ["跨用户访问被拒绝"],
                }
            ],
            "features": ["项目管理", "学习记录"],
            "constraints": ["所有 API 使用 JWT"],
        },
        ensure_ascii=False,
    )


def tech_stack_json(*, language: str = "Python") -> str:
    return json.dumps(
        {
            "result_type": "tech_stack_analysis",
            "summary": "技术栈已经确定。",
            "language": {"value": language, "reason": "符合项目约束。"},
            "framework": {
                "value": "Spring Boot" if language == "Java" else "FastAPI",
                "reason": "提供成熟的后端边界。",
            },
            "frontend": {"value": "Vue 3", "reason": "沿用现有前端。"},
            "backend": {
                "value": "Spring Boot" if language == "Java" else "FastAPI",
                "reason": "与语言和项目结构一致。",
            },
            "database": {"value": "MySQL", "reason": "沿用现有数据库。"},
        },
        ensure_ascii=False,
    )


def architecture_json(*, backend: str = "FastAPI") -> str:
    return json.dumps(
        {
            "result_type": "architecture_design",
            "summary": "架构边界已经确定。",
            "style": "分层模块化单体",
            "components": [
                {
                    "name": "Web API",
                    "responsibility": "处理认证、输入和响应映射。",
                    "technology": backend,
                    "dependencies": ["Application Service"],
                },
                {
                    "name": "Application Service",
                    "responsibility": "编排业务规则和持久化。",
                    "technology": backend,
                    "dependencies": ["MySQL"],
                },
            ],
            "data_flows": [
                {
                    "source": "Vue 3",
                    "target": "Web API",
                    "data": "受认证 JSON 请求",
                }
            ],
            "decisions": [
                {
                    "title": "数据库隔离",
                    "choice": "Repository 封装查询",
                    "reason": "避免 Router 直接访问 ORM。",
                }
            ],
        },
        ensure_ascii=False,
    )


class QueueProvider(AIProvider):
    def __init__(
        self,
        outcomes: list[
            str | tuple[str, int] | AIClientError
        ],
        *,
        delay_seconds: float = 0,
    ) -> None:
        self.outcomes = outcomes.copy()
        self.delay_seconds = delay_seconds
        self.requests: list[AICompletionRequest] = []

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request_data: AICompletionRequest) -> AIProviderResult:
        self.requests.append(request_data)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, AIClientError):
            raise outcome
        if isinstance(outcome, tuple):
            content, completion_tokens = outcome
        else:
            content, completion_tokens = outcome, 100
        return AIProviderResult(
            provider=self.name,
            model=request_data.model,
            content=content,
            finish_reason="stop",
            usage=AIUsage(
                prompt_tokens=100,
                completion_tokens=completion_tokens,
                total_tokens=100 + completion_tokens,
            ),
        )


def make_context():
    return ContextBuilder().build(
        ProjectContextSeed(
            project_name="ScholarHub",
            language="Python",
            framework="FastAPI",
            frontend="Vue 3",
            backend="FastAPI",
            database="MySQL",
            difficulty=ProjectDifficulty.INTERMEDIATE,
            requirements=[{"title": "校园学习平台"}],
            output_requirement="返回结构化、可验证的结果",
        ),
        source=ContextSource(type=ContextSourceType.PROJECT, id=7),
        now=NOW,
    )


def make_workflow(*, owner_id: int = 1) -> Workflow:
    project = Project(
        id=7,
        owner_id=owner_id,
        name="ScholarHub",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        status=ProjectStatus.IN_PROGRESS,
        language="Python",
        framework="FastAPI",
        frontend="Vue 3",
        backend="FastAPI",
        database="MySQL",
        requirements=[{"title": "校园学习平台"}],
        output_requirement="返回结构化、可验证的结果",
        context_data=make_context().to_storage(),
        created_at=NOW,
        updated_at=NOW,
    )
    workflow = Workflow(
        id=11,
        project_id=7,
        project=project,
        name="三节点演示",
        status=WorkflowStatus.READY,
        version=4,
        created_at=NOW,
        updated_at=NOW,
    )
    workflow.nodes = [
        WorkflowNode(
            id=21,
            workflow_id=11,
            node_key="requirements",
            node_type="requirements_analysis",
            name="需求分析",
            position_x=Decimal("0"),
            position_y=Decimal("0"),
            config={"instruction": "整理核心需求。"},
            status=WorkflowNodeStatus.PENDING,
            context_version=1,
            created_at=NOW,
            updated_at=NOW,
        ),
        WorkflowNode(
            id=22,
            workflow_id=11,
            node_key="tech-stack",
            node_type="tech_stack_analysis",
            name="技术栈分析",
            position_x=Decimal("260"),
            position_y=Decimal("0"),
            config={"instruction": "选择兼容技术栈。"},
            status=WorkflowNodeStatus.PENDING,
            context_version=1,
            created_at=NOW,
            updated_at=NOW,
        ),
        WorkflowNode(
            id=23,
            workflow_id=11,
            node_key="architecture",
            node_type="architecture_design",
            name="架构设计",
            position_x=Decimal("520"),
            position_y=Decimal("0"),
            config={"instruction": "设计模块和数据流。"},
            status=WorkflowNodeStatus.PENDING,
            context_version=1,
            created_at=NOW,
            updated_at=NOW,
        ),
    ]
    workflow.edges = [
        WorkflowEdge(
            id=31,
            workflow_id=11,
            source_node_id=21,
            target_node_id=22,
            condition_data=None,
            created_at=NOW,
        ),
        WorkflowEdge(
            id=32,
            workflow_id=11,
            source_node_id=22,
            target_node_id=23,
            condition_data=None,
            created_at=NOW,
        ),
    ]
    return workflow


class FakeExecutionRepository:
    def __init__(self, workflow: Workflow) -> None:
        self.workflow = workflow
        self.runs: list[WorkflowRun] = []
        self.requests: dict[int, AIRequest] = {}
        self.stale_events: list[frozenset[int]] = []
        self._next_run_id = 101
        self._next_request_id = 201

    def get_workflow(self, workflow_id: int) -> Workflow | None:
        return self.workflow if workflow_id == self.workflow.id else None

    def start_run(
        self,
        workflow_id: int,
        user_id: int,
        *,
        expected_version: int,
        context_snapshot: dict,
        stale_before: datetime,
    ) -> WorkflowRun:
        del stale_before
        if expected_version != self.workflow.version:
            raise AssertionError("unexpected version")
        run = WorkflowRun(
            id=self._next_run_id,
            workflow_id=workflow_id,
            workflow=self.workflow,
            started_by_id=user_id,
            status=WorkflowRunStatus.RUNNING,
            context_snapshot=context_snapshot,
            started_at=NOW,
            created_at=NOW,
        )
        run.ai_requests = []
        self._next_run_id += 1
        self.workflow.status = WorkflowStatus.RUNNING
        self.runs.append(run)
        return run

    def start_node(self, run_id: int, node_id: int, **values) -> AIRequest:
        node = next(item for item in self.workflow.nodes if item.id == node_id)
        node.status = WorkflowNodeStatus.RUNNING
        request_data = AIRequest(
            id=self._next_request_id,
            user_id=values["user_id"],
            project_id=values["project_id"],
            workflow_run_id=run_id,
            provider=values["provider"],
            model=values["model"],
            request_type=values["node_type"],
            status=AIRequestStatus.RUNNING,
            input_hash=values["input_hash"],
            input_summary=f"{values['node_type']} safe summary",
            request_metadata={
                "context_version": values["context_version"],
                "input_bytes": values["input_bytes"],
                "agent_rounds": 1,
                "node_id": node_id,
                "node_key": values["node_key"],
            },
            requested_at=NOW,
        )
        request_data.result = None
        self._next_request_id += 1
        self.requests[request_data.id] = request_data
        run = next(item for item in self.runs if item.id == run_id)
        run.ai_requests.append(request_data)
        return request_data

    def complete_node(
        self,
        run_id: int,
        node_id: int,
        request_id: int,
        **values,
    ) -> None:
        node = next(item for item in self.workflow.nodes if item.id == node_id)
        for stale_id in values["stale_node_ids"]:
            if stale_id != node_id:
                target = next(
                    item for item in self.workflow.nodes if item.id == stale_id
                )
                target.status = WorkflowNodeStatus.STALE
        self.stale_events.append(values["stale_node_ids"])
        context = values["context"]
        self.workflow.project.context_data = context.to_storage()
        context_values = context.values.model_dump(mode="python")
        for field_name in values["changed_fields"]:
            project_name = {
                "project_name": "name",
                "language": "language",
                "framework": "framework",
                "frontend": "frontend",
                "backend": "backend",
                "database": "database",
                "difficulty": "difficulty",
                "requirements": "requirements",
                "output_requirement": "output_requirement",
            }.get(field_name)
            if project_name is not None:
                setattr(self.workflow.project, project_name, context_values[field_name])
        node.status = WorkflowNodeStatus.SUCCESS
        node.context_version = context.version
        node.output_data = {
            "run_id": run_id,
            "request_id": request_id,
            "context_version": context.version,
            "changed_fields": sorted(values["changed_fields"]),
            "result": values["structured_result"],
        }
        request_data = self.requests[request_id]
        request_data.status = AIRequestStatus.COMPLETED
        request_data.prompt_tokens = values["prompt_tokens"]
        request_data.completion_tokens = values["completion_tokens"]
        request_data.latency_ms = values["latency_ms"]
        request_data.finished_at = NOW
        request_data.request_metadata = {
            **request_data.request_metadata,
            "finish_reason": values["finish_reason"],
            "total_tokens": values["total_tokens"],
        }
        request_data.result = AIResult(
            id=request_id + 1000,
            request_id=request_id,
            result_type=values["result_type"],
            structured_result=values["structured_result"],
            text_summary=values["text_summary"],
            content_hash=values["content_hash"],
            created_at=NOW,
        )

    def finish_run(self, run_id: int) -> WorkflowRun:
        run = next(item for item in self.runs if item.id == run_id)
        run.status = WorkflowRunStatus.COMPLETED
        run.finished_at = NOW
        self.workflow.status = (
            WorkflowStatus.COMPLETED
            if all(
                node.status == WorkflowNodeStatus.SUCCESS
                for node in self.workflow.nodes
            )
            else WorkflowStatus.STALE
        )
        return run

    def fail_run(
        self,
        run_id: int,
        *,
        node_id: int | None,
        request_id: int | None,
        error_code: str,
        error_message: str,
        cancelled: bool = False,
    ) -> WorkflowRun:
        run = next(item for item in self.runs if item.id == run_id)
        run.status = (
            WorkflowRunStatus.CANCELLED if cancelled else WorkflowRunStatus.FAILED
        )
        run.error_code = error_code
        run.error_message = error_message
        run.finished_at = NOW
        if node_id is not None:
            node = next(item for item in self.workflow.nodes if item.id == node_id)
            node.status = (
                WorkflowNodeStatus.STALE
                if cancelled
                else WorkflowNodeStatus.FAILED
            )
        if request_id is not None:
            request_data = self.requests[request_id]
            request_data.status = AIRequestStatus.FAILED
            request_data.error_code = error_code
            request_data.error_message = error_message
            request_data.finished_at = NOW
        self.workflow.status = (
            WorkflowStatus.STALE if cancelled else WorkflowStatus.FAILED
        )
        return run

    def count_runs(self, workflow_id: int) -> int:
        return len([item for item in self.runs if item.workflow_id == workflow_id])

    def list_runs(self, workflow_id: int, *, offset: int, limit: int):
        items = [item for item in reversed(self.runs) if item.workflow_id == workflow_id]
        return items[offset : offset + limit]

    def get_run(self, workflow_id: int, run_id: int):
        return next(
            (
                item
                for item in self.runs
                if item.workflow_id == workflow_id and item.id == run_id
            ),
            None,
        )


def make_registry(provider: AIProvider, *, client_timeout: float = 1) -> WorkflowAgentRegistry:
    client = AIClient(
        provider,
        total_timeout_seconds=client_timeout,
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
    return registry


def make_engine(
    repository: FakeExecutionRepository,
    provider: AIProvider,
    *,
    total_timeout: float = 1,
    max_completion_tokens: int = 4000,
) -> WorkflowEngine:
    return WorkflowEngine(
        repository,
        make_registry(provider),
        ContextManager(),
        WorkflowEngineLimits(
            max_nodes=12,
            max_rounds=12,
            max_node_tokens=1200,
            max_completion_tokens=max_completion_tokens,
            total_timeout_seconds=total_timeout,
            recovery_timeout_seconds=2,
            max_concurrency=1,
        ),
    )


class WorkflowEngineTests(unittest.TestCase):
    def test_three_node_workflow_persists_results_and_context(self) -> None:
        workflow = make_workflow()
        repository = FakeExecutionRepository(workflow)
        provider = QueueProvider(
            [requirements_json(), tech_stack_json(), architecture_json()]
        )

        run = asyncio.run(
            make_engine(repository, provider).run(
                workflow.id,
                1,
                expected_version=workflow.version,
                mode=WorkflowRunMode.INCOMPLETE,
            )
        )

        self.assertEqual(run.status, WorkflowRunStatus.COMPLETED)
        self.assertEqual(workflow.status, WorkflowStatus.COMPLETED)
        self.assertTrue(
            all(node.status == WorkflowNodeStatus.SUCCESS for node in workflow.nodes)
        )
        self.assertEqual(len(run.ai_requests), 3)
        self.assertTrue(
            all(item.status == AIRequestStatus.COMPLETED for item in run.ai_requests)
        )
        self.assertTrue(all(item.result is not None for item in run.ai_requests))
        context = workflow.project.context_data
        self.assertEqual(context["version"], 3)
        self.assertEqual(context["values"]["features"], ["项目管理", "学习记录"])
        self.assertEqual(
            context["values"]["architecture"]["style"], "分层模块化单体"
        )
        self.assertEqual(len(provider.requests), 3)
        self.assertTrue(
            all(request_data.response_format.value == "json_object" for request_data in provider.requests)
        )
        self.assertNotIn("整理核心需求", run.ai_requests[0].input_summary or "")

    def test_tech_change_marks_downstream_stale_and_regenerates(self) -> None:
        workflow = make_workflow()
        repository = FakeExecutionRepository(workflow)
        first_provider = QueueProvider(
            [requirements_json(), tech_stack_json(), architecture_json()]
        )
        asyncio.run(
            make_engine(repository, first_provider).run(
                workflow.id,
                1,
                expected_version=workflow.version,
                mode=WorkflowRunMode.INCOMPLETE,
            )
        )
        workflow.nodes[1].status = WorkflowNodeStatus.STALE
        workflow.nodes[2].status = WorkflowNodeStatus.SUCCESS
        repository.stale_events.clear()
        second_provider = QueueProvider(
            [tech_stack_json(language="Java"), architecture_json(backend="Spring Boot")]
        )

        rerun = asyncio.run(
            make_engine(repository, second_provider).run(
                workflow.id,
                1,
                expected_version=workflow.version,
                mode=WorkflowRunMode.INCOMPLETE,
            )
        )

        self.assertEqual(rerun.status, WorkflowRunStatus.COMPLETED)
        self.assertEqual(len(rerun.ai_requests), 2)
        self.assertEqual(
            [item.request_type for item in rerun.ai_requests],
            ["tech_stack_analysis", "architecture_design"],
        )
        self.assertIn(23, repository.stale_events[0])
        self.assertEqual(workflow.project.language, "Java")
        self.assertEqual(workflow.project.backend, "Spring Boot")
        self.assertEqual(workflow.nodes[2].status, WorkflowNodeStatus.SUCCESS)

    def test_completed_workflow_default_rerun_creates_no_duplicate(self) -> None:
        workflow = make_workflow()
        repository = FakeExecutionRepository(workflow)
        engine = make_engine(
            repository,
            QueueProvider([requirements_json(), tech_stack_json(), architecture_json()]),
        )
        asyncio.run(
            engine.run(
                workflow.id,
                1,
                expected_version=workflow.version,
                mode=WorkflowRunMode.INCOMPLETE,
            )
        )

        with self.assertRaises(ConflictError):
            asyncio.run(
                engine.run(
                    workflow.id,
                    1,
                    expected_version=workflow.version,
                    mode=WorkflowRunMode.INCOMPLETE,
                )
            )
        self.assertEqual(len(repository.runs), 1)

    def test_provider_failure_is_persisted(self) -> None:
        workflow = make_workflow()
        repository = FakeExecutionRepository(workflow)
        provider = QueueProvider(
            [AIClientError("private body", category=AIFailureCategory.UPSTREAM)]
        )

        run = asyncio.run(
            make_engine(repository, provider).run(
                workflow.id,
                1,
                expected_version=workflow.version,
                mode=WorkflowRunMode.INCOMPLETE,
            )
        )

        self.assertEqual(run.status, WorkflowRunStatus.FAILED)
        self.assertEqual(run.error_code, "upstream")
        self.assertNotIn("private body", run.error_message or "")
        self.assertEqual(workflow.nodes[0].status, WorkflowNodeStatus.FAILED)
        self.assertEqual(run.ai_requests[0].status, AIRequestStatus.FAILED)

    def test_invalid_model_result_is_persisted(self) -> None:
        workflow = make_workflow()
        repository = FakeExecutionRepository(workflow)
        run = asyncio.run(
            make_engine(repository, QueueProvider(["not-json"])).run(
                workflow.id,
                1,
                expected_version=workflow.version,
                mode=WorkflowRunMode.INCOMPLETE,
            )
        )
        self.assertEqual(run.status, WorkflowRunStatus.FAILED)
        self.assertEqual(run.error_code, "agent_output_invalid")

    def test_workflow_total_timeout_is_persisted(self) -> None:
        workflow = make_workflow()
        repository = FakeExecutionRepository(workflow)
        provider = QueueProvider([requirements_json()], delay_seconds=0.05)
        run = asyncio.run(
            make_engine(repository, provider, total_timeout=0.01).run(
                workflow.id,
                1,
                expected_version=workflow.version,
                mode=WorkflowRunMode.INCOMPLETE,
            )
        )
        self.assertEqual(run.status, WorkflowRunStatus.FAILED)
        self.assertEqual(run.error_code, "workflow_timeout")

    def test_cancellation_is_propagated_and_persisted(self) -> None:
        workflow = make_workflow()
        repository = FakeExecutionRepository(workflow)
        provider = QueueProvider([requirements_json()], delay_seconds=1)
        engine = make_engine(repository, provider, total_timeout=2)

        async def cancel_running_workflow() -> None:
            task = asyncio.create_task(
                engine.run(
                    workflow.id,
                    1,
                    expected_version=workflow.version,
                    mode=WorkflowRunMode.INCOMPLETE,
                )
            )
            await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        asyncio.run(cancel_running_workflow())

        self.assertEqual(repository.runs[0].status, WorkflowRunStatus.CANCELLED)
        self.assertEqual(repository.runs[0].error_code, "cancelled")
        self.assertEqual(workflow.nodes[0].status, WorkflowNodeStatus.STALE)
        self.assertEqual(
            repository.runs[0].ai_requests[0].status,
            AIRequestStatus.FAILED,
        )

    def test_completion_budget_stops_before_next_node(self) -> None:
        workflow = make_workflow()
        repository = FakeExecutionRepository(workflow)
        provider = QueueProvider([(requirements_json(), 200)])
        run = asyncio.run(
            make_engine(
                repository,
                provider,
                max_completion_tokens=256,
            ).run(
                workflow.id,
                1,
                expected_version=workflow.version,
                mode=WorkflowRunMode.INCOMPLETE,
            )
        )
        self.assertEqual(run.status, WorkflowRunStatus.FAILED)
        self.assertEqual(run.error_code, "budget_exhausted")
        self.assertEqual(len(provider.requests), 1)

    def test_unregistered_node_and_wrong_owner_are_rejected_before_run(self) -> None:
        workflow = make_workflow(owner_id=2)
        repository = FakeExecutionRepository(workflow)
        engine = make_engine(repository, QueueProvider([]))
        with self.assertRaises(PermissionDeniedError):
            asyncio.run(
                engine.run(
                    workflow.id,
                    1,
                    expected_version=workflow.version,
                    mode=WorkflowRunMode.INCOMPLETE,
                )
            )
        workflow.project.owner_id = 1
        workflow.nodes[0].node_type = "quality_check"
        with self.assertRaises(ConflictError):
            asyncio.run(
                engine.run(
                    workflow.id,
                    1,
                    expected_version=workflow.version,
                    mode=WorkflowRunMode.INCOMPLETE,
                )
            )
        self.assertEqual(repository.runs, [])


def make_run_data() -> WorkflowRunData:
    return WorkflowRunData(
        id=101,
        workflow_id=11,
        status=WorkflowRunStatus.COMPLETED,
        context_version=1,
        error=None,
        nodes=[],
        started_at=NOW,
        finished_at=NOW,
        created_at=NOW,
    )


class WorkflowRunAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=WorkflowService)
        self.service.run_workflow = AsyncMock(return_value=make_run_data())
        self.service.list_runs.return_value = WorkflowRunPage(
            items=[make_run_data()], total=1, page=1, page_size=20, total_pages=1
        )
        self.service.get_run.return_value = make_run_data()
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="student",
            email="student@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_workflow_execution_service] = (
            lambda: self.service
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_run_list_and_detail_routes_map_service(self) -> None:
        run_response = request(
            self.app,
            "POST",
            "/api/v1/workflows/11/run",
            body={"expected_version": 4},
        )
        list_response = request(
            self.app,
            "GET",
            "/api/v1/workflows/11/runs",
        )
        detail_response = request(
            self.app,
            "GET",
            "/api/v1/workflows/11/runs/101",
        )

        self.assertEqual(run_response.status_code, 201)
        self.assertEqual(run_response.json()["status"], "completed")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 1)
        self.assertEqual(detail_response.status_code, 200)
        run_input = self.service.run_workflow.await_args.args[2]
        self.assertEqual(run_input.mode, WorkflowRunMode.INCOMPLETE)

    def test_routes_require_authentication_and_validate_payload(self) -> None:
        app = create_app()
        app.dependency_overrides[get_workflow_execution_service] = lambda: self.service
        unauthenticated = request(
            app,
            "POST",
            "/api/v1/workflows/11/run",
            body={"expected_version": 4},
        )
        invalid = request(
            self.app,
            "POST",
            "/api/v1/workflows/11/run",
            body={"expected_version": 0, "mode": "unknown"},
        )
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(invalid.status_code, 422)


class WorkflowRunServiceTests(unittest.TestCase):
    def test_results_are_queryable_and_revalidated(self) -> None:
        workflow = make_workflow()
        execution_repository = FakeExecutionRepository(workflow)
        crud_repository = Mock(spec=WorkflowRepository)
        crud_repository.get_workflow.return_value = workflow
        engine = make_engine(
            execution_repository,
            QueueProvider([requirements_json(), tech_stack_json(), architecture_json()]),
        )
        service = WorkflowService(crud_repository, execution_repository, engine)

        created = asyncio.run(
            service.run_workflow(
                workflow.id,
                1,
                data=type(
                    "RunInput",
                    (),
                    {
                        "expected_version": workflow.version,
                        "mode": WorkflowRunMode.INCOMPLETE,
                    },
                )(),
            )
        )
        queried = service.get_run(workflow.id, created.id, 1)
        page = service.list_runs(workflow.id, 1, page=1, page_size=20)

        self.assertEqual(queried.id, created.id)
        self.assertEqual(len(queried.nodes), 3)
        self.assertEqual(queried.nodes[0].result.result_type, "requirements_analysis")
        self.assertEqual(page.total, 1)


if __name__ == "__main__":
    unittest.main()
