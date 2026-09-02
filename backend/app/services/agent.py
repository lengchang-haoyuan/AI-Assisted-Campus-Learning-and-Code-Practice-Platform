import asyncio
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Mapping, cast

from pydantic import ValidationError

from app.agents.base import (
    AgentInputValidationError,
    AgentOutputValidationError,
    BaseAgent,
)
from app.agents.schemas import (
    AGENT_RESULT_SCHEMAS,
    AgentOutput,
    AgentSchema,
    AgentType,
)
from app.ai.provider import AIClientError
from app.context.context_schema import CORE_PROJECT_FIELD_MAP
from app.context.project_context import InvalidProjectContextError, ProjectContext
from app.core.exceptions import (
    AgentOutputError,
    ConflictError,
    InputError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.ai import AIRequest
from app.models.enums import AIRequestStatus
from app.models.project import Project
from app.repositories.agent import AgentRepository
from app.services.ai import raise_ai_application_error


@dataclass(frozen=True, slots=True)
class AgentErrorData:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class AgentRecordData:
    request_id: int
    project_id: int | None
    agent_type: AgentType
    status: AIRequestStatus
    provider: str
    model: str
    context_version: int
    result: AgentOutput | None
    error: AgentErrorData | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    requested_at: datetime
    finished_at: datetime | None


class AgentService:
    def __init__(
        self,
        repository: AgentRepository,
        agents: Mapping[AgentType, BaseAgent],
        *,
        api_key_env_name: str,
    ) -> None:
        self._repository = repository
        self._agents = dict(agents)
        self._api_key_env_name = api_key_env_name
        if set(self._agents) != set(AgentType):
            raise ValueError("AgentService 必须注册当前全部核心 Agent")

    async def run_agent(
        self,
        agent_type: AgentType,
        user_id: int,
        project_id: int,
        input_data: dict[str, object],
    ) -> AgentRecordData:
        project = self._repository.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError("项目不存在")
        if project.owner_id != user_id:
            raise PermissionDeniedError("无权对该项目运行 AI Agent")
        context = self._load_context(project.context_data)
        stale_fields = self._stale_fields(project, context)
        if stale_fields:
            raise ConflictError(
                f"项目上下文已过期，请先同步字段：{', '.join(stale_fields)}"
            )

        agent = self._agents[agent_type]
        try:
            validated_input = agent.validate_input(input_data)
        except AgentInputValidationError as exc:
            raise InputError("Agent 输入不符合当前类型要求") from exc
        canonical_input = self._canonical_json(validated_input)
        request = self._repository.create_request(
            AIRequest(
                user_id=user_id,
                project_id=project_id,
                workflow_run_id=None,
                provider=agent.provider_name,
                model=agent.model,
                request_type=agent_type.value,
                status=AIRequestStatus.RUNNING,
                input_hash=self._hash_text(canonical_input),
                input_summary=(
                    f"{agent_type.value} for project {project_id} context v{context.version}"
                ),
                request_metadata={
                    "context_version": context.version,
                    "input_bytes": len(canonical_input.encode("utf-8")),
                    "agent_rounds": 1,
                },
            )
        )

        try:
            execution = await agent.run(
                context,
                validated_input.model_dump(mode="python"),
            )
        except asyncio.CancelledError:
            self._mark_failed(
                request.id,
                error_code="cancelled",
                error_message="AI Agent 请求已取消",
            )
            raise
        except AgentInputValidationError as exc:
            self._mark_failed(
                request.id,
                error_code="agent_input_invalid",
                error_message="Agent Context 或输入超过安全边界",
            )
            raise InputError("Agent Context 或输入超过安全边界") from exc
        except AgentOutputValidationError as exc:
            self._mark_failed(
                request.id,
                error_code="agent_output_invalid",
                error_message="AI Agent 返回的结构化结果无效",
            )
            raise AgentOutputError() from exc
        except AIClientError as exc:
            self._mark_failed(
                request.id,
                error_code=exc.category.value,
                error_message="AI Provider 调用失败",
            )
            raise_ai_application_error(exc, self._api_key_env_name)
        except Exception:
            self._mark_failed(
                request.id,
                error_code="agent_internal_error",
                error_message="AI Agent 内部处理失败",
            )
            raise

        structured_result = execution.result.model_dump(mode="json")
        canonical_result = json.dumps(
            structured_result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        completed = self._repository.complete_request(
            request.id,
            result_type=execution.agent_type.value,
            structured_result=structured_result,
            text_summary=self._result_summary(execution.result),
            content_hash=self._hash_text(canonical_result),
            prompt_tokens=execution.completion.usage.prompt_tokens,
            completion_tokens=execution.completion.usage.completion_tokens,
            latency_ms=execution.completion.latency_ms,
            finish_reason=execution.completion.finish_reason,
            total_tokens=execution.completion.usage.total_tokens,
        )
        return self._to_record_data(completed)

    def get_result(self, request_id: int, user_id: int) -> AgentRecordData:
        request = self._repository.get_request_for_user(request_id, user_id)
        if request is None:
            raise ResourceNotFoundError("AI Agent 结果不存在")
        return self._to_record_data(request)

    def _mark_failed(
        self,
        request_id: int,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        self._repository.fail_request(
            request_id,
            error_code=error_code,
            error_message=error_message,
        )

    @staticmethod
    def _load_context(value: object) -> ProjectContext:
        if value is None:
            raise ResourceNotFoundError("项目上下文尚未创建")
        try:
            return ProjectContext.from_storage(value)
        except InvalidProjectContextError as exc:
            raise ConflictError("项目上下文格式无效，需要修复后重试") from exc

    @staticmethod
    def _stale_fields(project: Project, context: ProjectContext) -> list[str]:
        return sorted(
            context_field
            for context_field, project_field in CORE_PROJECT_FIELD_MAP.items()
            if getattr(project, project_field) != getattr(context.values, context_field)
        )

    @staticmethod
    def _canonical_json(value: AgentSchema) -> str:
        return json.dumps(
            value.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _hash_text(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _result_summary(result: AgentOutput) -> str:
        if hasattr(result, "summary"):
            return str(result.summary)
        if hasattr(result, "completion_summary"):
            return str(result.completion_summary)
        return str(result.title)

    @staticmethod
    def _to_record_data(request: AIRequest) -> AgentRecordData:
        try:
            agent_type = AgentType(request.request_type)
        except ValueError as exc:
            raise ConflictError("AI Agent 记录类型无效") from exc
        raw_context_version = (request.request_metadata or {}).get("context_version")
        if not isinstance(raw_context_version, int) or raw_context_version < 1:
            raise ConflictError("AI Agent 记录缺少有效 Context 版本")

        parsed_result: AgentOutput | None = None
        if request.result is not None:
            raw_result = request.result.structured_result
            if not isinstance(raw_result, dict):
                raise ConflictError("AI Agent 持久化结果格式无效")
            try:
                parsed = AGENT_RESULT_SCHEMAS[agent_type].model_validate(raw_result)
            except ValidationError as exc:
                raise ConflictError("AI Agent 持久化结果格式无效") from exc
            parsed_result = cast(AgentOutput, parsed)
        elif request.status == AIRequestStatus.COMPLETED:
            raise ConflictError("AI Agent 已完成记录缺少结果")

        error = None
        if request.error_code is not None:
            error = AgentErrorData(
                code=request.error_code,
                message=request.error_message or "AI Agent 运行失败",
            )
        return AgentRecordData(
            request_id=request.id,
            project_id=request.project_id,
            agent_type=agent_type,
            status=request.status,
            provider=request.provider,
            model=request.model,
            context_version=raw_context_version,
            result=parsed_result,
            error=error,
            prompt_tokens=request.prompt_tokens,
            completion_tokens=request.completion_tokens,
            latency_ms=request.latency_ms,
            requested_at=request.requested_at,
            finished_at=request.finished_at,
        )
