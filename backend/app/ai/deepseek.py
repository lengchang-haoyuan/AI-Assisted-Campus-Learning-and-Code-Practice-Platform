import json

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIProvider,
    AIProviderResult,
    AIResponseFormat,
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


class _ResponsesUsage(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)
    total_tokens: int = Field(ge=0, strict=True)


class _ResponsesContent(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str
    text: str | None = None


class _ResponsesItem(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str
    role: str | None = None
    content: list[_ResponsesContent] | None = None


class _ResponsesResult(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    model: str = Field(min_length=1, max_length=100, pattern=MODEL_NAME_PATTERN)
    status: str
    output: list[_ResponsesItem]
    usage: _ResponsesUsage | None = None
    error: dict | None = None
    incomplete_details: dict | None = None


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

        path, payload = self._request_payload(request)

        try:
            response = await self._http_client.post(
                f"{self._base_url}{path}",
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

        if request.response_format == AIResponseFormat.JSON_SCHEMA:
            return self._parse_responses_result(response)

        try:
            parsed = _DeepSeekResponse.model_validate(self._decode_json(response))
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
    def _request_payload(request: AICompletionRequest) -> tuple[str, dict]:
        if request.response_format == AIResponseFormat.JSON_SCHEMA:
            payload = {
                "model": request.model,
                "input": [{"role": item.role.value, "content": item.content} for item in request.messages],
                "temperature": request.temperature,
                "stream": False,
                "text": {"format": {
                    "type": "json_schema", "name": request.response_schema_name,
                    "schema": request.response_schema,
                }},
            }
            if request.max_tokens is not None:
                payload["max_output_tokens"] = request.max_tokens
            if request.reasoning_enabled is not None:
                payload["reasoning"] = {"effort": "high" if request.reasoning_enabled else "none"}
            return "/responses", payload

        payload = {
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
        if request.response_format == AIResponseFormat.JSON_OBJECT:
            payload["response_format"] = {"type": "json_object"}
        if request.reasoning_enabled is not None:
            payload["thinking"] = {
                "type": "enabled" if request.reasoning_enabled else "disabled"
            }

        return "/chat/completions", payload

    def _parse_responses_result(self, response: httpx.Response) -> AIProviderResult:
        observed = None
        try:
            body = self._decode_json(response)
            raw_usage = body.get("usage") if isinstance(body, dict) else None
            if raw_usage is not None:
                usage = _ResponsesUsage.model_validate(raw_usage)
                if usage.input_tokens + usage.output_tokens != usage.total_tokens:
                    raise ValueError("Responses用量合计不一致")
                observed = AIUsage(prompt_tokens=usage.input_tokens,
                                   completion_tokens=usage.output_tokens, total_tokens=usage.total_tokens)
            parsed = _ResponsesResult.model_validate(body)
            if parsed.status != "completed" or parsed.error is not None or parsed.incomplete_details is not None:
                raise ValueError("Responses未完成")
            if len(parsed.output) != 1:
                raise ValueError("Responses必须仅有一个文本输出")
            item = parsed.output[0]
            if item.type != "message" or item.role != "assistant" or not item.content or len(item.content) != 1:
                raise ValueError("Responses输出类型不符合约定")
            part = item.content[0]
            if part.type != "output_text" or not part.text or not part.text.strip():
                raise ValueError("Responses无有效文本")
            content = part.text.strip()
            if not isinstance(json.loads(content), dict):
                raise ValueError("Responses输出不是JSON对象")
            return AIProviderResult(
                provider=self.name, model=parsed.model, content=content,
                # 此接口不返回Chat finish_reason，保留其真实终态，不伪造stop。
                finish_reason=parsed.status,
                usage=observed or AIUsage(prompt_tokens=None, completion_tokens=None, total_tokens=None),
            )
        except (ValueError, ValidationError) as exc:
            raise AIClientError(
                "AI Provider 结构化响应无效或未完成", category=AIFailureCategory.RESPONSE_FORMAT,
                observed_usage=observed,
            ) from exc

    @staticmethod
    def _decode_json(response: httpx.Response) -> object:
        # 模型网络JSON只接受UTF-8（兼容BOM），禁止按本机/响应charset猜测或替换坏字节。
        return json.loads(response.content.decode("utf-8-sig"))

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
