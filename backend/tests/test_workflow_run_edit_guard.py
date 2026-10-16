import asyncio
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import unittest

import httpx
from sqlalchemy import (
    Column,
    DefaultClause,
    Integer,
    MetaData,
    Table,
    create_engine,
    func,
    select,
    text,
    update,
)
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, SMALLINT
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIProviderResult,
)
from app.api.deps import (
    get_current_user,
    get_workflow_execution_service,
    get_workflow_service,
)
from app.context.context_manager import ContextManager
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.main import create_app
from app.models.ai import AIRequest, AIResult
from app.models.enums import (
    AIRequestStatus,
    WorkflowNodeStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from app.models.project import Project
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode, WorkflowRun
from app.repositories.workflow import WorkflowPersistenceConflictError, WorkflowRepository
from app.repositories.workflow_execution import WorkflowExecutionRepository
from app.services.auth import UserIdentity
from app.services.workflow import (
    WorkflowEdgeCreateData,
    WorkflowEdgeUpdateData,
    WorkflowGraphEdgeData,
    WorkflowGraphNodeData,
    WorkflowGraphUpdateData,
    WorkflowNodeCreateData,
    WorkflowNodeUpdateData,
    WorkflowService,
    WorkflowUpdateData,
)
from app.workflow.engine import WorkflowEngine, WorkflowEngineLimits, WorkflowRunMode
from tests.test_workflow_engine import (
    QueueProvider,
    architecture_json,
    make_registry,
    make_workflow,
    requirements_json,
    tech_stack_json,
)


class PausedProvider(QueueProvider):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__(
            [AIClientError("fake failure", category=AIFailureCategory.UPSTREAM)]
            if fail else [requirements_json(), tech_stack_json(), architecture_json()]
        )
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def complete(self, request_data: AICompletionRequest) -> AIProviderResult:
        self.entered.set()
        await self.release.wait()
        return await super().complete(request_data)


@contextmanager
def isolated_database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    metadata = MetaData()
    users = Table("users", metadata, Column("id", Integer, primary_key=True))
    # 只复制实际执行需要的表；仅在测试副本转换 MySQL 自增和时间默认值。
    for model in (Project, Workflow, WorkflowNode, WorkflowEdge, WorkflowRun, AIRequest, AIResult):
        table = model.__table__.to_metadata(metadata)
        for column in table.columns:
            if isinstance(column.type, (BIGINT, INTEGER, SMALLINT)):
                column.type = Integer()
            if (
                column.server_default is not None
                and "CURRENT_TIMESTAMP(6)" in str(column.server_default.arg)
            ):
                column.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))
    metadata.create_all(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    with Session(engine) as session:
        session.execute(users.insert().values(id=1))
        workflow = make_workflow()
        edges = list(workflow.edges)
        workflow.edges = []
        session.add(workflow)
        session.flush()
        workflow.edges = edges
        session.commit()
    try:
        yield engine
    finally:
        engine.dispose()


def make_real_engine(repository, provider):
    return WorkflowEngine(
        repository,
        make_registry(provider, client_timeout=5),
        ContextManager(),
        WorkflowEngineLimits(
            max_nodes=12,
            max_rounds=12,
            max_node_tokens=1200,
            max_completion_tokens=4000,
            total_timeout_seconds=10,
            recovery_timeout_seconds=30,
        ),
    )


def graph_snapshot(engine):
    with Session(engine) as session:
        return deepcopy(asdict(WorkflowService(WorkflowRepository(session)).get_graph(11, 1)))


def unchanged_graph_data(snapshot):
    node_fields = (
        "node_key", "node_type", "name", "position_x", "position_y", "config",
    )
    return WorkflowGraphUpdateData(
        version=snapshot["workflow"]["version"],
        nodes=[WorkflowGraphNodeData(**{
            key: node[key] for key in node_fields
        }) for node in snapshot["nodes"]],
        edges=[WorkflowGraphEdgeData(**{
            key: edge[key] for key in ("source_node_key", "target_node_key", "condition_data")
        }) for edge in snapshot["edges"]],
    )


class WorkflowRunEditGuardTests(unittest.IsolatedAsyncioTestCase):
    async def paused_run(self, engine, repository_class=WorkflowExecutionRepository, *, fail=False):
        session = Session(engine, autoflush=False, expire_on_commit=False)
        provider = PausedProvider(fail=fail)

        async def execute():
            with session:
                return await make_real_engine(repository_class(session), provider).run(
                    11, 1, expected_version=4, mode=WorkflowRunMode.ALL,
                )

        task = asyncio.create_task(execute())
        try:
            await asyncio.wait_for(provider.entered.wait(), timeout=3)
            self.assertFalse(session.in_transaction(), "模型等待期间不应持有数据库事务")
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
        return task, provider

    async def finish_paused(self, task, provider):
        provider.release.set()
        return await asyncio.wait_for(task, timeout=5)

    async def retry(self, engine, expected_version):
        with Session(engine) as session:
            provider = QueueProvider([requirements_json(), tech_stack_json(), architecture_json()])
            return await make_real_engine(WorkflowExecutionRepository(session), provider).run(
                11, 1, expected_version=expected_version, mode=WorkflowRunMode.ALL,
            )

    async def test_all_graph_writes_are_rejected_without_partial_changes(self):
        operations = [
            ("create_node", lambda service, before: service.create_node(
                11, 1, WorkflowNodeCreateData(
                    "extra", "requirements_analysis", "额外节点", 780, 0,
                    {"instruction": "新指令"},
                ),
            )),
            *[(f"update_node_{field}", lambda service, before, field=field, value=value:
               service.update_node(11, 21, 1, WorkflowNodeUpdateData({field: value})))
              for field, value in (
                  ("config", {"instruction": "运行中修改指令"}),
                  ("name", "运行中改名"), ("position_x", 25), ("position_y", 50),
                  ("node_key", "renamed"), ("node_type", "tech_stack_analysis"),
              )],
            ("delete_node", lambda service, before: service.delete_node(11, 23, 1)),
            ("create_edge", lambda service, before: service.create_edge(
                11, 1, WorkflowEdgeCreateData(21, 23, None),
            )),
            ("update_edge_condition", lambda service, before: service.update_edge(
                11, 31, 1, WorkflowEdgeUpdateData({"condition_data": {"changed": True}}),
            )),
            ("update_edge_endpoints", lambda service, before: service.update_edge(
                11, 31, 1, WorkflowEdgeUpdateData({"target_node_id": 23}),
            )),
            ("delete_edge", lambda service, before: service.delete_edge(11, 31, 1)),
            ("replace_identical_graph", lambda service, before: service.replace_graph(
                11, 1, unchanged_graph_data(before),
            )),
            ("replace_empty_graph", lambda service, before: service.replace_graph(
                11, 1, WorkflowGraphUpdateData(4, [], []),
            )),
            ("delete_workflow", lambda service, before: service.delete_workflow(11, 1)),
        ]
        for operation_name, operation in operations:
            with self.subTest(operation=operation_name), isolated_database() as engine:
                task, provider = await self.paused_run(engine)
                try:
                    before = graph_snapshot(engine)
                    with Session(engine) as session:
                        service = WorkflowService(WorkflowRepository(session))
                        with self.assertRaises(ConflictError):
                            operation(service, before)
                    self.assertEqual(graph_snapshot(engine), before)
                finally:
                    provider.release.set()
                    await asyncio.gather(task, return_exceptions=True)

    async def test_metadata_update_and_reads_work_during_run_and_editing_resumes(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine)
            try:
                before = graph_snapshot(engine)
                with Session(engine) as session:
                    service = WorkflowService(WorkflowRepository(session))
                    updated = service.update_workflow(11, 1, WorkflowUpdateData({
                        "name": "运行中允许修改标题", "description": "元信息更新",
                    }))
                    self.assertEqual(updated.version, 4)
                    self.assertEqual(updated.status, WorkflowStatus.RUNNING)
                    self.assertEqual(len(service.list_nodes(11, 1)), 3)
                    self.assertEqual(len(service.list_edges(11, 1)), 2)
                    self.assertEqual(service.get_graph(11, 1).workflow.name, updated.name)
                after = graph_snapshot(engine)
                self.assertEqual(after["nodes"], before["nodes"])
                self.assertEqual(after["edges"], before["edges"])
                self.assertEqual((after["workflow"]["name"], after["workflow"]["description"]),
                                 ("运行中允许修改标题", "元信息更新"))
                result = await self.finish_paused(task, provider)
                self.assertEqual(result.status, WorkflowRunStatus.COMPLETED)
                with Session(engine) as session:
                    service = WorkflowService(WorkflowRepository(session))
                    service.update_node(
                        11, 21, 1,
                        WorkflowNodeUpdateData({"config": {"instruction": "完成后编辑"}}),
                    )
                    self.assertEqual(service.get_graph(11, 1).workflow.version, 5)
            finally:
                provider.release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_active_run_is_not_overwritten_by_second_start(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine)
            try:
                with Session(engine) as session:
                    second_provider = QueueProvider([requirements_json()])
                    with self.assertRaises(ConflictError):
                        second_engine = make_real_engine(
                            WorkflowExecutionRepository(session), second_provider,
                        )
                        await second_engine.run(
                            11, 1, expected_version=4, mode=WorkflowRunMode.ALL,
                        )
                    self.assertEqual(second_provider.requests, [])
                    self.assertEqual(session.scalar(select(func.count(WorkflowRun.id))), 1)
                completed = await self.finish_paused(task, provider)
                self.assertEqual(completed.status, WorkflowRunStatus.COMPLETED)
            finally:
                provider.release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_repository_rejects_pre_mutated_node_without_autoflush(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine)
            try:
                before = graph_snapshot(engine)
                with Session(engine) as session:
                    repository = WorkflowRepository(session)
                    workflow = repository.get_workflow(11)
                    node = next(node for node in workflow.nodes if node.id == 21)
                    node.config = {"instruction": "不能在检查前自动提交"}
                    with self.assertRaises(WorkflowPersistenceConflictError):
                        repository.update_node(workflow, node)
                self.assertEqual(graph_snapshot(engine), before)
            finally:
                provider.release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_other_owner_cannot_edit_active_workflow(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine)
            try:
                before = graph_snapshot(engine)
                with Session(engine) as session:
                    with self.assertRaises(PermissionDeniedError):
                        WorkflowService(WorkflowRepository(session)).update_node(
                            11, 21, 2, WorkflowNodeUpdateData({"name": "越权修改"}),
                        )
                self.assertEqual(graph_snapshot(engine), before)
            finally:
                provider.release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_running_run_blocks_edit_even_if_workflow_display_status_changes(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine)
            try:
                with Session(engine) as session:
                    session.execute(
                        update(Workflow).where(Workflow.id == 11)
                        .values(status=WorkflowStatus.STALE)
                    )
                    session.commit()
                before = graph_snapshot(engine)
                with Session(engine) as session:
                    with self.assertRaises(ConflictError):
                        WorkflowService(WorkflowRepository(session)).update_node(
                            11, 21, 1, WorkflowNodeUpdateData({"name": "不可绕过"}),
                        )
                self.assertEqual(graph_snapshot(engine), before)
            finally:
                provider.release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_version_change_during_provider_rejects_old_result_and_allows_retry(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine)
            try:
                with Session(engine) as session:
                    original_context = deepcopy(session.get(Project, 7).context_data)
                    session.execute(update(Workflow).where(Workflow.id == 11).values(version=5))
                    session.commit()
                failed = await self.finish_paused(task, provider)
                self.assertEqual(failed.status, WorkflowRunStatus.FAILED)
                self.assertIsNotNone(failed.finished_at)
                with Session(engine) as session:
                    self.assertEqual(session.get(Project, 7).context_data, original_context)
                    self.assertEqual(session.scalar(select(func.count(AIResult.id))), 0)
                    self.assertEqual(
                        session.scalar(select(AIRequest.status)), AIRequestStatus.FAILED,
                    )
                    self.assertNotEqual(
                        session.get(WorkflowNode, 21).status, WorkflowNodeStatus.SUCCESS,
                    )
                    self.assertEqual(session.get(Workflow, 11).status, WorkflowStatus.FAILED)
                self.assertEqual((await self.retry(engine, 5)).status, WorkflowRunStatus.COMPLETED)
            finally:
                provider.release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_finish_run_checks_starting_version_after_last_node_commit(self):
        with isolated_database() as engine:
            class BumpAfterLastNode(WorkflowExecutionRepository):
                def complete_node(inner_self, run_id, node_id, request_id, **values):
                    super().complete_node(run_id, node_id, request_id, **values)
                    if node_id == 23:
                        with Session(engine) as session:
                            session.execute(
                                update(Workflow).where(Workflow.id == 11).values(version=5)
                            )
                            session.commit()

            task, provider = await self.paused_run(engine, BumpAfterLastNode)
            result = await self.finish_paused(task, provider)
            self.assertEqual(result.status, WorkflowRunStatus.FAILED)
            with Session(engine) as session:
                self.assertEqual(session.get(Workflow, 11).status, WorkflowStatus.FAILED)
            self.assertEqual((await self.retry(engine, 5)).status, WorkflowRunStatus.COMPLETED)

    async def test_version_change_before_start_node_calls_no_provider_and_allows_retry(self):
        with isolated_database() as engine:
            class BumpAfterStartRun(WorkflowExecutionRepository):
                def start_run(inner_self, *args, **values):
                    run = super().start_run(*args, **values)
                    with Session(engine) as session:
                        session.execute(update(Workflow).where(Workflow.id == 11).values(version=5))
                        session.commit()
                    return run

            with Session(engine) as session:
                original_context = deepcopy(session.get(Project, 7).context_data)
                provider = QueueProvider([
                    requirements_json(), tech_stack_json(), architecture_json(),
                ])
                result = await make_real_engine(BumpAfterStartRun(session), provider).run(
                    11, 1, expected_version=4, mode=WorkflowRunMode.ALL,
                )
                self.assertEqual(result.status, WorkflowRunStatus.FAILED)
                self.assertEqual(provider.requests, [])
                self.assertEqual(session.get(Project, 7).context_data, original_context)
                self.assertEqual(session.scalar(select(func.count(AIRequest.id))), 0)
                self.assertEqual(session.scalar(select(func.count(AIResult.id))), 0)
            self.assertEqual((await self.retry(engine, 5)).status, WorkflowRunStatus.COMPLETED)

    async def test_cancelled_run_releases_edit_guard(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            with Session(engine) as session:
                self.assertEqual(
                    session.scalar(select(WorkflowRun.status)), WorkflowRunStatus.CANCELLED,
                )
                self.assertEqual(session.scalar(select(AIRequest.status)), AIRequestStatus.FAILED)
                WorkflowService(WorkflowRepository(session)).update_node(
                    11, 21, 1, WorkflowNodeUpdateData({"name": "取消后编辑"}),
                )
            self.assertEqual(graph_snapshot(engine)["workflow"]["version"], 5)

    async def test_provider_failure_releases_edit_guard(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine, fail=True)
            failed = await self.finish_paused(task, provider)
            self.assertEqual(failed.status, WorkflowRunStatus.FAILED)
            with Session(engine) as session:
                self.assertEqual(session.scalar(select(func.count(AIResult.id))), 0)
                WorkflowService(WorkflowRepository(session)).update_node(
                    11, 21, 1, WorkflowNodeUpdateData({"name": "失败后编辑"}),
                )
            self.assertEqual(graph_snapshot(engine)["workflow"]["version"], 5)

    async def test_abandoned_run_recovery_does_not_let_old_engine_overwrite_new_run(self):
        with isolated_database() as engine:
            task, provider = await self.paused_run(engine)
            try:
                with Session(engine) as session:
                    old_run_id = session.scalar(select(WorkflowRun.id))
                    old_request_id = session.scalar(select(AIRequest.id))
                    session.execute(
                        update(WorkflowRun).where(WorkflowRun.id == old_run_id)
                        .values(started_at=datetime.now(UTC) - timedelta(seconds=60))
                    )
                    session.commit()

                recovered = await self.retry(engine, 4)
                self.assertEqual(recovered.status, WorkflowRunStatus.COMPLETED)
                with Session(engine) as session:
                    old_run = session.get(WorkflowRun, old_run_id)
                    self.assertEqual(old_run.status, WorkflowRunStatus.FAILED)
                    self.assertEqual(old_run.error_code, "recovered_timeout")
                    self.assertEqual(
                        session.get(AIRequest, old_request_id).status,
                        AIRequestStatus.FAILED,
                    )
                    self.assertEqual(session.scalar(select(func.count(AIResult.id))), 3)

                before_old_response = graph_snapshot(engine)
                self.assertEqual(
                    (await self.finish_paused(task, provider)).status,
                    WorkflowRunStatus.FAILED,
                )
                self.assertEqual(graph_snapshot(engine), before_old_response)
                with Session(engine) as session:
                    self.assertEqual(
                        session.get(WorkflowRun, recovered.id).status,
                        WorkflowRunStatus.COMPLETED,
                    )
                    self.assertEqual(session.scalar(select(func.count(AIResult.id))), 3)
            finally:
                provider.release.set()
                await asyncio.gather(task, return_exceptions=True)

    async def test_http_node_edit_returns_409_while_run_waits_for_provider(self):
        with isolated_database() as engine, Session(
            engine, autoflush=False, expire_on_commit=False,
        ) as execution_session, Session(
            engine, autoflush=False, expire_on_commit=False,
        ) as edit_session:
            app = create_app()
            provider = PausedProvider()
            execution_repository = WorkflowExecutionRepository(execution_session)
            execution_service = WorkflowService(
                WorkflowRepository(execution_session), execution_repository,
                make_real_engine(execution_repository, provider),
            )

            async def execution_override():
                return execution_service

            async def edit_override():
                return WorkflowService(WorkflowRepository(edit_session))

            app.dependency_overrides[get_current_user] = lambda: UserIdentity(
                id=1, username="student", email="student@example.com",
                avatar_url=None, bio=None, is_active=True,
                created_at=datetime.now(UTC),
            )
            app.dependency_overrides[get_workflow_execution_service] = execution_override
            app.dependency_overrides[get_workflow_service] = edit_override
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver",
            ) as client:
                run_task = asyncio.create_task(client.post(
                    "/api/v1/workflows/11/run",
                    json={"expected_version": 4, "mode": "all"},
                ))
                try:
                    await asyncio.wait_for(provider.entered.wait(), timeout=3)
                    self.assertFalse(execution_session.in_transaction())
                    before = graph_snapshot(engine)
                    edit_response = await client.put(
                        "/api/v1/workflows/11/nodes/21",
                        json={"config": {"instruction": "运行中替换指令"}},
                    )
                    self.assertEqual(edit_response.status_code, 409)
                    self.assertEqual(graph_snapshot(engine), before)
                    provider.release.set()
                    run_response = await asyncio.wait_for(run_task, timeout=5)
                    self.assertEqual(run_response.status_code, 201)
                    self.assertEqual(run_response.json()["status"], "completed")
                finally:
                    provider.release.set()
                    await asyncio.gather(run_task, return_exceptions=True)
                    app.dependency_overrides.clear()
