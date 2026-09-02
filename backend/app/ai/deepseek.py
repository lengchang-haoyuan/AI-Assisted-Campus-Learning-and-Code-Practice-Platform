import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIProvider,
    AIProviderResult,
    AIUsage,
    MODEL_NAME_PATTERN,
)


class _DeepSeekMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    content: str = Field(min_length=1, max_length=12000)


class _DeepSeekChoice(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    message: _DeepSeekMessage
    finish_reason: str | None = Field(default=None, max_length=50)


class _DeepSeekUsage(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class _DeepSeekResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    model: str = Field(min_length=1, max_length=100, pattern=MODEL_NAME_PATTERN)
    choices: list[_DeepSeekChoice] = Field(min_length=1, max_length=16)
    usage: _DeepSeekUsage | None = None


class DeepSeekProvider(AIProvider):
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        api_key: SecretStr | None,
        base_url: str,
        connect_timeout_seconds: float,
        request_timeout_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(
            request_timeout_seconds,
            connect=connect_timeout_seconds,
        )

    @property
    def name(self) -> str:
        return "deepseek"

    async def complete(self, request: AICompletionRequest) -> AIProviderResult:
        if self._api_key is None:
            raise AIClientError(
                "未配置 DEEPSEEK_API_KEY",
                category=AIFailureCategory.CONFIGURATION,
            )

        payload: dict[str, object] = {
            "model": request.model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        try:
            response = await self._http_client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
        except (httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            raise AIClientError(
                "AI Provider 连接超时",
                category=AIFailureCategory.CONNECTION_TIMEOUT,
                retryable=True,
            ) from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            raise AIClientError(
                "AI Provider 响应超时",
                category=AIFailureCategory.RESPONSE_TIMEOUT,
            ) from exc
        except httpx.ConnectError as exc:
            raise AIClientError(
                "AI Provider 连接失败",
                category=AIFailureCategory.NETWORK,
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise AIClientError(
                "AI Provider 网络请求失败",
                category=AIFailureCategory.NETWORK,
            ) from exc

        if response.status_code == 429:
            raise AIClientError(
                "AI Provider 触发限流",
                category=AIFailureCategory.RATE_LIMIT,
                retryable=True,
                retry_after_seconds=self._read_retry_after(response),
            )
        if response.status_code in {401, 403}:
            raise AIClientError(
                "AI Provider 凭据不可用",
                category=AIFailureCategory.AUTHENTICATION,
            )
        if response.status_code == 408:
            raise AIClientError(
                "AI Provider 请求超时",
                category=AIFailureCategory.RESPONSE_TIMEOUT,
            )
        if response.status_code in {400, 404, 422}:
            raise AIClientError(
                "AI Provider 拒绝了模型请求",
                category=AIFailureCategory.MODEL,
            )
        if not response.is_success:
            raise AIClientError(
                "AI Provider 返回上游错误",
                category=AIFailureCategory.UPSTREAM,
            )

        try:
            parsed = _DeepSeekResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise AIClientError(
                "AI Provider 返回格式无效",
                category=AIFailureCategory.RESPONSE_FORMAT,
            ) from exc

        content = parsed.choices[0].message.content.strip()
        if not content:
            raise AIClientError(
                "AI Provider 返回空内容",
                category=AIFailureCategory.RESPONSE_FORMAT,
            )
        usage = parsed.usage
        return AIProviderResult(
            provider=self.name,
            model=parsed.model,
            content=content,
            finish_reason=parsed.choices[0].finish_reason,
            usage=AIUsage(
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
            ),
        )

    @staticmethod
    def _read_retry_after(response: httpx.Response) -> float | None:
        raw_value = response.headers.get("Retry-After")
        if raw_value is None:
            return None
        try:
            seconds = float(raw_value)
        except ValueError:
            return None
        return seconds if seconds >= 0 else None
