from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
import httpx

from app.api.deps import DatabaseSession, build_ai_client
from app.core.config import get_ai_settings
from app.practice.agent import PracticeGuidanceAgent
from app.practice.review import PracticeReviewAgent, PracticeCodeGuidanceAgent
from app.repositories.practice import PracticeRepository
from app.services.practice import PracticeService


async def get_practice_service(
    session: DatabaseSession,
) -> AsyncGenerator[PracticeService, None]:
    settings = get_ai_settings()
    async with httpx.AsyncClient(follow_redirects=False) as http_client:
        # 实践单步失败后由本人明确继续，不能在Provider层静默重复付费请求。
        client = build_ai_client(
            settings.model_copy(update={"ai_max_retries": 0}), http_client
        )
        agent = PracticeGuidanceAgent(
            client,
            model=settings.deepseek_model,
            max_tokens=settings.ai_agent_max_tokens,
            temperature=settings.ai_agent_temperature,
        )
        yield PracticeService(
            PracticeRepository(session),
            agent,
            provider_name=settings.ai_provider,
            model=settings.deepseek_model,
            review_agent=PracticeReviewAgent(client, model=settings.deepseek_model,
                max_tokens=settings.ai_agent_max_tokens, temperature=settings.ai_agent_temperature),
            code_guidance_agent=PracticeCodeGuidanceAgent(client, model=settings.deepseek_model,
                max_tokens=settings.ai_agent_max_tokens, temperature=settings.ai_agent_temperature),
            operation_timeout_seconds=max(
                120.0, settings.ai_total_timeout_seconds + 30.0
            ),
        )


PracticeServiceDependency = Annotated[PracticeService, Depends(get_practice_service)]
