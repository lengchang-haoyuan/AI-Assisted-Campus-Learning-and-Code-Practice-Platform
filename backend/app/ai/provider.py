from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MODEL_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class AIMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIResponseFormat(str, Enum):
    TEXT = "text"
    JSON_OBJECT = "json_object"


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

    @model_validator(mode="after")
    def validate_total_message_size(self) -> "AICompletionRequest":
        if sum(len(message.content) for message in self.messages) > 24000:
            raise ValueError("消息总长度不能超过 24000 个字符")
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
    ) -> None:
        self.category = category
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def complete(self, request: AICompletionRequest) -> AIProviderResult:
        raise NotImplementedError
