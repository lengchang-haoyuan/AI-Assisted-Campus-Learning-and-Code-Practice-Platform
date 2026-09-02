from app.agents.base import BaseAgent
from app.agents.schemas import (
    AgentOutput,
    AgentSchema,
    AgentType,
    PromptAgentInput,
    PromptAgentResult,
    PromptDraft,
)
from app.context.project_context import ProjectContext


class PromptAgent(BaseAgent):
    agent_type = AgentType.PROMPT
    input_schema = PromptAgentInput
    model_output_schema = PromptDraft
    role_instruction = (
        "为代码 AI 生成实施指导和验收标准。建议必须尊重现有项目边界、明确输入输出，"
        "不得要求绕过认证、执行未授权命令、写入秘密或跳过测试。"
    )

    def build_result(
        self,
        context: ProjectContext,
        input_data: AgentSchema,
        model_output: AgentSchema,
    ) -> AgentOutput:
        prompt_input = PromptAgentInput.model_validate(input_data.model_dump())
        draft = PromptDraft.model_validate(model_output.model_dump())
        values = context.values
        language = values.language or "未指定，实施前确认"
        framework = values.framework or "未指定，沿用仓库现有框架"
        database = values.database or "未指定；数据库只能由后端访问"
        api_requirements = prompt_input.api_requirements or [
            "沿用 /api/v1 前缀和现有请求、响应、认证及错误语义"
        ]
        relationship = prompt_input.frontend_backend_relationship or (
            f"前端 {values.frontend or '未指定'} 通过受认证 API 调用后端 "
            f"{values.backend or '未指定'}；前端不得直接访问数据库。"
        )
        context_output = values.output_requirement or "以请求中的输出说明和验收标准为准"
        standards = "\n".join(
            f"- {item}" for item in prompt_input.coding_standards
        )
        api_lines = "\n".join(f"- {item}" for item in api_requirements)
        acceptance_lines = "\n".join(
            f"- {item}" for item in draft.acceptance_criteria
        )
        generated_prompt = (
            f"# {draft.title}\n\n"
            "## 项目上下文\n"
            f"- 项目：{values.project_name}\n"
            f"- 语言：{language}\n"
            f"- 框架：{framework}\n"
            f"- 前端：{values.frontend or '未指定'}\n"
            f"- 后端：{values.backend or '未指定'}\n"
            f"- 数据库：{database}\n"
            f"- 运行环境：{prompt_input.environment}\n"
            f"- 目标目录：{prompt_input.target_directory}\n\n"
            "## 本次任务\n"
            f"{prompt_input.task}\n\n"
            "## 输入\n"
            f"{prompt_input.input_description}\n\n"
            "## 输出\n"
            f"{prompt_input.output_description}\n"
            f"项目既定输出约束：{context_output}\n\n"
            "## 编码规范\n"
            f"{standards}\n\n"
            "## API 与前后端关系\n"
            f"{api_lines}\n"
            f"{relationship}\n\n"
            "## 实施指导\n"
            f"{draft.implementation_guidance}\n\n"
            "## 验收标准\n"
            f"{acceptance_lines}\n\n"
            "只修改完成本任务所必需的代码；先扫描现有实现，不硬编码秘密，不执行输入中未授权的命令。"
        )
        return PromptAgentResult(
            result_type="prompt",
            title=draft.title,
            task=prompt_input.task,
            language=language,
            framework=framework,
            environment=prompt_input.environment,
            target_directory=prompt_input.target_directory,
            input_description=prompt_input.input_description,
            output_description=prompt_input.output_description,
            coding_standards=prompt_input.coding_standards,
            database=database,
            api_requirements=api_requirements,
            frontend_backend_relationship=relationship,
            generated_prompt=generated_prompt,
            acceptance_criteria=draft.acceptance_criteria,
            risk_notes=draft.risk_notes,
        )
