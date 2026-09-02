from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.context.context_schema import CORE_PROJECT_FIELD_MAP
from app.context.project_context import InvalidProjectContextError, ProjectContext
from app.models.ai import AIRequest, AIResult
from app.models.enums import (
    AIRequestStatus,
    WorkflowNodeStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from app.models.project import Project
from app.models.workflow import Workflow, WorkflowNode, WorkflowRun


class WorkflowExecutionPersistenceError(Exception):
    """Workflow 执行状态无法按数据库约束保存。"""


class WorkflowExecutionVersionError(Exception):
    """执行使用的 Workflow 或 Context 版本已过期。"""


class WorkflowActiveRunError(Exception):
    """同一个 Workflow 已存在未过期的运行。"""


class WorkflowRunStateError(Exception):
    """WorkflowRun 或节点已不在允许的状态。"""


class WorkflowExecutionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_workflow(self, workflow_id: int) -> Workflow | None:
        statement = (
            self._workflow_query()
            .where(Workflow.id == workflow_id)
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def start_run(
        self,
        workflow_id: int,
        user_id: int,
        *,
        expected_version: int,
        context_snapshot: dict[str, Any],
        stale_before: datetime,
    ) -> WorkflowRun:
        try:
            workflow = self._session.scalar(
                select(Workflow)
                .where(Workflow.id == workflow_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workflow is None:
                raise WorkflowRunStateError("工作流不存在")
            if workflow.version != expected_version:
                raise WorkflowExecutionVersionError

            active_runs = list(
                self._session.scalars(
                    select(WorkflowRun)
                    .where(
                        WorkflowRun.workflow_id == workflow_id,
                        WorkflowRun.status == WorkflowRunStatus.RUNNING,
                    )
                    .order_by(WorkflowRun.id)
                    .with_for_update()
                )
            )
            for active_run in active_runs:
                if active_run.started_at is not None and active_run.started_at > stale_before:
                    raise WorkflowActiveRunError
                self._recover_abandoned_run(active_run)

            self._session.execute(
                update(WorkflowNode)
                .where(
                    WorkflowNode.workflow_id == workflow_id,
                    WorkflowNode.status == WorkflowNodeStatus.RUNNING,
                )
                .values(status=WorkflowNodeStatus.STALE)
            )

            now = datetime.now(UTC)
            run = WorkflowRun(
                workflow_id=workflow_id,
                started_by_id=user_id,
                status=WorkflowRunStatus.RUNNING,
                context_snapshot=context_snapshot,
                started_at=now,
            )
            workflow.status = WorkflowStatus.RUNNING
            self._session.add(run)
            self._session.commit()
            return self._reload_run(run.id)
        except (
            WorkflowActiveRunError,
            WorkflowExecutionVersionError,
            WorkflowRunStateError,
        ):
            self._session.rollback()
            raise
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkflowExecutionPersistenceError from exc

    def start_node(
        self,
        run_id: int,
        node_id: int,
        *,
        user_id: int,
        project_id: int,
        provider: str,
        model: str,
        node_type: str,
        node_key: str,
        input_hash: str,
        input_bytes: int,
        context_version: int,
    ) -> AIRequest:
        try:
            run = self._required_run(run_id, for_update=True)
            node = self._required_node(node_id, for_update=True)
            if run.status != WorkflowRunStatus.RUNNING:
                raise WorkflowRunStateError("WorkflowRun 已不是运行状态")
            if node.workflow_id != run.workflow_id:
                raise WorkflowRunStateError("节点不属于当前 WorkflowRun")
            if node.status == WorkflowNodeStatus.RUNNING:
                raise WorkflowRunStateError("节点已在运行")

            node.status = WorkflowNodeStatus.RUNNING
            request = AIRequest(
                user_id=user_id,
                project_id=project_id,
                workflow_run_id=run_id,
                provider=provider,
                model=model,
                request_type=node_type,
                status=AIRequestStatus.RUNNING,
                input_hash=input_hash,
                input_summary=(
                    f"{node_type} for workflow {run.workflow_id} run {run_id}"
                ),
                request_metadata={
                    "context_version": context_version,
                    "input_bytes": input_bytes,
                    "agent_rounds": 1,
                    "node_id": node_id,
                    "node_key": node_key,
                },
            )
            self._session.add(request)
            self._session.commit()
            return self._reload_request(request.id)
        except WorkflowRunStateError:
            self._session.rollback()
            raise
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkflowExecutionPersistenceError from exc

    def complete_node(
        self,
        run_id: int,
        node_id: int,
        request_id: int,
        *,
        expected_context_version: int,
        context: ProjectContext,
        changed_fields: frozenset[str],
        stale_node_ids: frozenset[int],
        structured_result: dict[str, Any],
        result_type: str,
        text_summary: str,
        content_hash: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        latency_ms: int,
        finish_reason: str | None,
        total_tokens: int | None,
    ) -> None:
        try:
            run = self._required_run(run_id, for_update=True)
            node = self._required_node(node_id, for_update=True)
            request = self._required_request(request_id, for_update=True)
            workflow = self._required_workflow(run.workflow_id, for_update=True)
            project = self._required_project(workflow.project_id, for_update=True)
            if (
                run.status != WorkflowRunStatus.RUNNING
                or node.status != WorkflowNodeStatus.RUNNING
                or request.status != AIRequestStatus.RUNNING
            ):
                raise WorkflowRunStateError("节点完成时运行状态已改变")
            if request.workflow_run_id != run_id or node.workflow_id != run.workflow_id:
                raise WorkflowRunStateError("节点请求关联不一致")

            try:
                persisted_context = ProjectContext.from_storage(project.context_data)
            except InvalidProjectContextError as exc:
                raise WorkflowExecutionVersionError from exc
            if persisted_context.version != expected_context_version:
                raise WorkflowExecutionVersionError

            project.context_data = context.to_storage()
            context_values = context.values.model_dump(mode="python")
            for context_field, project_field in CORE_PROJECT_FIELD_MAP.items():
                if context_field in changed_fields:
                    setattr(project, project_field, context_values[context_field])

            stale_nodes = list(
                self._session.scalars(
                    select(WorkflowNode)
                    .where(
                        WorkflowNode.workflow_id == run.workflow_id,
                        WorkflowNode.id.in_(stale_node_ids or {-1}),
                    )
                    .with_for_update()
                )
            )
            for stale_node in stale_nodes:
                if stale_node.id != node_id:
                    stale_node.status = WorkflowNodeStatus.STALE

            node.status = WorkflowNodeStatus.SUCCESS
            node.context_version = context.version
            node.output_data = {
                "run_id": run_id,
                "request_id": request_id,
                "context_version": context.version,
                "changed_fields": sorted(changed_fields),
                "result": structured_result,
            }
            request.status = AIRequestStatus.COMPLETED
            request.prompt_tokens = prompt_tokens
            request.completion_tokens = completion_tokens
            request.latency_ms = latency_ms
            request.finished_at = datetime.now(UTC)
            request.error_code = None
            request.error_message = None
            metadata = dict(request.request_metadata or {})
            metadata.update(
                {"finish_reason": finish_reason, "total_tokens": total_tokens}
            )
            request.request_metadata = metadata
            self._session.add(
                AIResult(
                    request_id=request_id,
                    result_type=result_type,
                    structured_result=structured_result,
                    text_summary=text_summary,
                    content_hash=content_hash,
                )
            )
            self._session.commit()
        except (
            WorkflowExecutionVersionError,
            WorkflowRunStateError,
        ):
            self._session.rollback()
            raise
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkflowExecutionPersistenceError from exc

    def finish_run(self, run_id: int) -> WorkflowRun:
        try:
            run = self._required_run(run_id, for_update=True)
            workflow = self._required_workflow(run.workflow_id, for_update=True)
            if run.status != WorkflowRunStatus.RUNNING:
                raise WorkflowRunStateError("WorkflowRun 已不是运行状态")
            node_statuses = list(
                self._session.scalars(
                    select(WorkflowNode.status).where(
                        WorkflowNode.workflow_id == workflow.id
                    )
                )
            )
            run.status = WorkflowRunStatus.COMPLETED
            run.finished_at = datetime.now(UTC)
            workflow.status = (
                WorkflowStatus.COMPLETED
                if node_statuses
                and all(status == WorkflowNodeStatus.SUCCESS for status in node_statuses)
                else WorkflowStatus.STALE
            )
            self._session.commit()
            return self._reload_run(run_id)
        except WorkflowRunStateError:
            self._session.rollback()
            raise
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkflowExecutionPersistenceError from exc

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
        try:
            run = self._required_run(run_id, for_update=True)
            workflow = self._required_workflow(run.workflow_id, for_update=True)
            if run.status not in {
                WorkflowRunStatus.RUNNING,
                WorkflowRunStatus.PENDING,
            }:
                self._session.rollback()
                return self._reload_run(run_id)
            now = datetime.now(UTC)
            if node_id is not None:
                node = self._required_node(node_id, for_update=True)
                node.status = (
                    WorkflowNodeStatus.STALE
                    if cancelled
                    else WorkflowNodeStatus.FAILED
                )
            if request_id is not None:
                request = self._required_request(request_id, for_update=True)
                if request.status == AIRequestStatus.RUNNING:
                    request.status = AIRequestStatus.FAILED
                    request.error_code = error_code
                    request.error_message = error_message
                    request.finished_at = now
            run.status = (
                WorkflowRunStatus.CANCELLED
                if cancelled
                else WorkflowRunStatus.FAILED
            )
            run.error_code = error_code
            run.error_message = error_message
            run.finished_at = now
            workflow.status = (
                WorkflowStatus.STALE if cancelled else WorkflowStatus.FAILED
            )
            self._session.commit()
            return self._reload_run(run_id)
        except WorkflowRunStateError:
            self._session.rollback()
            raise
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkflowExecutionPersistenceError from exc

    def count_runs(self, workflow_id: int) -> int:
        return self._session.scalar(
            select(func.count(WorkflowRun.id)).where(
                WorkflowRun.workflow_id == workflow_id
            )
        ) or 0

    def list_runs(
        self, workflow_id: int, *, offset: int, limit: int
    ) -> list[WorkflowRun]:
        statement = (
            self._run_query()
            .where(WorkflowRun.workflow_id == workflow_id)
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement).unique())

    def get_run(self, workflow_id: int, run_id: int) -> WorkflowRun | None:
        statement = (
            self._run_query()
            .where(
                WorkflowRun.id == run_id,
                WorkflowRun.workflow_id == workflow_id,
            )
            .execution_options(populate_existing=True)
        )
        return self._session.scalar(statement)

    def _recover_abandoned_run(self, run: WorkflowRun) -> None:
        now = datetime.now(UTC)
        run.status = WorkflowRunStatus.FAILED
        run.error_code = "recovered_timeout"
        run.error_message = "上一次 WorkflowRun 已超时并由新运行恢复"
        run.finished_at = now
        self._session.execute(
            update(AIRequest)
            .where(
                AIRequest.workflow_run_id == run.id,
                AIRequest.status == AIRequestStatus.RUNNING,
            )
            .values(
                status=AIRequestStatus.FAILED,
                error_code="recovered_timeout",
                error_message="WorkflowRun 超时恢复",
                finished_at=now,
            )
        )
        self._session.execute(
            update(WorkflowNode)
            .where(
                WorkflowNode.workflow_id == run.workflow_id,
                WorkflowNode.status == WorkflowNodeStatus.RUNNING,
            )
            .values(status=WorkflowNodeStatus.STALE)
        )

    def _required_run(self, run_id: int, *, for_update: bool) -> WorkflowRun:
        statement = select(WorkflowRun).where(WorkflowRun.id == run_id)
        if for_update:
            statement = statement.with_for_update()
        run = self._session.scalar(statement.execution_options(populate_existing=True))
        if run is None:
            raise WorkflowRunStateError("WorkflowRun 不存在")
        return run

    def _required_workflow(self, workflow_id: int, *, for_update: bool) -> Workflow:
        statement = select(Workflow).where(Workflow.id == workflow_id)
        if for_update:
            statement = statement.with_for_update()
        workflow = self._session.scalar(
            statement.execution_options(populate_existing=True)
        )
        if workflow is None:
            raise WorkflowRunStateError("工作流不存在")
        return workflow

    def _required_project(self, project_id: int, *, for_update: bool) -> Project:
        statement = select(Project).where(Project.id == project_id)
        if for_update:
            statement = statement.with_for_update()
        project = self._session.scalar(
            statement.execution_options(populate_existing=True)
        )
        if project is None:
            raise WorkflowRunStateError("项目不存在")
        return project

    def _required_node(self, node_id: int, *, for_update: bool) -> WorkflowNode:
        statement = select(WorkflowNode).where(WorkflowNode.id == node_id)
        if for_update:
            statement = statement.with_for_update()
        node = self._session.scalar(statement.execution_options(populate_existing=True))
        if node is None:
            raise WorkflowRunStateError("工作流节点不存在")
        return node

    def _required_request(self, request_id: int, *, for_update: bool) -> AIRequest:
        statement = select(AIRequest).where(AIRequest.id == request_id)
        if for_update:
            statement = statement.with_for_update()
        request = self._session.scalar(
            statement.execution_options(populate_existing=True)
        )
        if request is None:
            raise WorkflowRunStateError("AIRequest 不存在")
        return request

    def _reload_run(self, run_id: int) -> WorkflowRun:
        statement = (
            self._run_query()
            .where(WorkflowRun.id == run_id)
            .execution_options(populate_existing=True)
        )
        run = self._session.scalar(statement)
        if run is None:
            raise RuntimeError("WorkflowRun 保存后无法重新加载")
        return run

    def _reload_request(self, request_id: int) -> AIRequest:
        statement = (
            select(AIRequest)
            .options(joinedload(AIRequest.result))
            .where(AIRequest.id == request_id)
            .execution_options(populate_existing=True)
        )
        request = self._session.scalar(statement)
        if request is None:
            raise RuntimeError("AIRequest 保存后无法重新加载")
        return request

    @staticmethod
    def _workflow_query():
        return select(Workflow).options(
            joinedload(Workflow.project),
            selectinload(Workflow.nodes),
            selectinload(Workflow.edges),
        )

    @staticmethod
    def _run_query():
        return select(WorkflowRun).options(
            joinedload(WorkflowRun.workflow).joinedload(Workflow.project),
            selectinload(WorkflowRun.ai_requests).joinedload(AIRequest.result),
        )
