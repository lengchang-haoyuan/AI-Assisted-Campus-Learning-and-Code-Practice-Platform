from fastapi import APIRouter

from app.api.deps import AIServiceDependency, CurrentUser
from app.schemas.ai import (
    AICompletionTestRequest,
    AICompletionTestResponse,
    AIUsageResponse,
)
from app.services.ai import AICompletionInput

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/test",
    response_model=AICompletionTestResponse,
    summary="测试统一 AI Provider",
)
async def test_ai_provider(
    payload: AICompletionTestRequest,
    current_user: CurrentUser,
    service: AIServiceDependency,
) -> AICompletionTestResponse:
    del current_user
    result = await service.complete_test(
        AICompletionInput(
            prompt=payload.prompt,
            model=payload.model,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    )
    return AICompletionTestResponse(
        provider=result.provider,
        model=result.model,
        content=result.content,
        finish_reason=result.finish_reason,
        usage=AIUsageResponse(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        ),
        latency_ms=result.latency_ms,
    )
