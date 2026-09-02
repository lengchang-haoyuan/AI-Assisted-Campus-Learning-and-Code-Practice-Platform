import asyncio
from secrets import token_hex, token_urlsafe

from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from app.agents.project_analysis import ProjectAnalysisAgent
from app.agents.project_review import ProjectReviewAgent
from app.agents.prompt_agent import PromptAgent
from app.agents.schemas import AgentType
from app.ai.client import AIClient
from app.ai.provider import (
    AICompletionRequest,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.context.context_schema import ContextSource, ContextSourceType
from app.context.project_context import ContextBuilder, ProjectContextSeed
from app.core.database import get_session_factory
from app.core.exceptions import ResourceNotFoundError
from app.models.ai import AIRequest
from app.models.enums import AIRequestStatus, ProjectDifficulty, ProjectStatus
from app.models.project import Project
from app.models.user import User
from app.repositories.agent import AgentRepository
from app.services.agent import AgentService

ANALYSIS_RESULT = """{
  "result_type": "project_analysis",
  "summary": "项目应按上下文中的技术栈分阶段交付。",
  "requirements_breakdown": [{
    "title": "结构化 Agent",
    "description": "读取 ProjectContext 并返回可验证结果。",
    "acceptance_criteria": ["结果保存到 AIResult"]
  }],
  "technical_challenges": [{
    "title": "边界隔离",
    "reason": "模型输入和数据库属于不同信任边界。",
    "mitigation": "由 Service 编排并使用 Schema 校验。"
  }],
  "development_steps": [{
    "order": 1,
    "title": "运行 Agent",
    "action": "使用已验证 Context 调用 Fake Provider。",
    "verification": "重新查询 AIRequest 和 AIResult。"
  }],
  "knowledge_points": ["Pydantic", "事务边界"],
  "technology_recommendations": [{
    "category": "后端",
    "choice": "FastAPI",
    "reason": "与项目上下文一致。",
    "alternatives": []
  }]
}"""

PROMPT_RESULT = """{
  "title": "实现 Agent 结果查询",
  "implementation_guidance": "沿用 Router、Service、Repository 分层并校验当前用户。",
  "acceptance_criteria": ["结果可以按 request_id 查询"],
  "risk_notes": ["不要保存原始敏感输入"]
}"""


class VerificationProvider(AIProvider):
    def __init__(self) -> None:
        self._results = [ANALYSIS_RESULT, PROMPT_RESULT]

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request: AICompletionRequest) -> AIProviderResult:
        return AIProviderResult(
            provider=self.name,
            model=request.model,
            content=self._results.pop(0),
            finish_reason="stop",
            usage=AIUsage(
                prompt_tokens=120,
                completion_tokens=80,
                total_tokens=200,
            ),
        )


async def run_verification(service: AgentService, user_id: int, project_id: int) -> None:
    analysis = await service.run_agent(
        AgentType.PROJECT_ANALYSIS,
        user_id,
        project_id,
        {
            "focus": "p12-verification-focus",
            "additional_requirements": [],
        },
    )
    prompt = await service.run_agent(
        AgentType.PROMPT,
        user_id,
        project_id,
        {
            "task": "实现 Agent 结果查询",
            "environment": "verification",
            "target_directory": "backend/app",
            "input_description": "当前用户和 request_id",
            "output_description": "结构化 Agent 结果",
            "coding_standards": ["所有权由 Service 校验"],
            "api_requirements": ["使用 /api/v1 前缀"],
        },
    )
    queried_analysis = service.get_result(analysis.request_id, user_id)
    queried_prompt = service.get_result(prompt.request_id, user_id)
    if queried_analysis.status != AIRequestStatus.COMPLETED:
        raise RuntimeError("项目分析 Agent 未持久化为 completed")
    if queried_prompt.status != AIRequestStatus.COMPLETED:
        raise RuntimeError("Prompt Agent 未持久化为 completed")
    if queried_analysis.result is None or queried_prompt.result is None:
        raise RuntimeError("Agent 结构化结果无法重新查询")
    try:
        service.get_result(analysis.request_id, user_id + 1_000_000)
    except ResourceNotFoundError:
        pass
    else:
        raise RuntimeError("其他用户不应查询到 Agent 结果")


def main() -> None:
    session = get_session_factory()()
    user_id: int | None = None
    project_id: int | None = None
    try:
        suffix = token_hex(6)
        user = User(
            username=f"p12_verify_{suffix}",
            email=f"p12_verify_{suffix}@example.invalid",
            password_hash=PasswordHash.recommended().hash(token_urlsafe(32)),
        )
        project = Project(
            owner=user,
            name="P12 verification",
            difficulty=ProjectDifficulty.INTERMEDIATE,
            status=ProjectStatus.IN_PROGRESS,
            language="Python",
            framework="FastAPI",
            frontend="Vue 3",
            backend="FastAPI",
            database="MySQL",
            requirements=[{"title": "Agent verification"}],
            output_requirement="Persisted structured Agent results",
        )
        session.add_all([user, project])
        session.flush()
        user_id = user.id
        project_id = project.id
        project.context_data = ContextBuilder().build(
            ProjectContextSeed(
                project_name=project.name,
                language=project.language,
                framework=project.framework,
                frontend=project.frontend,
                backend=project.backend,
                database=project.database,
                difficulty=project.difficulty,
                requirements=project.requirements,
                output_requirement=project.output_requirement,
            ),
            source=ContextSource(type=ContextSourceType.PROJECT, id=project.id),
        ).to_storage()
        session.commit()

        provider = VerificationProvider()
        client = AIClient(
            provider,
            total_timeout_seconds=5,
            max_retries=0,
            retry_base_delay_seconds=0.1,
            max_retry_delay_seconds=1,
        )
        options = {"model": "fake-model", "max_tokens": 1200, "temperature": 0.1}
        service = AgentService(
            AgentRepository(session),
            {
                AgentType.PROJECT_ANALYSIS: ProjectAnalysisAgent(client, **options),
                AgentType.PROMPT: PromptAgent(client, **options),
                AgentType.PROJECT_REVIEW: ProjectReviewAgent(client, **options),
            },
            api_key_env_name="DEEPSEEK_API_KEY",
        )
        asyncio.run(run_verification(service, user.id, project.id))

        requests = list(
            session.scalars(
                select(AIRequest)
                .options(joinedload(AIRequest.result))
                .where(AIRequest.user_id == user.id)
                .order_by(AIRequest.id)
            ).unique()
        )
        if len(requests) != 2 or any(item.result is None for item in requests):
            raise RuntimeError("MySQL 中的 Agent 请求与结果数量不符合预期")
        if any(len(item.input_hash) != 64 for item in requests):
            raise RuntimeError("Agent 输入哈希未正确保存")
        if any(
            "p12-verification-focus"
            in f"{item.input_summary}{item.request_metadata}"
            for item in requests
        ):
            raise RuntimeError("原始 Agent 输入不应写入请求摘要或元数据")
        print(
            "P12 Agent MySQL 验收通过：分析与 Prompt 结果可持久化、按用户查询且原始输入未落库。"
        )
    finally:
        session.rollback()
        if user_id is not None:
            session.execute(
                delete(AIRequest)
                .where(AIRequest.user_id == user_id)
                .execution_options(synchronize_session=False)
            )
        if project_id is not None:
            session.execute(
                delete(Project)
                .where(Project.id == project_id)
                .execution_options(synchronize_session=False)
            )
        if user_id is not None:
            session.execute(
                delete(User)
                .where(User.id == user_id)
                .execution_options(synchronize_session=False)
            )
        session.commit()
        session.close()


if __name__ == "__main__":
    main()
