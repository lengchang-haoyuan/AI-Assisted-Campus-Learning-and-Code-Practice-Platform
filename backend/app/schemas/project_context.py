from datetime import datetime
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
)

from app.context.context_schema import (
    CONTEXT_FIELDS,
    ContextSourceType,
    ProjectContextPatch,
)
from app.models.enums import ProjectDifficulty

JsonObject = dict[str, JsonValue]


class ProjectContextUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    values: ProjectContextPatch


class NodeContextReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[str] | None = Field(default=None, max_length=len(CONTEXT_FIELDS))

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("fields 不能包含重复项")
        if not set(value) <= CONTEXT_FIELDS:
            raise ValueError("fields 包含未知上下文字段")
        return value


class NodeContextWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    values: ProjectContextPatch


class ContextSourceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: ContextSourceType
    id: int
    node_key: str | None


class ContextFieldMetadataResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    updated_at: datetime
    source: ContextSourceResponse


class ProjectContextValuesResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_name: str
    language: str | None
    framework: str | None
    frontend: str | None
    backend: str | None
    database: str | None
    difficulty: ProjectDifficulty
    requirements: list[JsonObject] | None
    output_requirement: str | None
    architecture: JsonObject | None
    features: list[str]
    constraints: list[str]
    extensions: JsonObject


class ProjectContextResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: int
    version: int
    values: ProjectContextValuesResponse
    field_metadata: dict[str, ContextFieldMetadataResponse]
    updated_at: datetime
    source: ContextSourceResponse
    is_stale: bool
    stale_fields: list[str]
    stale_node_ids: list[int]


class ProjectContextMutationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    context: ProjectContextResponse
    changed_fields: list[str]
    stale_node_ids: list[int]


class NodeContextResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: int
    workflow_id: int
    node_id: int
    node_key: str
    context_version: int
    values: JsonObject
    is_stale: bool
