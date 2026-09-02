from app.agents.base import BaseAgent
from app.agents.schemas import (
    AgentOutput,
    AgentSchema,
    AgentType,
    ProjectReviewDraft,
    ProjectReviewInput,
    ProjectReviewResult,
)
from app.context.project_context import ProjectContext


class ProjectReviewAgent(BaseAgent):
    agent_type = AgentType.PROJECT_REVIEW
    input_schema = ProjectReviewInput
    model_output_schema = ProjectReviewDraft
    role_instruction = (
        "依据用户给出的完成项、问题和证据审查项目。只陈述证据支持的完成情况，"
        "按严重程度列出问题并给出下一步和验证方法，不得假装运行过测试。"
    )

    def build_result(
        self,
        context: ProjectContext,
        input_data: AgentSchema,
        model_output: AgentSchema,
    ) -> AgentOutput:
        del context
        review_input = ProjectReviewInput.model_validate(input_data.model_dump())
        draft = ProjectReviewDraft.model_validate(model_output.model_dump())
        return ProjectReviewResult(
            result_type="project_review",
            overall_status=draft.overall_status,
            completion_summary=draft.completion_summary,
            completed_items_assessment=draft.completed_items_assessment,
            issues=draft.issues,
            next_steps=draft.next_steps,
            evidence_considered=review_input.evidence,
        )
