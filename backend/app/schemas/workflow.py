import json
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from app.models.enums import (
    AIRequestStatus,
    WorkflowNodeStatus,
    WorkflowRunStatus,
    WorkflowStatus,
)
from app.workflow.engine import WorkflowRunMode
from app.workflow.schemas import (
    ArchitectureDesignNodeResult,
    RequirementsAnalysisNodeResult,
    TechStackAnalysisNodeResult,
)

MAX_GRAPH_NODES = 100
MAX_GRAPH_EDGES = 300
MAX_JSON_BYTES = 65_536
NODE_KEY_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"
NODE_TYPE_PATTERN = r"^[a-z][a-z0-9_]{0,49}$"

JsonObject = dict[str, JsonValue]


def normalize_optional_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


def limit_json(value: JsonObject | None) -> JsonObject | None:
    if value is not None:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
            raise ValueError("JSON 内容不能超过 65536 字节")
    return value


class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5_000)
    status: WorkflowStatus = WorkflowStatus.DRAFT

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        return normalize_optional_text(value)


class WorkflowUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5_000)
    status: WorkflowStatus | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_changes(self) -> "WorkflowUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in ("name", "status"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class WorkflowProjectResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    project: WorkflowProjectResponse
    name: str
    description: str | None
    status: WorkflowStatus
    version: int
    node_count: int
    edge_count: int
    created_at: datetime
    updated_at: datetime


class WorkflowListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[WorkflowResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class WorkflowNodeFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_key: str = Field(min_length=1, max_length=64, pattern=NODE_KEY_PATTERN)
    node_type: str = Field(min_length=1, max_length=50, pattern=NODE_TYPE_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    position_x: float = Field(ge=-100_000, le=100_000)
    position_y: float = Field(ge=-100_000, le=100_000)
    config: JsonObject | None = None

    @field_validator("node_key", "node_type", "name", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: JsonObject | None) -> JsonObject | None:
        return limit_json(value)


class WorkflowNodeCreate(WorkflowNodeFields):
    pass


class WorkflowNodeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_key: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=NODE_KEY_PATTERN
    )
    node_type: str | None = Field(
        default=None, min_length=1, max_length=50, pattern=NODE_TYPE_PATTERN
    )
    name: str | None = Field(default=None, min_length=1, max_length=120)
    position_x: float | None = Field(default=None, ge=-100_000, le=100_000)
    position_y: float | None = Field(default=None, ge=-100_000, le=100_000)
    config: JsonObject | None = None

    @field_validator("node_key", "node_type", "name", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: JsonObject | None) -> JsonObject | None:
        return limit_json(value)

    @model_validator(mode="after")
    def validate_changes(self) -> "WorkflowNodeUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in ("node_key", "node_type", "name", "position_x", "position_y"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class WorkflowNodeResponse(WorkflowNodeFields):
    model_config = ConfigDict(frozen=True)

    id: int
    workflow_id: int
    status: WorkflowNodeStatus
    context_version: int
    created_at: datetime
    updated_at: datetime


class WorkflowNodeListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[WorkflowNodeResponse]
    total: int


class WorkflowEdgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_node_id: int = Field(ge=1)
    target_node_id: int = Field(ge=1)
    condition_data: JsonObject | None = None

    @field_validator("condition_data")
    @classmethod
    def validate_condition_data(
        cls, value: JsonObject | None
    ) -> JsonObject | None:
        return limit_json(value)


class WorkflowEdgeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_node_id: int | None = Field(default=None, ge=1)
    target_node_id: int | None = Field(default=None, ge=1)
    condition_data: JsonObject | None = None

    @field_validator("condition_data")
    @classmethod
    def validate_condition_data(
        cls, value: JsonObject | None
    ) -> JsonObject | None:
        return limit_json(value)

    @model_validator(mode="after")
    def validate_changes(self) -> "WorkflowEdgeUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in ("source_node_id", "target_node_id"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class WorkflowEdgeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    workflow_id: int
    source_node_id: int
    target_node_id: int
    source_node_key: str
    target_node_key: str
    condition_data: JsonObject | None
    created_at: datetime


class WorkflowEdgeListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[WorkflowEdgeResponse]
    total: int


class WorkflowGraphNode(WorkflowNodeFields):
    pass


class WorkflowGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_node_key: str = Field(
        min_length=1, max_length=64, pattern=NODE_KEY_PATTERN
    )
    target_node_key: str = Field(
        min_length=1, max_length=64, pattern=NODE_KEY_PATTERN
    )
    condition_data: JsonObject | None = None

    @field_validator("source_node_key", "target_node_key", mode="before")
    @classmethod
    def normalize_keys(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("condition_data")
    @classmethod
    def validate_condition_data(
        cls, value: JsonObject | None
    ) -> JsonObject | None:
        return limit_json(value)


class WorkflowGraphUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    nodes: list[WorkflowGraphNode] = Field(max_length=MAX_GRAPH_NODES)
    edges: list[WorkflowGraphEdge] = Field(max_length=MAX_GRAPH_EDGES)

    @model_validator(mode="after")
    def validate_unique_node_keys(self) -> "WorkflowGraphUpdate":
        keys = [node.node_key for node in self.nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("节点 key 不能重复")
        return self


class WorkflowGraphResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    workflow: WorkflowResponse
    nodes: list[WorkflowNodeResponse]
    edges: list[WorkflowEdgeResponse]


WorkflowNodeResultResponse = Annotated[
    RequirementsAnalysisNodeResult
    | TechStackAnalysisNodeResult
    | ArchitectureDesignNodeResult,
    Field(discriminator="result_type"),
]


class WorkflowRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    mode: WorkflowRunMode = WorkflowRunMode.INCOMPLETE


class WorkflowRunErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class WorkflowRunNodeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: int
    node_id: int
    node_key: str
    node_type: str
    status: AIRequestStatus
    result: WorkflowNodeResultResponse | None
    error: WorkflowRunErrorResponse | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None
    requested_at: datetime
    finished_at: datetime | None


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    workflow_id: int
    status: WorkflowRunStatus
    context_version: int
    error: WorkflowRunErrorResponse | None
    nodes: list[WorkflowRunNodeResponse]
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class WorkflowRunListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[WorkflowRunResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
