import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from app.models.enums import ProjectDifficulty

CONTEXT_SCHEMA_VERSION = 1
MAX_CONTEXT_BYTES = 262_144
MAX_CONTEXT_JSON_DEPTH = 8
MAX_CONTEXT_ITEMS = 100

JsonObject = dict[str, JsonValue]


class ContextSourceType(StrEnum):
    PROJECT = "project"
    USER = "user"
    WORKFLOW_NODE = "workflow_node"


class ContextSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: ContextSourceType
    id: int = Field(ge=1)
    node_key: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_node_source(self) -> Self:
        if self.type == ContextSourceType.WORKFLOW_NODE and self.node_key is None:
            raise ValueError("工作流节点来源必须包含 node_key")
        if self.type != ContextSourceType.WORKFLOW_NODE and self.node_key is not None:
            raise ValueError("非工作流节点来源不能包含 node_key")
        return self


class ContextFieldMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    updated_at: datetime
    source: ContextSource

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value)


def _normalize_optional_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("上下文时间必须包含时区")
    return value.astimezone(UTC)


def _normalize_text_items(value: object) -> object:
    if not isinstance(value, list):
        return value
    normalized: list[object] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            normalized.append(item)
            continue
        text = item.strip()
        if text and text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized


def _validate_text_items(value: list[str]) -> list[str]:
    if any(len(item) > 500 for item in value):
        raise ValueError("列表单项不能超过 500 个字符")
    return value


def _validate_json_value(value: JsonValue, *, depth: int = 0) -> None:
    if depth > MAX_CONTEXT_JSON_DEPTH:
        raise ValueError(f"JSON 嵌套不能超过 {MAX_CONTEXT_JSON_DEPTH} 层")
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = key.lower().replace("-", "_")
            if normalized_key in {
                "api_key",
                "authorization",
                "password",
                "raw_input",
                "raw_prompt",
                "secret",
                "secret_key",
                "token",
            } or normalized_key.endswith(
                ("_api_key", "_password", "_secret", "_token")
            ):
                raise ValueError(f"上下文不允许保存敏感字段 {key}")
            _validate_json_value(child, depth=depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_CONTEXT_ITEMS:
            raise ValueError(f"JSON 数组不能超过 {MAX_CONTEXT_ITEMS} 项")
        for child in value:
            _validate_json_value(child, depth=depth + 1)


def validate_json_object(value: JsonObject | None) -> JsonObject | None:
    if value is not None:
        _validate_json_value(value)
    return value


class ProjectContextValues(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_name: str = Field(min_length=1, max_length=120)
    language: str | None = Field(default=None, max_length=100)
    framework: str | None = Field(default=None, max_length=100)
    frontend: str | None = Field(default=None, max_length=100)
    backend: str | None = Field(default=None, max_length=100)
    database: str | None = Field(default=None, max_length=100)
    difficulty: ProjectDifficulty
    requirements: list[JsonObject] | None = Field(
        default=None, max_length=MAX_CONTEXT_ITEMS
    )
    output_requirement: str | None = Field(default=None, max_length=5_000)
    architecture: JsonObject | None = None
    features: list[str] = Field(default_factory=list, max_length=MAX_CONTEXT_ITEMS)
    constraints: list[str] = Field(default_factory=list, max_length=MAX_CONTEXT_ITEMS)
    extensions: JsonObject = Field(default_factory=dict)

    @field_validator("project_name", mode="before")
    @classmethod
    def normalize_project_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "language",
        "framework",
        "frontend",
        "backend",
        "database",
        "output_requirement",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @field_validator("features", "constraints", mode="before")
    @classmethod
    def normalize_text_items(cls, value: object) -> object:
        return _normalize_text_items(value)

    @field_validator("features", "constraints")
    @classmethod
    def validate_text_items(cls, value: list[str]) -> list[str]:
        return _validate_text_items(value)

    @field_validator("requirements")
    @classmethod
    def validate_requirements(
        cls, value: list[JsonObject] | None
    ) -> list[JsonObject] | None:
        if value is not None:
            for item in value:
                validate_json_object(item)
        return value

    @field_validator("architecture", "extensions")
    @classmethod
    def validate_json_fields(cls, value: JsonObject | None) -> JsonObject | None:
        return validate_json_object(value)


class ProjectContextPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str | None = Field(default=None, min_length=1, max_length=120)
    language: str | None = Field(default=None, max_length=100)
    framework: str | None = Field(default=None, max_length=100)
    frontend: str | None = Field(default=None, max_length=100)
    backend: str | None = Field(default=None, max_length=100)
    database: str | None = Field(default=None, max_length=100)
    difficulty: ProjectDifficulty | None = None
    requirements: list[JsonObject] | None = Field(
        default=None, max_length=MAX_CONTEXT_ITEMS
    )
    output_requirement: str | None = Field(default=None, max_length=5_000)
    architecture: JsonObject | None = None
    features: list[str] | None = Field(default=None, max_length=MAX_CONTEXT_ITEMS)
    constraints: list[str] | None = Field(default=None, max_length=MAX_CONTEXT_ITEMS)
    extensions: JsonObject | None = None

    @field_validator("project_name", mode="before")
    @classmethod
    def normalize_project_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "language",
        "framework",
        "frontend",
        "backend",
        "database",
        "output_requirement",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @field_validator("requirements")
    @classmethod
    def validate_requirements(
        cls, value: list[JsonObject] | None
    ) -> list[JsonObject] | None:
        if value is not None:
            for item in value:
                validate_json_object(item)
        return value

    @field_validator("architecture", "extensions")
    @classmethod
    def validate_json_fields(cls, value: JsonObject | None) -> JsonObject | None:
        return validate_json_object(value)

    @field_validator("features", "constraints", mode="before")
    @classmethod
    def normalize_text_items(cls, value: object) -> object:
        return _normalize_text_items(value)

    @field_validator("features", "constraints")
    @classmethod
    def validate_text_items(cls, value: list[str] | None) -> list[str] | None:
        return _validate_text_items(value) if value is not None else None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("至少提供一个上下文字段")
        for field_name in ("project_name", "difficulty"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"{field_name} 不能为 null")
        for field_name in ("features", "constraints"):
            value = getattr(self, field_name)
            if field_name in self.model_fields_set and value is None:
                raise ValueError(f"{field_name} 不能为 null，请使用空数组清空")
        return self


class StoredProjectContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=CONTEXT_SCHEMA_VERSION, ge=1)
    version: int = Field(ge=1)
    values: ProjectContextValues
    field_metadata: dict[str, ContextFieldMetadata]
    updated_at: datetime
    source: ContextSource

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value)

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        if self.schema_version != CONTEXT_SCHEMA_VERSION:
            raise ValueError("不支持的 ProjectContext schema_version")
        value_fields = set(ProjectContextValues.model_fields)
        if set(self.field_metadata) != value_fields:
            raise ValueError("field_metadata 必须覆盖全部上下文字段")
        if any(item.version > self.version for item in self.field_metadata.values()):
            raise ValueError("字段元数据版本不能高于上下文版本")
        current_metadata = [
            item
            for item in self.field_metadata.values()
            if item.version == self.version
        ]
        if not current_metadata or any(
            item.updated_at != self.updated_at or item.source != self.source
            for item in current_metadata
        ):
            raise ValueError("当前版本字段元数据必须与上下文来源和时间一致")
        encoded = json.dumps(
            self.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
        )
        if len(encoded.encode("utf-8")) > MAX_CONTEXT_BYTES:
            raise ValueError(f"项目上下文不能超过 {MAX_CONTEXT_BYTES} 字节")
        return self


CONTEXT_FIELDS = frozenset(ProjectContextValues.model_fields)
CORE_PROJECT_FIELD_MAP = {
    "project_name": "name",
    "language": "language",
    "framework": "framework",
    "frontend": "frontend",
    "backend": "backend",
    "database": "database",
    "difficulty": "difficulty",
    "requirements": "requirements",
    "output_requirement": "output_requirement",
}
