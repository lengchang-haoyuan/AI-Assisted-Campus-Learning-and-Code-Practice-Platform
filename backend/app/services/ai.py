from dataclasses import dataclass
from typing import NoReturn

from app.ai.client import AIClient
from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIMessage,
    AIMessageRole,
)
from app.core.exceptions import (
    AIConfigurationError,
    AIRateLimitError,
    AIUpstreamError,
    AIUpstreamTimeoutError,
)


@dataclass(frozen=True, slots=True)
class AICompletionInput:
    prompt: str
    model: str | None
    temperature: float
    max_tokens: int


@dataclass(frozen=True, slots=True)
class AICompletionData:
    provider: str
    model: str
    content: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int


class AIService:
    def __init__(
        self,
        client: AIClient,
        *,
        default_model: str,
        api_key_env_name: str,
    ) -> None:
        self._client = client
        self._default_model = default_model
        self._api_key_env_name = api_key_env_name

    async def complete_test(self, data: AICompletionInput) -> AICompletionData:
        request = AICompletionRequest(
            messages=(AIMessage(role=AIMessageRole.USER, content=data.prompt),),
            model=data.model or self._default_model,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )
        try:
            result = await self._client.complete(request)
        except AIClientError as exc:
            raise_ai_application_error(exc, self._api_key_env_name)

        return AICompletionData(
            provider=result.provider,
            model=result.model,
            content=result.content,
            finish_reason=result.finish_reason,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
            latency_ms=result.latency_ms,
        )



def raise_ai_application_error(
    error: AIClientError, api_key_env_name: str
) -> NoReturn:
    if error.category == AIFailureCategory.CONFIGURATION:
        raise AIConfigurationError(
            f"未配置 {api_key_env_name}，请在后端环境变量中配置后重试"
        ) from error
    if error.category == AIFailureCategory.AUTHENTICATION:
        raise AIConfigurationError(
            "AI Provider 凭据不可用，请联系管理员检查后端配置"
        ) from error
    if error.category == AIFailureCategory.RATE_LIMIT:
        raise AIRateLimitError() from error
    if error.category in {
        AIFailureCategory.CONNECTION_TIMEOUT,
        AIFailureCategory.RESPONSE_TIMEOUT,
        AIFailureCategory.TOTAL_TIMEOUT,
    }:
        raise AIUpstreamTimeoutError() from error
    raise AIUpstreamError() from error
