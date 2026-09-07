from typing import Annotated

from fastapi import APIRouter, Path, status

from app.agents.schemas import AgentType
from app.api.deps import AgentServiceDependency, CurrentUser
from app.schemas.agent import (
    AgentErrorResponse,
    AgentRecordResponse,
    AgentUsageResponse,
    ProjectAnalysisRunRequest,
    ProjectReviewRunRequest,
    PromptAgentRunRequest,
)
from app.services.agent import AgentRecordData

router = APIRouter(prefix="/agents", tags=["agents"])
RequestId = Annotated[int, Path(ge=1)]


def to_agent_record_response(data: AgentRecordData) -> AgentRecordResponse:
    return AgentRecordResponse(
        request_id=data.request_id,
        project_id=data.project_id,
        agent_type=data.agent_type,
        status=data.status,
        provider=data.provider,
        model=data.model,
        context_version=data.context_version,
        result=data.result,
        error=(
            AgentErrorResponse(code=data.error.code, message=data.error.message)
            if data.error is not None
            else None
        ),
        usage=AgentUsageResponse(
            prompt_tokens=data.prompt_tokens,
            completion_tokens=data.completion_tokens,
            latency_ms=data.latency_ms,
        ),
        requested_at=data.requested_at,
        finished_at=data.finished_at,
    )


@router.post(
    "/project-analysis",
    response_model=AgentRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="运行项目分析 Agent",
)
async def run_project_analysis_agent(
    payload: ProjectAnalysisRunRequest,
    current_user: CurrentUser,
    service: AgentServiceDependency,
) -> AgentRecordResponse:
    return to_agent_record_response(
        await service.run_agent(
            AgentType.PROJECT_ANALYSIS,
            current_user.id,
            payload.project_id,
            payload.input.model_dump(mode="python"),
        )
    )


@router.post(
    "/prompt",
    response_model=AgentRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="运行开发 Prompt Agent",
)
async def run_prompt_agent(
    payload: PromptAgentRunRequest,
    current_user: CurrentUser,
    service: AgentServiceDependency,
) -> AgentRecordResponse:
    return to_agent_record_response(
        await service.run_agent(
            AgentType.PROMPT,
            current_user.id,
            payload.project_id,
            payload.input.model_dump(mode="python"),
        )
    )


@router.post(
    "/project-review",
    response_model=AgentRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="运行项目审查 Agent",
)
async def run_project_review_agent(
    payload: ProjectReviewRunRequest,
    current_user: CurrentUser,
    service: AgentServiceDependency,
) -> AgentRecordResponse:
    return to_agent_record_response(
        await service.run_agent(
            AgentType.PROJECT_REVIEW,
            current_user.id,
            payload.project_id,
            payload.input.model_dump(mode="python"),
        )
    )


@router.get(
    "/results/{request_id}",
    response_model=AgentRecordResponse,
    summary="查询当前用户的 Agent 结果",
)
def get_agent_result(
    request_id: RequestId,
    current_user: CurrentUser,
    service: AgentServiceDependency,
) -> AgentRecordResponse:
    return to_agent_record_response(service.get_result(request_id, current_user.id))
