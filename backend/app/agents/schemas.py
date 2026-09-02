import re
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{16,}", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|password|secret|token)\b\s*[:=]\s*[\"']?"
        r"[A-Za-z0-9+/_.-]{16,}",
        re.IGNORECASE,
    ),
)


class AgentType(StrEnum):
    PROJECT_ANALYSIS = "project_analysis"
    PROMPT = "prompt"
    PROJECT_REVIEW = "project_review"


def validate_safe_text(value: str) -> str:
    normalized = value.strip()
    if any(pattern.search(normalized) for pattern in SENSITIVE_TEXT_PATTERNS):
        raise ValueError("Agent 输入或输出不能包含疑似密钥、密码或认证令牌")
    return normalized


def normalize_text_list(value: object) -> object:
    if not isinstance(value, list):
        return value
    normalized: list[object] = []
    for item in value:
        normalized.append(validate_safe_text(item) if isinstance(item, str) else item)
    return normalized


def _validate_nested_text(value: object) -> None:
    if isinstance(value, str):
        validate_safe_text(value)
    elif isinstance(value, dict):
        for child in value.values():
            _validate_nested_text(child)
    elif isinstance(value, list):
        for child in value:
            _validate_nested_text(child)


class AgentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def reject_sensitive_text(self) -> "AgentSchema":
        _validate_nested_text(self.model_dump(mode="python"))
        return self


class ProjectAnalysisInput(AgentSchema):
    focus: str | None = Field(default=None, max_length=1000)
    additional_requirements: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("focus")
    @classmethod
    def normalize_focus(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_safe_text(value) or None

    @field_validator("additional_requirements", mode="before")
    @classmethod
    def normalize_requirements(cls, value: object) -> object:
        return normalize_text_list(value)

    @field_validator("additional_requirements")
    @classmethod
    def validate_requirements(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("补充需求单项必须为 1-500 个字符")
        return value


class PromptAgentInput(AgentSchema):
    task: str = Field(min_length=1, max_length=1000)
    environment: str = Field(min_length=1, max_length=500)
    target_directory: str = Field(min_length=1, max_length=300)
    input_description: str = Field(min_length=1, max_length=500)
    output_description: str = Field(min_length=1, max_length=500)
    coding_standards: list[str] = Field(
        default_factory=lambda: [
            "安全性优先，其次是正确性和可读性",
            "使用明确类型并运行相关测试",
        ],
        min_length=1,
        max_length=10,
    )
    api_requirements: list[str] = Field(default_factory=list, max_length=10)
    frontend_backend_relationship: str | None = Field(default=None, max_length=800)

    @field_validator(
        "task",
        "environment",
        "target_directory",
        "input_description",
        "output_description",
        "frontend_backend_relationship",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_safe_text(value)

    @field_validator("target_directory")
    @classmethod
    def validate_target_directory(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if value.startswith(("/", "\\")) or ":" in value or ".." in parts:
            raise ValueError("target_directory 必须是项目内相对路径")
        return normalized

    @field_validator("coding_standards", "api_requirements", mode="before")
    @classmethod
    def normalize_items(cls, value: object) -> object:
        return normalize_text_list(value)

    @field_validator("coding_standards", "api_requirements")
    @classmethod
    def validate_items(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 200 for item in value):
            raise ValueError("规范或 API 要求单项必须为 1-200 个字符")
        return value


class ProjectReviewInput(AgentSchema):
    completed_items: list[str] = Field(default_factory=list, max_length=30)
    known_issues: list[str] = Field(default_factory=list, max_length=30)
    evidence: list[str] = Field(default_factory=list, max_length=30)
    review_focus: str | None = Field(default=None, max_length=1000)

    @field_validator("completed_items", "known_issues", "evidence", mode="before")
    @classmethod
    def normalize_items(cls, value: object) -> object:
        return normalize_text_list(value)

    @field_validator("completed_items", "known_issues", "evidence")
    @classmethod
    def validate_items(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("审查信息单项必须为 1-500 个字符")
        return value

    @field_validator("review_focus")
    @classmethod
    def normalize_focus(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_safe_text(value) or None

    @model_validator(mode="after")
    def require_review_evidence(self) -> "ProjectReviewInput":
        if not (self.completed_items or self.known_issues or self.evidence):
            raise ValueError("项目审查至少需要完成项、已知问题或证据中的一项")
        return self


class RequirementBreakdownItem(AgentSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=8)


class TechnicalChallenge(AgentSchema):
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=800)
    mitigation: str = Field(min_length=1, max_length=800)


class DevelopmentStep(AgentSchema):
    order: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=1000)
    verification: str = Field(min_length=1, max_length=800)


class TechnologyRecommendation(AgentSchema):
    category: str = Field(min_length=1, max_length=100)
    choice: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=800)
    alternatives: list[str] = Field(default_factory=list, max_length=5)


class ProjectAnalysisResult(AgentSchema):
    result_type: Literal["project_analysis"]
    summary: str = Field(min_length=1, max_length=1500)
    requirements_breakdown: list[RequirementBreakdownItem] = Field(
        min_length=1, max_length=12
    )
    technical_challenges: list[TechnicalChallenge] = Field(min_length=1, max_length=10)
    development_steps: list[DevelopmentStep] = Field(min_length=1, max_length=20)
    knowledge_points: list[str] = Field(min_length=1, max_length=20)
    technology_recommendations: list[TechnologyRecommendation] = Field(
        min_length=1, max_length=12
    )

    @model_validator(mode="after")
    def validate_step_order(self) -> "ProjectAnalysisResult":
        orders = [step.order for step in self.development_steps]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("开发步骤 order 必须从 1 连续递增")
        return self


class PromptDraft(AgentSchema):
    title: str = Field(min_length=1, max_length=200)
    implementation_guidance: str = Field(min_length=1, max_length=3000)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=15)
    risk_notes: list[str] = Field(default_factory=list, max_length=10)


class PromptAgentResult(AgentSchema):
    result_type: Literal["prompt"]
    title: str = Field(min_length=1, max_length=200)
    task: str = Field(min_length=1, max_length=1000)
    language: str
    framework: str
    environment: str
    target_directory: str
    input_description: str
    output_description: str
    coding_standards: list[str] = Field(min_length=1, max_length=10)
    database: str
    api_requirements: list[str] = Field(min_length=1, max_length=10)
    frontend_backend_relationship: str
    generated_prompt: str = Field(min_length=1, max_length=20000)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=15)
    risk_notes: list[str] = Field(default_factory=list, max_length=10)


class ReviewIssue(AgentSchema):
    severity: Literal["high", "medium", "low"]
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    recommendation: str = Field(min_length=1, max_length=1000)


class ReviewNextStep(AgentSchema):
    priority: int = Field(ge=1, le=20)
    action: str = Field(min_length=1, max_length=1000)
    verification: str = Field(min_length=1, max_length=800)


class ProjectReviewDraft(AgentSchema):
    overall_status: Literal["on_track", "at_risk", "blocked", "completed"]
    completion_summary: str = Field(min_length=1, max_length=1500)
    completed_items_assessment: list[str] = Field(default_factory=list, max_length=30)
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=20)
    next_steps: list[ReviewNextStep] = Field(min_length=1, max_length=20)


class ProjectReviewResult(ProjectReviewDraft):
    result_type: Literal["project_review"]
    evidence_considered: list[str] = Field(default_factory=list, max_length=30)


AgentInput: TypeAlias = ProjectAnalysisInput | PromptAgentInput | ProjectReviewInput
AgentOutput: TypeAlias = (
    ProjectAnalysisResult | PromptAgentResult | ProjectReviewResult
)

AGENT_RESULT_SCHEMAS: dict[AgentType, type[AgentSchema]] = {
    AgentType.PROJECT_ANALYSIS: ProjectAnalysisResult,
    AgentType.PROMPT: PromptAgentResult,
    AgentType.PROJECT_REVIEW: ProjectReviewResult,
}
