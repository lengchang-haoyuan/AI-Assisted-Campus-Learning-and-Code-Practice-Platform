from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.agents.schemas import (
    AgentType,
    ProjectAnalysisInput,
    ProjectAnalysisResult,
    ProjectReviewInput,
    ProjectReviewResult,
    PromptAgentInput,
    PromptAgentResult,
)
from app.models.enums import AIRequestStatus

AgentResponseResult = Annotated[
    ProjectAnalysisResult | PromptAgentResult | ProjectReviewResult,
    Field(discriminator="result_type"),
]


class ProjectAnalysisRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(ge=1)
    input: ProjectAnalysisInput = Field(default_factory=ProjectAnalysisInput)


class PromptAgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(ge=1)
    input: PromptAgentInput


class ProjectReviewRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(ge=1)
    input: ProjectReviewInput


class AgentErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class AgentUsageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None


class AgentRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: int
    project_id: int | None
    agent_type: AgentType
    status: AIRequestStatus
    provider: str
    model: str
    context_version: int
    result: AgentResponseResult | None
    error: AgentErrorResponse | None
    usage: AgentUsageResponse
    requested_at: datetime
    finished_at: datetime | None
