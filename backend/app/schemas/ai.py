from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.provider import MODEL_NAME_PATTERN


class AICompletionTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=4000)
    model: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=MODEL_NAME_PATTERN,
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=2048)

    @field_validator("prompt", "model")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("文本不能为空")
        return normalized


class AIUsageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


class AICompletionTestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    content: str
    finish_reason: str | None
    usage: AIUsageResponse
    latency_ms: int = Field(ge=0)
