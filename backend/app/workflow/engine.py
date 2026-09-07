import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
import heapq
import json
import logging
from time import perf_counter
from typing import Any, cast

from pydantic import ValidationError

from app.agents.base import AgentInputValidationError, AgentOutputValidationError
from app.ai.provider import AIClientError
from app.context.context_manager import (
    ContextAccessError,
    ContextEdge,
    ContextManager,
    ContextMergeResult,
    ContextNode,
    InvalidContextPolicyError,
)
from app.context.context_schema import (
    CORE_PROJECT_FIELD_MAP,
    ContextSource,
    ContextSourceType,
)
from app.context.project_context import InvalidProjectContextError, ProjectContext
from app.core.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.enums import WorkflowNodeStatus
from app.models.workflow import Workflow, WorkflowNode, WorkflowRun
from app.repositories.workflow_execution import (
    WorkflowActiveRunError,
    WorkflowExecutionPersistenceError,
    WorkflowExecutionRepository,
    WorkflowExecutionVersionError,
    WorkflowRunStateError,
)
from app.workflow.registry import (
    WorkflowAgentNotFoundError,
    WorkflowAgentRegistry,
    WorkflowAgentRegistrationError,
)
from app.workflow.schemas import (
    WORKFLOW_NODE_RESULT_SCHEMAS,
    ArchitectureDesignNodeResult,
    RequirementsAnalysisNodeResult,
    TechStackAnalysisNodeResult,
    WorkflowNodeInput,
    WorkflowNodeResult,
    TeachingNodeInput,
    CodeTeachingNodeInput,
    ExerciseHintNodeResult,
    CodeExplanationNodeResult,
    AnswerReviewNodeResult,
)

MIN_NODE_COMPLETION_TOKENS = 256


class WorkflowRunMode(StrEnum):
    INCOMPLETE = "incomplete"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class WorkflowEngineLimits:
    max_nodes: int
    max_rounds: int
    max_node_tokens: int
    max_completion_tokens: int
    total_timeout_seconds: float
    recovery_timeout_seconds: float
    max_concurrency: int = 1

    def __post_init__(self) -> None:
        if self.max_nodes < 1 or self.max_rounds < 1:
            raise ValueError("Workflow 节点和回合上限必须大于 0")
        if self.max_node_tokens < MIN_NODE_COMPLETION_TOKENS:
            raise ValueError("节点 Token 上限过小")
        if self.max_completion_tokens < MIN_NODE_COMPLETION_TOKENS:
            raise ValueError("Workflow Token 预算过小")
        if self.total_timeout_seconds <= 0 or self.recovery_timeout_seconds <= 0:
            raise ValueError("Workflow 超时必须大于 0")
        if self.max_concurrency != 1:
            raise ValueError("当前 Context 写入模型只支持顺序执行")


@dataclass(frozen=True, slots=True)
class WorkflowExecutionPlan:
    ordered_node_ids: tuple[int, ...]
    selected_node_ids: frozenset[int]
    predecessors: dict[int, frozenset[int]]


class WorkflowEngine:
    def __init__(
        self,
        repository: WorkflowExecutionRepository,
        registry: WorkflowAgentRegistry,
        context_manager: ContextManager,
        limits: WorkflowEngineLimits,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._context_manager = context_manager
        self._limits = limits
        self._logger = logging.getLogger("scholarhub.workflow")

    async def run(
        self,
        workflow_id: int,
        user_id: int,
        *,
        expected_version: int,
        mode: WorkflowRunMode,
    ) -> WorkflowRun:
        workflow = self._get_owned_workflow(workflow_id, user_id)
        if workflow.version != expected_version:
            raise ConflictError("工作流已被更新，请刷新后重试")
        context = self._load_context(workflow)
        stale_fields = self._stale_project_fields(workflow, context)
        if stale_fields:
            raise ConflictError(
                f"项目上下文已过期，请先同步字段：{', '.join(stale_fields)}"
            )
        plan = self._build_plan(workflow, mode)
        node_inputs = {
            node.id: self._node_input(node, workflow.project.description)
            for node in workflow.nodes
            if node.id in plan.selected_node_ids
        }

        stale_before = datetime.now(UTC) - timedelta(
            seconds=self._limits.recovery_timeout_seconds
        )
        try:
            run = self._repository.start_run(
                workflow_id,
                user_id,
                expected_version=expected_version,
                context_snapshot=context.to_storage(),
                stale_before=stale_before,
            )
        except WorkflowActiveRunError as exc:
            raise ConflictError("工作流已有运行中的任务") from exc
        except WorkflowExecutionVersionError as exc:
            raise ConflictError("工作流已被更新，请刷新后重试") from exc
        except WorkflowRunStateError as exc:
            raise ResourceNotFoundError("工作流不存在") from exc
        except WorkflowExecutionPersistenceError as exc:
            raise ConflictError("工作流当前无法开始运行") from exc

        run_started = perf_counter()
        current_node_id: int | None = None
        current_request_id: int | None = None
        completion_tokens_used = 0
        status_by_id = {node.id: node.status for node in workflow.nodes}
        nodes_by_id = {node.id: node for node in workflow.nodes}
        context_nodes = [self._context_node(node) for node in workflow.nodes]
        context_edges = [
            ContextEdge(edge.source_node_id, edge.target_node_id)
            for edge in workflow.edges
        ]
        self._log_run(
            "workflow_run_started",
            run,
            status="running",
            termination_reason=None,
            total_tokens=0,
            latency_ms=0,
        )

        try:
            async with asyncio.timeout(self._limits.total_timeout_seconds):
                for node_id in plan.ordered_node_ids:
                    if node_id not in plan.selected_node_ids:
                        continue
                    current_node_id = node_id
                    current_request_id = None
                    node = nodes_by_id[node_id]
                    unmet = [
                        predecessor
                        for predecessor in plan.predecessors[node_id]
                        if status_by_id[predecessor] != WorkflowNodeStatus.SUCCESS
                    ]
                    if unmet:
                        return self._fail_run(
                            run,
                            node_id=current_node_id,
                            request_id=None,
                            error_code="dependency_not_ready",
                            error_message="节点依赖尚未成功",
                            started_at=run_started,
                            total_tokens=completion_tokens_used,
                        )

                    remaining_tokens = (
                        self._limits.max_completion_tokens - completion_tokens_used
                    )
                    if remaining_tokens < MIN_NODE_COMPLETION_TOKENS:
                        return self._fail_run(
                            run,
                            node_id=current_node_id,
                            request_id=None,
                            error_code="budget_exhausted",
                            error_message="Workflow 模型 Token 预算已耗尽",
                            started_at=run_started,
                            total_tokens=completion_tokens_used,
                        )
                    node_max_tokens = min(
                        self._limits.max_node_tokens, remaining_tokens
                    )
                    agent = self._registry.create(
                        node.node_type, max_tokens=node_max_tokens
                    )
                    validated_input = agent.validate_input(
                        node_inputs[node_id].model_dump(mode="python")
                    )
                    canonical_input = self._canonical_json(validated_input.model_dump(mode="json"))
                    request = self._repository.start_node(
                        run.id,
                        node.id,
                        user_id=user_id,
                        project_id=workflow.project_id,
                        provider=agent.provider_name,
                        model=agent.model,
                        node_type=node.node_type,
                        node_key=node.node_key,
                        input_hash=self._hash_text(canonical_input),
                        input_bytes=len(canonical_input.encode("utf-8")),
                        context_version=context.version,
                    )
                    current_request_id = request.id
                    status_by_id[node_id] = WorkflowNodeStatus.RUNNING
                    self._log_node(
                        "workflow_node_started",
                        run.id,
                        node,
                        status="running",
                        latency_ms=0,
                        failure_category=None,
                    )

                    execution = await agent.run(
                        context,
                        validated_input.model_dump(mode="python"),
                    )
                    result_schema = WORKFLOW_NODE_RESULT_SCHEMAS[node.node_type]
                    result = cast(
                        WorkflowNodeResult,
                        result_schema.model_validate(
                            execution.result.model_dump(mode="python")
                        ),
                    )
                    consumed_tokens = (
                        execution.completion.usage.completion_tokens
                        if execution.completion.usage.completion_tokens is not None
                        else node_max_tokens
                    )
                    completion_tokens_used += consumed_tokens
                    if completion_tokens_used > self._limits.max_completion_tokens:
                        return self._fail_run(
                            run,
                            node_id=current_node_id,
                            request_id=current_request_id,
                            error_code="budget_exhausted",
                            error_message="Workflow 模型 Token 预算已耗尽",
                            started_at=run_started,
                            total_tokens=completion_tokens_used,
                        )

                    updates = self._context_updates(result)
                    descriptor = self._context_node(node)
                    merged = ContextMergeResult(context, frozenset())
                    if updates:
                        patch = self._context_manager.validate_node_write(
                            descriptor, updates
                        )
                        merged = self._context_manager.merge(
                            context,
                            patch.model_dump(exclude_unset=True),
                            source=ContextSource(
                                type=ContextSourceType.WORKFLOW_NODE,
                                id=node.id,
                                node_key=node.node_key,
                            ),
                        )
                    stale_node_ids = self._context_manager.stale_node_ids(
                        context_nodes,
                        context_edges,
                        merged.changed_fields,
                        source_node_id=node.id,
                    )
                    structured_result = result.model_dump(mode="json")
                    canonical_result = self._canonical_json(structured_result)
                    self._repository.complete_node(
                        run.id,
                        node.id,
                        request.id,
                        expected_context_version=context.version,
                        context=merged.context,
                        changed_fields=merged.changed_fields,
                        stale_node_ids=stale_node_ids,
                        structured_result=structured_result,
                        result_type=node.node_type,
                        text_summary=result.summary,
                        content_hash=self._hash_text(canonical_result),
                        prompt_tokens=execution.completion.usage.prompt_tokens,
                        completion_tokens=execution.completion.usage.completion_tokens,
                        latency_ms=execution.completion.latency_ms,
                        finish_reason=execution.completion.finish_reason,
                        total_tokens=execution.completion.usage.total_tokens,
                    )
                    context = merged.context
                    for stale_node_id in stale_node_ids:
                        status_by_id[stale_node_id] = WorkflowNodeStatus.STALE
                    status_by_id[node_id] = WorkflowNodeStatus.SUCCESS
                    self._log_node(
                        "workflow_node_finished",
                        run.id,
                        node,
                        status="success",
                        latency_ms=execution.completion.latency_ms,
                        failure_category=None,
                    )
                    current_node_id = None
                    current_request_id = None

                completed = self._repository.finish_run(run.id)
                self._log_run(
                    "workflow_run_finished",
                    completed,
                    status="completed",
                    termination_reason="completed",
                    total_tokens=completion_tokens_used,
                    latency_ms=self._elapsed_ms(run_started),
                )
                return completed
        except asyncio.CancelledError:
            cancelled = self._repository.fail_run(
                run.id,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="cancelled",
                error_message="WorkflowRun 已取消",
                cancelled=True,
            )
            self._log_run(
                "workflow_run_finished",
                cancelled,
                status="cancelled",
                termination_reason="cancelled",
                total_tokens=completion_tokens_used,
                latency_ms=self._elapsed_ms(run_started),
            )
            raise
        except TimeoutError:
            return self._fail_run(
                run,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="workflow_timeout",
                error_message="WorkflowRun 超过总超时",
                started_at=run_started,
                total_tokens=completion_tokens_used,
            )
        except AgentInputValidationError:
            return self._fail_run(
                run,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="agent_input_invalid",
                error_message="节点输入超过 Agent 安全边界",
                started_at=run_started,
                total_tokens=completion_tokens_used,
            )
        except AgentOutputValidationError:
            return self._fail_run(
                run,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="agent_output_invalid",
                error_message="节点 Agent 返回的结构化结果无效",
                started_at=run_started,
                total_tokens=completion_tokens_used,
            )
        except AIClientError as exc:
            return self._fail_run(
                run,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code=exc.category.value,
                error_message="AI Provider 调用失败",
                started_at=run_started,
                total_tokens=completion_tokens_used,
            )
        except (ContextAccessError, InvalidContextPolicyError, ValidationError):
            return self._fail_run(
                run,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="context_update_invalid",
                error_message="节点结果无法安全更新 ProjectContext",
                started_at=run_started,
                total_tokens=completion_tokens_used,
            )
        except WorkflowExecutionVersionError:
            return self._fail_run(
                run,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="context_version_conflict",
                error_message="ProjectContext 已被并发修改",
                started_at=run_started,
                total_tokens=completion_tokens_used,
            )
        except (WorkflowRunStateError, WorkflowExecutionPersistenceError):
            return self._fail_run(
                run,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="workflow_state_conflict",
                error_message="WorkflowRun 状态与当前执行冲突",
                started_at=run_started,
                total_tokens=completion_tokens_used,
            )
        except (WorkflowAgentNotFoundError, WorkflowAgentRegistrationError):
            return self._fail_run(
                run,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="node_type_unavailable",
                error_message="工作流节点类型当前不可执行",
                started_at=run_started,
                total_tokens=completion_tokens_used,
            )
        except Exception:
            self._repository.fail_run(
                run.id,
                node_id=current_node_id,
                request_id=current_request_id,
                error_code="workflow_internal_error",
                error_message="WorkflowRun 内部处理失败",
            )
            raise

    def _build_plan(
        self, workflow: Workflow, mode: WorkflowRunMode
    ) -> WorkflowExecutionPlan:
        nodes = sorted(workflow.nodes, key=lambda item: item.id)
        if not nodes:
            raise ConflictError("空工作流不能运行")
        if len(nodes) > self._limits.max_nodes:
            raise ConflictError(
                f"可执行工作流节点不能超过 {self._limits.max_nodes} 个"
            )
        unsupported = sorted(
            {node.node_type for node in nodes} - self._registry.registered_types
        )
        if unsupported:
            raise ConflictError(f"存在未注册节点类型：{', '.join(unsupported)}")

        node_ids = {node.id for node in nodes}
        adjacency = {node.id: [] for node in nodes}
        predecessors: dict[int, set[int]] = {node.id: set() for node in nodes}
        edge_pairs: set[tuple[int, int]] = set()
        for edge in workflow.edges:
            pair = (edge.source_node_id, edge.target_node_id)
            if (
                pair in edge_pairs
                or pair[0] == pair[1]
                or pair[0] not in node_ids
                or pair[1] not in node_ids
            ):
                raise ConflictError("工作流图包含非法边")
            if edge.condition_data:
                raise ConflictError("P13 暂不执行带条件的边")
            edge_pairs.add(pair)
            adjacency[pair[0]].append(pair[1])
            predecessors[pair[1]].add(pair[0])

        in_degree = {node_id: len(predecessors[node_id]) for node_id in node_ids}
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        heapq.heapify(queue)
        ordered: list[int] = []
        while queue:
            node_id = heapq.heappop(queue)
            ordered.append(node_id)
            for target_id in sorted(adjacency[node_id]):
                in_degree[target_id] -= 1
                if in_degree[target_id] == 0:
                    heapq.heappush(queue, target_id)
        if len(ordered) != len(nodes):
            raise ConflictError("工作流不允许形成循环")

        if mode == WorkflowRunMode.ALL:
            selected = set(node_ids)
        else:
            selected = {
                node.id
                for node in nodes
                if node.status != WorkflowNodeStatus.SUCCESS
            }
            queue_ids = list(selected)
            while queue_ids:
                source_id = queue_ids.pop()
                for target_id in adjacency[source_id]:
                    if target_id not in selected:
                        selected.add(target_id)
                        queue_ids.append(target_id)
        if not selected:
            raise ConflictError("工作流没有需要执行或重新生成的节点")
        if len(selected) > self._limits.max_rounds:
            raise ConflictError(
                f"单次 WorkflowRun 不能超过 {self._limits.max_rounds} 个模型回合"
            )
        return WorkflowExecutionPlan(
            ordered_node_ids=tuple(ordered),
            selected_node_ids=frozenset(selected),
            predecessors={
                node_id: frozenset(values)
                for node_id, values in predecessors.items()
            },
        )

    def _get_owned_workflow(self, workflow_id: int, user_id: int) -> Workflow:
        workflow = self._repository.get_workflow(workflow_id)
        if workflow is None:
            raise ResourceNotFoundError("工作流不存在")
        if workflow.project.owner_id != user_id:
            raise PermissionDeniedError("无权运行该工作流")
        return workflow

    @staticmethod
    def _load_context(workflow: Workflow) -> ProjectContext:
        if workflow.project.context_data is None:
            raise ResourceNotFoundError("项目上下文尚未创建")
        try:
            return ProjectContext.from_storage(workflow.project.context_data)
        except InvalidProjectContextError as exc:
            raise ConflictError("项目上下文格式无效，需要修复后重试") from exc

    @staticmethod
    def _stale_project_fields(
        workflow: Workflow, context: ProjectContext
    ) -> list[str]:
        return sorted(
            context_field
            for context_field, project_field in CORE_PROJECT_FIELD_MAP.items()
            if getattr(workflow.project, project_field)
            != getattr(context.values, context_field)
        )

    @staticmethod
    def _node_input(node: WorkflowNode, project_description: str | None = None) -> WorkflowNodeInput:
        config = node.config or {}
        try:
            if node.node_type in {"exercise_hint", "code_explanation", "answer_review"}:
                schema = TeachingNodeInput if node.node_type == "exercise_hint" else CodeTeachingNodeInput
                return schema.model_validate({
                    "instruction": config.get("instruction"),
                    "expected_output": config.get("expected_output"),
                    "problem": config.get("problem") or project_description or "",
                    "student_code": config.get("student_code"),
                })
            return WorkflowNodeInput.model_validate(
                {
                    "instruction": config.get("instruction"),
                    "expected_output": config.get("expected_output"),
                }
            )
        except ValidationError as exc:
            raise ConflictError(f"节点“{node.name}”配置无效，请检查题目、代码及文字长度") from exc

    @staticmethod
    def _context_node(node: WorkflowNode) -> ContextNode:
        return ContextNode(id=node.id, node_type=node.node_type, config=node.config)

    @staticmethod
    def _context_updates(result: WorkflowNodeResult) -> dict[str, object]:
        if isinstance(result, (ExerciseHintNodeResult, CodeExplanationNodeResult, AnswerReviewNodeResult)):
            # 教学输出由已有节点结果和运行记录保存，不改写项目需求与技术栈。
            return {}
        if isinstance(result, RequirementsAnalysisNodeResult):
            return {
                "requirements": [
                    item.model_dump(mode="json") for item in result.requirements
                ],
                "features": list(result.features),
                "constraints": list(result.constraints),
            }
        if isinstance(result, TechStackAnalysisNodeResult):
            return {
                "language": result.language.value,
                "framework": result.framework.value,
                "frontend": result.frontend.value,
                "backend": result.backend.value,
                "database": result.database.value,
            }
        if isinstance(result, ArchitectureDesignNodeResult):
            return {
                "architecture": {
                    "style": result.style,
                    "components": [
                        component.model_dump(mode="json")
                        for component in result.components
                    ],
                    "data_flows": [
                        flow.model_dump(mode="json") for flow in result.data_flows
                    ],
                    "decisions": [
                        decision.model_dump(mode="json")
                        for decision in result.decisions
                    ],
                }
            }
        raise TypeError("未知 Workflow 节点结果")

    def _fail_run(
        self,
        run: WorkflowRun,
        *,
        node_id: int | None,
        request_id: int | None,
        error_code: str,
        error_message: str,
        started_at: float,
        total_tokens: int,
    ) -> WorkflowRun:
        failed = self._repository.fail_run(
            run.id,
            node_id=node_id,
            request_id=request_id,
            error_code=error_code,
            error_message=error_message,
        )
        if node_id is not None:
            self._logger.warning(
                "workflow_node_finished",
                extra={
                    "workflow_run_id": run.id,
                    "node_id": node_id,
                    "status": "failed",
                    "latency_ms": self._elapsed_ms(started_at),
                    "failure_category": error_code,
                },
            )
        self._log_run(
            "workflow_run_finished",
            failed,
            status="failed",
            termination_reason=error_code,
            total_tokens=total_tokens,
            latency_ms=self._elapsed_ms(started_at),
        )
        return failed

    def _log_node(
        self,
        message: str,
        run_id: int,
        node: WorkflowNode,
        *,
        status: str,
        latency_ms: int,
        failure_category: str | None,
    ) -> None:
        self._logger.info(
            message,
            extra={
                "workflow_run_id": run_id,
                "node_id": node.id,
                "node_key": node.node_key,
                "status": status,
                "latency_ms": latency_ms,
                "failure_category": failure_category,
            },
        )

    def _log_run(
        self,
        message: str,
        run: WorkflowRun,
        *,
        status: str,
        termination_reason: str | None,
        total_tokens: int,
        latency_ms: int,
    ) -> None:
        level = logging.INFO if status in {"running", "completed"} else logging.WARNING
        self._logger.log(
            level,
            message,
            extra={
                "workflow_run_id": run.id,
                "status": status,
                "latency_ms": latency_ms,
                "termination_reason": termination_reason,
                "total_tokens": total_tokens,
            },
        )

    @staticmethod
    def _canonical_json(value: dict[str, Any]) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _hash_text(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, round((perf_counter() - started_at) * 1000))
