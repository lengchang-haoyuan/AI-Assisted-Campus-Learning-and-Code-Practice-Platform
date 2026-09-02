from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping

from app.context.context_schema import (
    CONTEXT_FIELDS,
    ContextFieldMetadata,
    ContextSource,
    JsonObject,
    ProjectContextPatch,
    ProjectContextValues,
    StoredProjectContext,
)
from app.context.project_context import ProjectContext


class ContextAccessError(ValueError):
    """节点尝试访问未授权的上下文字段。"""


class InvalidContextPolicyError(ValueError):
    """节点声明了无效的上下文权限。"""


@dataclass(frozen=True, slots=True)
class ContextNode:
    id: int
    node_type: str
    config: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class ContextEdge:
    source_node_id: int
    target_node_id: int


@dataclass(frozen=True, slots=True)
class ContextMergeResult:
    context: ProjectContext
    changed_fields: frozenset[str]


@dataclass(frozen=True, slots=True)
class NodeContextPolicy:
    reads: frozenset[str]
    writes: frozenset[str]


NODE_CONTEXT_POLICIES = {
    "requirements_analysis": NodeContextPolicy(
        reads=frozenset(
            {"project_name", "difficulty", "requirements", "output_requirement"}
        ),
        writes=frozenset({"requirements", "features", "constraints"}),
    ),
    "tech_stack_analysis": NodeContextPolicy(
        reads=frozenset(
            {"difficulty", "requirements", "features", "constraints"}
        ),
        writes=frozenset(
            {"language", "framework", "frontend", "backend", "database"}
        ),
    ),
    "architecture_design": NodeContextPolicy(
        reads=frozenset(
            {
                "language",
                "framework",
                "frontend",
                "backend",
                "database",
                "requirements",
                "features",
                "constraints",
            }
        ),
        writes=frozenset({"architecture"}),
    ),
    "project_structure": NodeContextPolicy(
        reads=frozenset(
            {
                "project_name",
                "language",
                "framework",
                "frontend",
                "backend",
                "database",
                "architecture",
                "requirements",
                "features",
                "constraints",
            }
        ),
        writes=frozenset(),
    ),
    "prompt": NodeContextPolicy(reads=CONTEXT_FIELDS, writes=frozenset()),
}


class ContextManager:
    def merge(
        self,
        current: ProjectContext,
        updates: Mapping[str, object],
        *,
        source: ContextSource,
        now: datetime | None = None,
    ) -> ContextMergeResult:
        patch = ProjectContextPatch.model_validate(dict(updates))
        changed_at = now or datetime.now(UTC)
        values = current.values.model_dump(mode="python")
        changed_fields: set[str] = set()

        for field_name in patch.model_fields_set:
            incoming = getattr(patch, field_name)
            if field_name in {"architecture", "extensions"}:
                existing = values[field_name]
                if incoming is None:
                    merged = None if field_name == "architecture" else {}
                else:
                    merged = self._merge_json_object(existing or {}, incoming)
                candidate = merged
            else:
                candidate = incoming
            if values[field_name] != candidate:
                values[field_name] = candidate
                changed_fields.add(field_name)

        if not changed_fields:
            return ContextMergeResult(current, frozenset())

        next_version = current.version + 1
        validated_values = ProjectContextValues.model_validate(values)
        metadata = dict(current.document.field_metadata)
        for field_name in changed_fields:
            metadata[field_name] = ContextFieldMetadata(
                version=next_version,
                updated_at=changed_at,
                source=source,
            )
        document = StoredProjectContext(
            schema_version=current.document.schema_version,
            version=next_version,
            values=validated_values,
            field_metadata=metadata,
            updated_at=changed_at,
            source=source,
        )
        return ContextMergeResult(ProjectContext(document), frozenset(changed_fields))

    def get_node_policy(self, node: ContextNode) -> NodeContextPolicy:
        base = NODE_CONTEXT_POLICIES.get(
            node.node_type, NodeContextPolicy(frozenset(), frozenset())
        )
        config = node.config or {}
        reads = self._narrow_policy(config, "context_reads", base.reads)
        writes = self._narrow_policy(config, "context_writes", base.writes)
        return NodeContextPolicy(reads=reads, writes=writes)

    def resolve_read_fields(
        self, node: ContextNode, requested_fields: Iterable[str] | None
    ) -> frozenset[str]:
        allowed = self.get_node_policy(node).reads
        requested = allowed if requested_fields is None else frozenset(requested_fields)
        unknown = requested - CONTEXT_FIELDS
        if unknown:
            raise ContextAccessError("请求包含未知上下文字段")
        if not requested <= allowed:
            raise ContextAccessError("节点无权读取请求的上下文字段")
        return requested

    def validate_node_write(
        self, node: ContextNode, updates: Mapping[str, object]
    ) -> ProjectContextPatch:
        patch = ProjectContextPatch.model_validate(dict(updates))
        requested = frozenset(patch.model_fields_set)
        if not requested <= self.get_node_policy(node).writes:
            raise ContextAccessError("节点无权写入请求的上下文字段")
        return patch

    def stale_node_ids(
        self,
        nodes: Iterable[ContextNode],
        edges: Iterable[ContextEdge],
        changed_fields: frozenset[str],
        *,
        source_node_id: int | None = None,
    ) -> frozenset[int]:
        node_list = list(nodes)
        direct = {
            node.id
            for node in node_list
            if node.id != source_node_id
            and bool(self.get_node_policy(node).reads & changed_fields)
        }
        adjacency: dict[int, list[int]] = {node.id: [] for node in node_list}
        for edge in edges:
            if edge.source_node_id in adjacency and edge.target_node_id in adjacency:
                adjacency[edge.source_node_id].append(edge.target_node_id)

        queue = deque(direct)
        if source_node_id is not None:
            queue.extend(adjacency.get(source_node_id, []))
        stale = set(queue)
        stale.discard(source_node_id)
        while queue:
            node_id = queue.popleft()
            for target_id in adjacency.get(node_id, []):
                if target_id != source_node_id and target_id not in stale:
                    stale.add(target_id)
                    queue.append(target_id)
        return frozenset(stale)

    @staticmethod
    def _merge_json_object(current: JsonObject, incoming: JsonObject) -> JsonObject:
        merged: JsonObject = dict(current)
        for key, value in incoming.items():
            if value is None:
                merged.pop(key, None)
            elif isinstance(value, dict) and isinstance(merged.get(key), dict):
                existing = merged[key]
                if not isinstance(existing, dict):
                    merged[key] = value
                else:
                    merged[key] = ContextManager._merge_json_object(existing, value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _narrow_policy(
        config: Mapping[str, Any], key: str, allowed: frozenset[str]
    ) -> frozenset[str]:
        if key not in config:
            return allowed
        value = config[key]
        if (
            not isinstance(value, list)
            or len(value) > len(CONTEXT_FIELDS)
            or any(not isinstance(item, str) for item in value)
        ):
            raise InvalidContextPolicyError(f"{key} 必须是有界字符串数组")
        declared = frozenset(value)
        if not declared <= allowed:
            raise InvalidContextPolicyError(f"{key} 不能扩大节点默认权限")
        return declared
