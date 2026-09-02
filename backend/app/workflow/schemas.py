from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.agents.schemas import AgentSchema, validate_safe_text

ShortText = Annotated[str, Field(min_length=1, max_length=500)]


class WorkflowNodeInput(AgentSchema):
    instruction: str | None = Field(default=None, max_length=1000)
    expected_output: str | None = Field(default=None, max_length=1000)

    @field_validator("instruction", "expected_output")
    @classmethod
    def normalize_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_safe_text(value) or None


class NormalizedRequirement(AgentSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    acceptance_criteria: list[ShortText] = Field(min_length=1, max_length=8)


class RequirementsAnalysisNodeResult(AgentSchema):
    result_type: Literal["requirements_analysis"]
    summary: str = Field(min_length=1, max_length=1500)
    requirements: list[NormalizedRequirement] = Field(min_length=1, max_length=12)
    features: list[ShortText] = Field(min_length=1, max_length=20)
    constraints: list[ShortText] = Field(default_factory=list, max_length=20)


class TechnologyChoice(AgentSchema):
    value: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=800)


class TechStackAnalysisNodeResult(AgentSchema):
    result_type: Literal["tech_stack_analysis"]
    summary: str = Field(min_length=1, max_length=1500)
    language: TechnologyChoice
    framework: TechnologyChoice
    frontend: TechnologyChoice
    backend: TechnologyChoice
    database: TechnologyChoice


class ArchitectureComponent(AgentSchema):
    name: str = Field(min_length=1, max_length=120)
    responsibility: str = Field(min_length=1, max_length=1000)
    technology: str = Field(min_length=1, max_length=200)
    dependencies: list[ShortText] = Field(default_factory=list, max_length=12)


class ArchitectureDataFlow(AgentSchema):
    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    data: str = Field(min_length=1, max_length=500)


class ArchitectureDecision(AgentSchema):
    title: str = Field(min_length=1, max_length=200)
    choice: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=1000)


class ArchitectureDesignNodeResult(AgentSchema):
    result_type: Literal["architecture_design"]
    summary: str = Field(min_length=1, max_length=1500)
    style: str = Field(min_length=1, max_length=200)
    components: list[ArchitectureComponent] = Field(min_length=2, max_length=20)
    data_flows: list[ArchitectureDataFlow] = Field(min_length=1, max_length=30)
    decisions: list[ArchitectureDecision] = Field(min_length=1, max_length=12)


WorkflowNodeResult = (
    RequirementsAnalysisNodeResult
    | TechStackAnalysisNodeResult
    | ArchitectureDesignNodeResult
)

WORKFLOW_NODE_RESULT_SCHEMAS: dict[str, type[AgentSchema]] = {
    "requirements_analysis": RequirementsAnalysisNodeResult,
    "tech_stack_analysis": TechStackAnalysisNodeResult,
    "architecture_design": ArchitectureDesignNodeResult,
}
