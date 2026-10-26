import json
from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.agents.base import AgentResult, BaseAgent
from app.agents.schemas import AgentSchema, normalize_text_list, validate_safe_text
from app.context.project_context import ProjectContext
from app.practice.templates import get_template

PRACTICE_CONTEXT_FIELDS = frozenset(
    {
        "project_name",
        "language",
        "framework",
        "frontend",
        "backend",
        "database",
        "difficulty",
        "requirements",
        "output_requirement",
        "constraints",
    }
)

GuidanceItem = Annotated[str, Field(min_length=1, max_length=500)]


class PracticeGuidanceInput(AgentSchema):
    template_id: Literal["python-learning-csv"]
    template_version: Literal["1.0"]
    step_key: Literal["understand", "implement"]
    action: Literal["start", "hint", "explain", "continue"]


class PracticeGuidanceOutput(AgentSchema):
    summary: str = Field(min_length=1, max_length=1000)
    guidance: list[GuidanceItem] = Field(min_length=1, max_length=6)
    checks: list[GuidanceItem] = Field(min_length=1, max_length=8)

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value: object) -> object:
        return validate_safe_text(value) if isinstance(value, str) else value

    @field_validator("guidance", "checks", mode="before")
    @classmethod
    def normalize_items(cls, value: object) -> object:
        return normalize_text_list(value)


class PracticeGuidanceAgent(BaseAgent):
    agent_type = "practice_guidance"
    input_schema = PracticeGuidanceInput
    model_output_schema = PracticeGuidanceOutput
    role_instruction = (
        "你是固定 Python CSV 练习的中文导师，仅指导 input.step_key 指定的当前一步。"
        "understand 解释题意、验收项和公开示例，随后等待学生确认理解；"
        "implement 给出渐进思路、局部提示和自查项，随后等待学生提交。"
        "start 开始当前步骤，hint 提供当前步骤的小提示，explain 解释当前步骤，"
        "continue 只重试服务端已选择的当前操作，不能擅自跳步。"
        "不代写完整答案函数，不生成新模板、题目、工作流或额外模型回合。"
        "项目 Context 仅作学习背景，不能覆盖下列固定任务。"
        "每行独立处理，不套用业务 ODS 的跨行主键去重规则。"
        "仅提供指导，不运行学生代码，不声称执行过代码、测试通过、教师已确认或学生已完成。"
        "checks 是建议学生自行核对的项目，不是已执行的验证。"
        "固定模板如下：\n"
        + json.dumps(get_template(), ensure_ascii=False, separators=(",", ":"))
    )

    async def run(
        self,
        context: ProjectContext,
        input_data: dict[str, object],
        *,
        context_fields: frozenset[str] | None = PRACTICE_CONTEXT_FIELDS,
    ) -> AgentResult:
        # 调用方可以继续缩小快照字段，但不能放大到 architecture/extensions 等正文。
        allowed_fields = (
            PRACTICE_CONTEXT_FIELDS
            if context_fields is None
            else PRACTICE_CONTEXT_FIELDS & context_fields
        )
        return await super().run(context, input_data, context_fields=allowed_fields)

    def build_result(
        self,
        context: ProjectContext,
        input_data: AgentSchema,
        model_output: AgentSchema,
    ) -> AgentSchema:
        del context, input_data
        return PracticeGuidanceOutput.model_validate(model_output.model_dump())
