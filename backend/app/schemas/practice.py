from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from app.agents.schemas import validate_safe_text
from app.practice.review import validate_declared_output

PracticeAction = Literal[
    "start", "hint", "explain", "review", "continue", "cancel", "resume", "confirm"
]


class PracticeSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: Literal["python-learning-csv"]
    template_version: Literal["1.0"]
    expected_context_version: int = Field(ge=1)
    request_key: str = Field(min_length=36, max_length=36)

    @field_validator("request_key")
    @classmethod
    def normalize_request_key(cls, value: str) -> str:
        return str(UUID(value))


class PracticeActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: PracticeAction
    expected_revision: int = Field(ge=1)
    request_key: str = Field(min_length=36, max_length=36)
    attempt_id: UUID | None = None

    @field_validator("request_key")
    @classmethod
    def normalize_request_key(cls, value: str) -> str:
        return str(UUID(value))


class PracticeAttemptSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    step_key: Literal["implement"]
    request_key: str = Field(min_length=36, max_length=36)
    code: str = Field(min_length=1, max_length=12000)
    declared_output: dict[str, JsonValue]
    self_statement: bool | None = Field(default=None, strict=True)

    @field_validator("request_key")
    @classmethod
    def normalize_request_key(cls, value: str) -> str:
        return str(UUID(value))

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        validate_safe_text(value)
        if not value.strip():
            raise ValueError("提交代码不能为空白")
        return value

    @field_validator("declared_output")
    @classmethod
    def limit_declared_output(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return validate_declared_output(value)
