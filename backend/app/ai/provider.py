from abc import ABC, abstractmethod
from enum import Enum
import json

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_serializer, model_validator


MODEL_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class AIMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIResponseFormat(str, Enum):
    TEXT = "text"
    JSON_OBJECT = "json_object"
    JSON_SCHEMA = "json_schema"


class AIMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: AIMessageRole
    content: str = Field(min_length=1, max_length=12000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("消息内容不能为空")
        return normalized


class AICompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    messages: tuple[AIMessage, ...] = Field(min_length=1, max_length=32)
    model: str = Field(min_length=1, max_length=100, pattern=MODEL_NAME_PATTERN)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    response_format: AIResponseFormat = AIResponseFormat.TEXT
    reasoning_enabled: bool | None = None
    response_schema: dict[str, JsonValue] | None = None
    response_schema_name: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$",
    )

    @model_serializer(mode="wrap")
    def omit_unused_schema_fields(self, handler):
        # 保持旧请求的序列化字段；不依赖高于项目2.11下限的exclude_if。
        data = handler(self)
        if self.response_schema is None:
            data.pop("response_schema", None)
        if self.response_schema_name is None:
            data.pop("response_schema_name", None)
        return data

    @model_validator(mode="after")
    def validate_total_message_size(self) -> "AICompletionRequest":
        if sum(len(message.content) for message in self.messages) > 24000:
            raise ValueError("消息总长度不能超过 24000 个字符")
        if self.response_format == AIResponseFormat.JSON_SCHEMA:
            if self.response_schema is None or self.response_schema_name is None:
                raise ValueError("Schema输出必须提供名称和JSON Schema")
            if self.response_schema.get("type") != "object":
                raise ValueError("Schema输出必须是对象")
            encoded = json.dumps(self.response_schema, ensure_ascii=False, allow_nan=False)
            if len(encoded) > 12000:
                raise ValueError("输出Schema不能超过12000字符")
        elif self.response_schema is not None or self.response_schema_name is not None:
            raise ValueError("只有Schema输出模式可携带输出Schema")
        return self


class AIUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class AIProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100, pattern=MODEL_NAME_PATTERN)
    content: str = Field(min_length=1, max_length=12000)
    finish_reason: str | None = Field(default=None, max_length=50)
    usage: AIUsage


class AICompletionResult(AIProviderResult):
    latency_ms: int = Field(ge=0)


class AIFailureCategory(str, Enum):
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    CONNECTION_TIMEOUT = "connection_timeout"
    RESPONSE_TIMEOUT = "response_timeout"
    TOTAL_TIMEOUT = "total_timeout"
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    MODEL = "model"
    RESPONSE_FORMAT = "response_format"
    UPSTREAM = "upstream"


class AIClientError(Exception):
    def __init__(
        self,
        message: str,
        *,
        category: AIFailureCategory,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
        observed_usage: AIUsage | None = None,
    ) -> None:
        self.category = category
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.observed_usage = observed_usage
        super().__init__(message)


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def complete(self, request: AICompletionRequest) -> AIProviderResult:
        raise NotImplementedError
