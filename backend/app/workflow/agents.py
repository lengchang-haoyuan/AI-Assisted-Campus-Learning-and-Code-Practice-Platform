from app.agents.base import BaseAgent
from app.agents.schemas import AgentSchema
from app.context.project_context import ProjectContext
from app.workflow.schemas import (
    ArchitectureDesignNodeResult,
    RequirementsAnalysisNodeResult,
    TechStackAnalysisNodeResult,
    WorkflowNodeInput,
)


class RequirementsAnalysisWorkflowAgent(BaseAgent):
    agent_type = "requirements_analysis"
    input_schema = WorkflowNodeInput
    model_output_schema = RequirementsAnalysisNodeResult
    role_instruction = (
        "规范化项目需求，提取可验证的功能和约束。只分析需求，不选择技术栈或设计架构。"
        "保持紧凑：需求 3-8 项、功能 3-12 项、约束不超过 10 项。"
    )

    def build_result(
        self,
        context: ProjectContext,
        input_data: AgentSchema,
        model_output: AgentSchema,
    ) -> AgentSchema:
        del context, input_data
        return RequirementsAnalysisNodeResult.model_validate(model_output.model_dump())


class TechStackAnalysisWorkflowAgent(BaseAgent):
    agent_type = "tech_stack_analysis"
    input_schema = WorkflowNodeInput
    model_output_schema = TechStackAnalysisNodeResult
    role_instruction = (
        "依据需求、功能、约束和难度选择语言、框架、前端、后端和数据库。"
        "每一类必须给出一个与现有项目可兼容的明确值及简短理由，不设计架构。"
    )

    def build_result(
        self,
        context: ProjectContext,
        input_data: AgentSchema,
        model_output: AgentSchema,
    ) -> AgentSchema:
        del context, input_data
        return TechStackAnalysisNodeResult.model_validate(model_output.model_dump())


class ArchitectureDesignWorkflowAgent(BaseAgent):
    agent_type = "architecture_design"
    input_schema = WorkflowNodeInput
    model_output_schema = ArchitectureDesignNodeResult
    role_instruction = (
        "依据已确定的需求和技术栈设计可实现的系统架构。输出架构风格、组件职责、"
        "数据流和关键决策；不生成完整代码，不声称执行过验证。"
    )

    def build_result(
        self,
        context: ProjectContext,
        input_data: AgentSchema,
        model_output: AgentSchema,
    ) -> AgentSchema:
        del context, input_data
        return ArchitectureDesignNodeResult.model_validate(model_output.model_dump())
