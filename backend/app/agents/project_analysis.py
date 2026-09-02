from app.agents.base import BaseAgent
from app.agents.schemas import (
    AgentOutput,
    AgentSchema,
    AgentType,
    ProjectAnalysisInput,
    ProjectAnalysisResult,
)
from app.context.project_context import ProjectContext


class ProjectAnalysisAgent(BaseAgent):
    agent_type = AgentType.PROJECT_ANALYSIS
    input_schema = ProjectAnalysisInput
    model_output_schema = ProjectAnalysisResult
    role_instruction = (
        "基于项目上下文拆解真实需求，识别技术难点，给出可验证的开发步骤、"
        "需要学习的知识点和符合现有技术栈的建议。不要生成完整项目代码。"
        "结果保持紧凑：需求和技术难点各 3-6 项，开发步骤 4-8 项，"
        "知识点 5-10 项，技术建议 3-6 项；每个说明只保留必要事实。"
    )

    def build_result(
        self,
        context: ProjectContext,
        input_data: AgentSchema,
        model_output: AgentSchema,
    ) -> AgentOutput:
        del context, input_data
        return ProjectAnalysisResult.model_validate(model_output.model_dump())
