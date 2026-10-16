"""CR1 专用本机 MySQL 并发验收；只使用虚构样本和确定性节点结果。"""

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
import re
from secrets import token_hex, token_urlsafe
from threading import Event, Thread
from typing import Any

from pwdlib import PasswordHash
from sqlalchemy import Engine, create_engine, delete, event, func, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.context.context_manager import ContextManager
from app.context.context_schema import ContextSource, ContextSourceType
from app.context.project_context import ContextBuilder, ProjectContext, ProjectContextSeed
from app.core.config import get_settings
from app.models import Base
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
from app.models.user import User
from app.models.workflow import Workflow, WorkflowNode, WorkflowRun
from app.repositories.project_context import ProjectContextRepository
from app.repositories.workflow import WorkflowEditConflictError, WorkflowRepository
from app.repositories.workflow_execution import (
    WorkflowActiveRunError,
    WorkflowExecutionRepository,
    WorkflowExecutionVersionError,
    WorkflowGraphVersionError,
)
from app.services.project_context import (
    NodeContextWriteData,
    ProjectContextService,
)
from scripts.verify_workflow_engine import requirements_result


WAIT_SECONDS = 8.0
JOIN_SECONDS = 15.0
BLOCK_PROBE_SECONDS = 0.25


class VerificationError(RuntimeError):
    """可公开的验收断言或隔离前置条件错误。"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def create_bounded_engine(url: URL) -> Engine:
    engine = create_engine(
        url,
        hide_parameters=True,
        pool_size=4,
        max_overflow=0,
        pool_timeout=5,
        connect_args={"connect_timeout": 3, "read_timeout": 12, "write_timeout": 6},
    )

    @event.listens_for(engine, "connect")
    def configure_connection(connection: Any, _record: Any) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")
            cursor.execute("SET SESSION lock_wait_timeout = 5")

    return engine


def database_counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            name: int(connection.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in Base.metadata.tables.items()
        }


def initialize_database(database: str, *, initialize: bool) -> Engine:
    require(initialize, "必须显式传入 --initialize；本脚本只接受首次创建的专用库")
    require(
        re.fullmatch(r"scholarhub_l4_20261016_cr1(?:_[a-z0-9_]{1,28})?", database)
        is not None,
        "专用库名必须是 scholarhub_l4_20261016_cr1 或带下划线后缀的同名前缀",
    )
    configured = get_settings().database_url
    require(bool(configured), "本机未配置数据库连接")
    url = make_url(configured)
    require(url.drivername == "mysql+pymysql", "只接受 mysql+pymysql 驱动")
    require(url.host in {"127.0.0.1", "localhost", "::1"}, "只接受本机 MySQL")
    # 连接参数只从已验证的主机、端口和凭据重建，避免 URL query 覆盖连接目标或超时。
    local_url = URL.create(
        "mysql+pymysql",
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        query={"charset": "utf8mb4"},
    )
    server = create_bounded_engine(local_url)
    try:
        with server.connect() as connection:
            exists = connection.scalar(
                text("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=:name"),
                {"name": database},
            )
            require(exists is None, "专用库已存在，拒绝复用、清空或重新初始化")
            connection.exec_driver_sql(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
    finally:
        server.dispose()
    engine = create_bounded_engine(local_url.set(database=database))
    try:
        # 仅建现有 Models 表，不执行迁移，也不修改已有库。
        Base.metadata.create_all(engine)
        require(
            set(inspect(engine).get_table_names()) == set(Base.metadata.tables),
            "专用库表集合与现有 Models 不一致",
        )
        require(not any(database_counts(engine).values()), "专用库出现非空数据，拒绝验收")
    except BaseException:
        engine.dispose()
        raise
    print(json.dumps({"environment": "dedicated-local-mysql", "database": database, "initial_rows": 0}))
    return engine


@dataclass(frozen=True)
class Fixture:
    user_id: int
    project_id: int
    workflow_id: int
    node_id: int


def create_fixture(factory: sessionmaker[Session], marker: str) -> Fixture:
    with factory() as session:
        user = User(
            username=marker,
            email=f"{marker}@example.invalid",
            password_hash=PasswordHash.recommended().hash(token_urlsafe(32)),
        )
        project = Project(
            owner=user,
            name="CR1 concurrency verification",
            difficulty=ProjectDifficulty.INTERMEDIATE,
            status=ProjectStatus.IN_PROGRESS,
            language="Python",
            framework="FastAPI",
            frontend="Vue 3",
            backend="FastAPI",
            database="MySQL",
            requirements=[{"title": "CR1 fictional verification"}],
            output_requirement="Deterministic persistence verification",
        )
        workflow = Workflow(project=project, name="CR1 verification", status=WorkflowStatus.READY)
        node = WorkflowNode(
            workflow=workflow,
            node_key="requirements",
            node_type="requirements_analysis",
            name="需求分析",
            position_x=0,
            position_y=0,
        )
        session.add_all([user, project, workflow, node])
        session.flush()
        context = ContextBuilder().build(
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
        )
        project.context_data = context.to_storage()
        session.commit()
        return Fixture(user.id, project.id, workflow.id, node.id)


@dataclass
class Worker:
    factory: sessionmaker[Session]
    operation: Callable[[Session], Any]
    ready: Event = field(default_factory=Event)
    at_project_lock: Event = field(default_factory=Event)
    done: Event = field(default_factory=Event)
    connection_id: int | None = None
    result: Any = None
    error: BaseException | None = None
    thread: Thread = field(init=False)

    def __post_init__(self) -> None:
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        try:
            with self.factory() as session:
                connection = session.connection()
                self.connection_id = int(connection.scalar(text("SELECT CONNECTION_ID()")))

                def mark_project_lock(
                    _connection: Any, _cursor: Any, statement: str,
                    _parameters: Any, _context: Any, _executemany: Any,
                ) -> None:
                    normalized = " ".join(statement.lower().replace("`", "").split())
                    if "from projects" in normalized and "for update" in normalized:
                        self.at_project_lock.set()

                event.listen(connection, "before_cursor_execute", mark_project_lock)
                self.ready.set()
                self.result = self.operation(session)
        except BaseException as exc:
            self.error = exc
        finally:
            self.ready.set()
            self.done.set()

    def join(self) -> None:
        self.thread.join(timeout=JOIN_SECONDS)
        require(not self.thread.is_alive(), "并发线程未在有界期限内结束")

    def successful_result(self) -> Any:
        self.join()
        if self.error is not None:
            raise VerificationError(f"并发操作出现意外异常：{type(self.error).__name__}") from None
        return self.result


def assert_waiting(worker: Worker, holder_connection_id: int) -> None:
    require(worker.ready.wait(WAIT_SECONDS), "并发连接未及时就绪")
    require(worker.connection_id != holder_connection_id, "并发验收必须使用独立 MySQL 连接")
    require(worker.at_project_lock.wait(WAIT_SECONDS), "并发操作未进入 Project 行锁边界")
    require(not worker.done.wait(BLOCK_PROBE_SECONDS), "持锁事务提交前，并发操作没有等待")


def snapshot(session: Session, fixture: Fixture) -> tuple[int, ProjectContext]:
    workflow = session.get(Workflow, fixture.workflow_id)
    project = session.get(Project, fixture.project_id)
    require(workflow is not None and project is not None, "虚构样本不存在")
    return workflow.version, ProjectContext.from_storage(project.context_data)


def start_run(session: Session, fixture: Fixture, version: int, context: ProjectContext) -> int:
    return WorkflowExecutionRepository(session).start_run(
        fixture.workflow_id,
        fixture.user_id,
        expected_version=version,
        context_snapshot=context.to_storage(),
        stale_before=datetime.now(UTC) - timedelta(seconds=60),
    ).id


def edit_node(session: Session, fixture: Fixture, name: str) -> int:
    repository = WorkflowRepository(session)
    workflow = repository.get_workflow(fixture.workflow_id)
    node = repository.get_node(fixture.node_id)
    require(workflow is not None and node is not None, "待编辑虚构节点不存在")
    node.name = name
    _, version = repository.update_node(workflow, node)
    return version


def fail_run(session: Session, run_id: int, *, node_id: int | None = None, request_id: int | None = None) -> None:
    WorkflowExecutionRepository(session).fail_run(
        run_id,
        node_id=node_id,
        request_id=request_id,
        error_code="cr1_controlled_failure",
        error_message="CR1 确定性验收主动结束运行",
    )


def verify_edit_then_start(factory: sessionmaker[Session], fixture: Fixture) -> None:
    worker = None
    with factory() as holder:
        try:
            version, context = snapshot(holder, fixture)
            workflow = holder.get(Workflow, fixture.workflow_id)
            WorkflowRepository(holder).lock_for_edit(workflow)
            connection_id = int(holder.scalar(text("SELECT CONNECTION_ID()")))
            worker = Worker(factory, lambda session: start_run(session, fixture, version, context))
            assert_waiting(worker, connection_id)
            edit_node(holder, fixture, "编辑先提交")
            worker.join()
            require(isinstance(worker.error, WorkflowGraphVersionError), "编辑提交后 start_run 必须拒绝旧图版本")
        finally:
            holder.rollback()
            if worker is not None:
                worker.join()
    with factory() as session:
        require(WorkflowExecutionRepository(session).count_runs(fixture.workflow_id) == 0, "旧图启动创建了运行")
    print(json.dumps({"edit_then_start": "passed", "blocked_before_commit": True, "old_version_rejected": True}))


def verify_start_then_edit(factory: sessionmaker[Session], fixture: Fixture) -> None:
    holder_locked, release_holder = Event(), Event()
    with factory() as session:
        version, context = snapshot(session, fixture)

    def hold_start(session: Session) -> int:
        def before_commit(_session: Session) -> None:
            holder_locked.set()
            require(release_holder.wait(WAIT_SECONDS), "启动事务未及时收到提交信号")

        event.listen(session, "before_commit", before_commit, once=True)
        return start_run(session, fixture, version, context)

    holder = Worker(factory, hold_start)
    editor = None
    try:
        require(holder_locked.wait(WAIT_SECONDS), "start_run 未及时持有父记录锁")
        editor = Worker(factory, lambda session: edit_node(session, fixture, "不应保存的编辑"))
        assert_waiting(editor, holder.connection_id)
    finally:
        release_holder.set()
        holder.join()
        if editor is not None:
            editor.join()
    run_id = holder.successful_result()
    require(isinstance(editor.error, WorkflowEditConflictError), "启动提交后必须拒绝活动运行的图编辑")
    with factory() as session:
        require(session.get(WorkflowNode, fixture.node_id).name == "编辑先提交", "拒绝编辑时仍保存了节点变更")
        fail_run(session, run_id)
    print(json.dumps({"start_then_edit": "passed", "blocked_before_commit": True, "active_run_edit_rejected": True}))


def verify_simultaneous_starts(factory: sessionmaker[Session], fixture: Fixture) -> None:
    gate = Event()
    with factory() as session:
        version, context = snapshot(session, fixture)

    def start_after_gate(session: Session) -> int:
        require(gate.wait(WAIT_SECONDS), "同时启动未及时收到放行信号")
        return start_run(session, fixture, version, context)

    workers = [Worker(factory, start_after_gate), Worker(factory, start_after_gate)]
    try:
        for worker in workers:
            require(worker.ready.wait(WAIT_SECONDS), "同时启动连接未及时就绪")
        require(workers[0].connection_id != workers[1].connection_id, "同时启动必须使用不同连接")
    finally:
        gate.set()
        for worker in workers:
            worker.join()
    winners = [worker for worker in workers if worker.error is None]
    losers = [worker for worker in workers if isinstance(worker.error, WorkflowActiveRunError)]
    require(len(winners) == 1 and len(losers) == 1, "同时启动必须只有一次成功和一次活动运行冲突")
    with factory() as session:
        active_count = session.scalar(select(func.count()).select_from(WorkflowRun).where(
            WorkflowRun.workflow_id == fixture.workflow_id,
            WorkflowRun.status == WorkflowRunStatus.RUNNING,
        ))
        require(active_count == 1, "同一工作流保存了多个活动运行")
        fail_run(session, winners[0].result)
    print(json.dumps({"simultaneous_starts": "passed", "successful_starts": 1, "active_run_conflicts": 1}))


def start_node(session: Session, fixture: Fixture, run_id: int, version: int, context: ProjectContext) -> int:
    return WorkflowExecutionRepository(session).start_node(
        run_id,
        fixture.node_id,
        expected_workflow_version=version,
        user_id=fixture.user_id,
        project_id=fixture.project_id,
        provider="fake",
        model="fake-model",
        node_type="requirements_analysis",
        node_key="requirements",
        input_hash="0" * 64,
        input_bytes=1,
        context_version=context.version,
    ).id


def complete_node(session: Session, fixture: Fixture, run_id: int, request_id: int, version: int, context: ProjectContext) -> None:
    # 沿用 P13 的确定性结果；直接验证持久化边界，不调用真实模型。
    result = json.loads(requirements_result())
    merged = ContextManager().merge(
        context,
        {key: result[key] for key in ("requirements", "features", "constraints")},
        source=ContextSource(type=ContextSourceType.WORKFLOW_NODE, id=fixture.node_id, node_key="requirements"),
    )
    WorkflowExecutionRepository(session).complete_node(
        run_id,
        fixture.node_id,
        request_id,
        expected_workflow_version=version,
        expected_context_version=context.version,
        context=merged.context,
        changed_fields=merged.changed_fields,
        stale_node_ids=frozenset(),
        structured_result=result,
        result_type="requirements_analysis",
        text_summary=result["summary"],
        content_hash="1" * 64,
        prompt_tokens=100,
        completion_tokens=80,
        latency_ms=1,
        finish_reason="stop",
        total_tokens=180,
    )


def verify_context_then_complete(factory: sessionmaker[Session], fixture: Fixture) -> None:
    with factory() as session:
        version, context = snapshot(session, fixture)
        run_id = start_run(session, fixture, version, context)
        request_id = start_node(session, fixture, run_id, version, context)

    def complete_then_fail(session: Session) -> str:
        try:
            complete_node(session, fixture, run_id, request_id, version, context)
        except WorkflowExecutionVersionError as exc:
            require(type(exc) is WorkflowExecutionVersionError, "预期 Context 版本冲突，实际发生图版本冲突")
            fail_run(session, run_id, node_id=fixture.node_id, request_id=request_id)
            return "context_conflict_then_failed"
        raise VerificationError("手工 Context 更新后 complete_node 未拒绝旧版本")

    worker = None
    with factory() as holder:
        try:
            repository = ProjectContextRepository(holder)
            require(repository.get_project(fixture.project_id, for_update=True) is not None, "待更新项目不存在")
            connection_id = int(holder.scalar(text("SELECT CONNECTION_ID()")))
            worker = Worker(factory, complete_then_fail)
            assert_waiting(worker, connection_id)
            # 用户通过节点 Context 写入入口修改该节点可写字段；保留 RUNNING 状态，
            # 同时写入节点 context_version，覆盖旧锁序下的 Project/Node 反向等待。
            ProjectContextService(repository).write_node_context(
                fixture.workflow_id,
                fixture.node_id,
                fixture.user_id,
                NodeContextWriteData(context.version, {"features": ["CR1 手工修改"]}),
            )
        finally:
            holder.rollback()
            if worker is not None:
                worker.join()
    require(worker.successful_result() == "context_conflict_then_failed", "Context 冲突后未正常结束运行")
    with factory() as session:
        require(session.get(WorkflowRun, run_id).status == WorkflowRunStatus.FAILED, "Context 冲突后运行未失败")
        require(session.get(AIRequest, request_id).status == AIRequestStatus.FAILED, "Context 冲突后请求未失败")
        require(session.scalar(select(AIResult.id).where(AIResult.request_id == request_id)) is None, "Context 冲突仍保存了旧结果")
        persisted = ProjectContext.from_storage(session.get(Project, fixture.project_id).context_data)
        require(persisted.version == context.version + 1 and persisted.values.features == ["CR1 手工修改"], "旧节点覆盖了手工 Context")
    print(json.dumps({"context_then_complete": "passed", "blocked_before_commit": True, "context_conflict": True, "fail_run_without_deadlock": True}))


def verify_completed_run_edit(factory: sessionmaker[Session], fixture: Fixture) -> None:
    with factory() as session:
        version, context = snapshot(session, fixture)
        run_id = start_run(session, fixture, version, context)
        request_id = start_node(session, fixture, run_id, version, context)
        complete_node(session, fixture, run_id, request_id, version, context)
        persisted = ProjectContext.from_storage(session.get(Project, fixture.project_id).context_data)
        run = WorkflowExecutionRepository(session).finish_run(
            run_id, expected_workflow_version=version, expected_context_version=persisted.version,
        )
        require(run.status == WorkflowRunStatus.COMPLETED, "成功节点未完成运行")
        require(session.get(WorkflowNode, fixture.node_id).status == WorkflowNodeStatus.SUCCESS, "成功节点状态未保存")
        require(edit_node(session, fixture, "运行结束后可编辑") == version + 1, "运行完成后没有恢复图编辑")
    print(json.dumps({"completed_run_edit": "passed", "completed_run": True, "edit_restored": True}))


def cleanup(factory: sessionmaker[Session], marker: str, engine: Engine) -> None:
    with factory() as session:
        owned_ids = list(session.scalars(select(User.id).where(User.username == marker)))
        if owned_ids:
            session.execute(delete(AIRequest).where(AIRequest.user_id.in_(owned_ids)))
            session.execute(delete(Project).where(Project.owner_id.in_(owned_ids)))
            session.execute(delete(User).where(User.id.in_(owned_ids), User.username == marker))
            session.commit()
        require(session.scalar(select(User.id).where(User.username == marker)) is None, "本轮虚构用户未清理")
    remaining = database_counts(engine)
    print(json.dumps({"cleanup": "passed" if not any(remaining.values()) else "remaining-data", "remaining_rows": sum(remaining.values())}))
    require(not any(remaining.values()), "隔离库仍有数据；保留现场，不扩大删除范围")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="新建的 scholarhub_l4_20261016_cr1 专用库或其下划线后缀库")
    parser.add_argument("--initialize", action="store_true", help="必传；仅首次创建不存在的专用库和现有 Models 表")
    args = parser.parse_args()
    engine = None
    marker = f"cr1_verify_{token_hex(6)}"
    try:
        engine = initialize_database(args.database, initialize=args.initialize)
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        try:
            fixture = create_fixture(factory, marker)
            verify_edit_then_start(factory, fixture)
            verify_start_then_edit(factory, fixture)
            verify_simultaneous_starts(factory, fixture)
            verify_context_then_complete(factory, fixture)
            verify_completed_run_edit(factory, fixture)
        finally:
            cleanup(factory, marker, engine)
        print(json.dumps({"cr1_mysql_concurrency": "passed", "checks": 5}))
        return 0
    except VerificationError as exc:
        print(json.dumps({"cr1_mysql_concurrency": "failed", "reason": str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:
        # DBAPI 异常可能包含 SQL 或连接信息，只公开异常类型。
        print(json.dumps({"cr1_mysql_concurrency": "failed", "error_type": type(exc).__name__}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
