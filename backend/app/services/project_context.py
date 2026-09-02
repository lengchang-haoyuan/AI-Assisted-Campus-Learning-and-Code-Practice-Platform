from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from pydantic import ValidationError

from app.context.context_manager import (
    ContextAccessError,
    ContextEdge,
    ContextManager,
    ContextMergeResult,
    ContextNode,
    InvalidContextPolicyError,
)
from app.context.context_schema import (
    CORE_PROJECT_FIELD_MAP,
    ContextFieldMetadata,
    ContextSource,
    ContextSourceType,
    ProjectContextValues,
)
from app.context.project_context import (
    ContextBuilder,
    InvalidProjectContextError,
    ProjectContext,
    ProjectContextSeed,
)
from app.core.exceptions import (
    ConflictError,
    InputError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models.enums import WorkflowNodeStatus
from app.models.project import Project
from app.models.workflow import WorkflowNode
from app.repositories.project_context import (
    ProjectContextPersistenceError,
    ProjectContextRepository,
)


@dataclass(frozen=True, slots=True)
class ProjectContextUpdateData:
    expected_version: int
    values: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class NodeContextReadData:
    fields: list[str] | None


@dataclass(frozen=True, slots=True)
class NodeContextWriteData:
    expected_version: int
    values: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ProjectContextData:
    project_id: int
    version: int
    values: ProjectContextValues
    field_metadata: dict[str, ContextFieldMetadata]
    updated_at: datetime
    source: ContextSource
    is_stale: bool
    stale_fields: list[str]
    stale_node_ids: list[int]


@dataclass(frozen=True, slots=True)
class ProjectContextMutationData:
    context: ProjectContextData
    changed_fields: list[str]
    stale_node_ids: list[int]


@dataclass(frozen=True, slots=True)
class NodeContextData:
    project_id: int
    workflow_id: int
    node_id: int
    node_key: str
    context_version: int
    values: dict[str, Any]
    is_stale: bool


class ProjectContextService:
    def __init__(
        self,
        repository: ProjectContextRepository,
        manager: ContextManager | None = None,
        builder: ContextBuilder | None = None,
    ) -> None:
        self._repository = repository
        self._manager = manager or ContextManager()
        self._builder = builder or ContextBuilder()

    def create_context(self, project_id: int, owner_id: int) -> ProjectContextData:
        project = self._get_owned_project(project_id, owner_id, for_update=True)
        if project.context_data is not None:
            raise ConflictError("项目上下文已经存在")
        context = self._builder.build(
            self._seed_from_project(project),
            source=ContextSource(type=ContextSourceType.PROJECT, id=project.id),
        )
        project.context_data = context.to_storage()
        try:
            saved = self._repository.save(project)
        except ProjectContextPersistenceError as exc:
            raise ConflictError("项目上下文与当前数据状态冲突") from exc
        return self._to_context_data(saved, self._load_context(saved))

    def get_context(self, project_id: int, owner_id: int) -> ProjectContextData:
        project = self._get_owned_project(project_id, owner_id)
        context = self._load_context(project)
        return self._to_context_data(project, context)

    def update_context(
        self,
        project_id: int,
        owner_id: int,
        data: ProjectContextUpdateData,
    ) -> ProjectContextMutationData:
        project = self._get_owned_project(project_id, owner_id, for_update=True)
        context = self._load_context(project)
        self._validate_version(context, data.expected_version)
        source = ContextSource(type=ContextSourceType.USER, id=owner_id)
        result = self._merge(context, data.values, source=source)
        if not result.changed_fields:
            return ProjectContextMutationData(
                context=self._to_context_data(project, context),
                changed_fields=[],
                stale_node_ids=[],
            )
        stale_node_ids = self._apply_context_update(
            project,
            result.context,
            result.changed_fields,
        )
        saved = self._save(project)
        persisted = self._load_context(saved)
        return ProjectContextMutationData(
            context=self._to_context_data(saved, persisted),
            changed_fields=sorted(result.changed_fields),
            stale_node_ids=sorted(stale_node_ids),
        )

    def read_node_context(
        self,
        workflow_id: int,
        node_id: int,
        owner_id: int,
        data: NodeContextReadData,
    ) -> NodeContextData:
        node = self._get_owned_node(workflow_id, node_id, owner_id)
        project = node.workflow.project
        context = self._load_context(project)
        stale_fields = self._stale_fields(project, context)
        if stale_fields:
            raise ConflictError("项目上下文已过期，请先同步变更字段")
        descriptor = self._node_descriptor(node)
        try:
            fields = self._manager.resolve_read_fields(descriptor, data.fields)
        except ContextAccessError as exc:
            raise PermissionDeniedError(str(exc)) from exc
        except InvalidContextPolicyError as exc:
            raise ConflictError("节点上下文权限配置无效") from exc
        values = context.values.model_dump(mode="json", include=fields)
        return NodeContextData(
            project_id=project.id,
            workflow_id=workflow_id,
            node_id=node.id,
            node_key=node.node_key,
            context_version=context.version,
            values=values,
            is_stale=node.status == WorkflowNodeStatus.STALE,
        )

    def write_node_context(
        self,
        workflow_id: int,
        node_id: int,
        owner_id: int,
        data: NodeContextWriteData,
    ) -> ProjectContextMutationData:
        initial_node = self._get_owned_node(workflow_id, node_id, owner_id)
        project = self._get_owned_project(
            initial_node.workflow.project_id, owner_id, for_update=True
        )
        node = self._find_project_node(project, workflow_id, node_id)
        context = self._load_context(project)
        if self._stale_fields(project, context):
            raise ConflictError("项目上下文已过期，请先同步变更字段")
        self._validate_version(context, data.expected_version)
        descriptor = self._node_descriptor(node)
        try:
            patch = self._manager.validate_node_write(descriptor, data.values)
        except ContextAccessError as exc:
            raise PermissionDeniedError(str(exc)) from exc
        except InvalidContextPolicyError as exc:
            raise ConflictError("节点上下文权限配置无效") from exc
        source = ContextSource(
            type=ContextSourceType.WORKFLOW_NODE,
            id=node.id,
            node_key=node.node_key,
        )
        result = self._merge(
            context,
            patch.model_dump(exclude_unset=True),
            source=source,
        )
        if not result.changed_fields:
            return ProjectContextMutationData(
                context=self._to_context_data(project, context),
                changed_fields=[],
                stale_node_ids=[],
            )
        stale_node_ids = self._apply_context_update(
            project,
            result.context,
            result.changed_fields,
            source_node_id=node.id,
        )
        node.context_version = result.context.version
        saved = self._save(project)
        persisted = self._load_context(saved)
        return ProjectContextMutationData(
            context=self._to_context_data(saved, persisted),
            changed_fields=sorted(result.changed_fields),
            stale_node_ids=sorted(stale_node_ids),
        )

    def _apply_context_update(
        self,
        project: Project,
        context: ProjectContext,
        changed_fields: frozenset[str],
        *,
        source_node_id: int | None = None,
    ) -> frozenset[int]:
        project.context_data = context.to_storage()
        values = context.values.model_dump(mode="python")
        for context_field, project_field in CORE_PROJECT_FIELD_MAP.items():
            if context_field in changed_fields:
                setattr(project, project_field, values[context_field])

        nodes = [node for workflow in project.workflows for node in workflow.nodes]
        edges = [edge for workflow in project.workflows for edge in workflow.edges]
        try:
            stale_node_ids = self._manager.stale_node_ids(
                [self._node_descriptor(node) for node in nodes],
                [
                    ContextEdge(edge.source_node_id, edge.target_node_id)
                    for edge in edges
                ],
                changed_fields,
                source_node_id=source_node_id,
            )
        except InvalidContextPolicyError as exc:
            raise ConflictError("节点上下文权限配置无效") from exc
        for node in nodes:
            if node.id in stale_node_ids:
                node.status = WorkflowNodeStatus.STALE
        return stale_node_ids

    def _save(self, project: Project) -> Project:
        try:
            return self._repository.save(project)
        except ProjectContextPersistenceError as exc:
            raise ConflictError("项目上下文与当前数据状态冲突") from exc

    def _merge(
        self,
        context: ProjectContext,
        values: Mapping[str, object],
        *,
        source: ContextSource,
    ) -> ContextMergeResult:
        try:
            return self._manager.merge(context, values, source=source)
        except ValidationError as exc:
            raise InputError("项目上下文字段无效") from exc

    def _get_owned_project(
        self, project_id: int, owner_id: int, *, for_update: bool = False
    ) -> Project:
        project = self._repository.get_project(project_id, for_update=for_update)
        if project is None:
            raise ResourceNotFoundError("项目不存在")
        if project.owner_id != owner_id:
            raise PermissionDeniedError("无权访问该项目的上下文")
        return project

    def _get_owned_node(
        self, workflow_id: int, node_id: int, owner_id: int
    ) -> WorkflowNode:
        node = self._repository.get_node(workflow_id, node_id)
        if node is None:
            raise ResourceNotFoundError("工作流节点不存在")
        if node.workflow.project.owner_id != owner_id:
            raise PermissionDeniedError("无权访问该节点的项目上下文")
        return node

    @staticmethod
    def _find_project_node(
        project: Project, workflow_id: int, node_id: int
    ) -> WorkflowNode:
        node = next(
            (
                node
                for workflow in project.workflows
                if workflow.id == workflow_id
                for node in workflow.nodes
                if node.id == node_id
            ),
            None,
        )
        if node is None:
            raise ResourceNotFoundError("工作流节点不存在")
        return node

    @staticmethod
    def _load_context(project: Project) -> ProjectContext:
        if project.context_data is None:
            raise ResourceNotFoundError("项目上下文尚未创建")
        try:
            return ProjectContext.from_storage(project.context_data)
        except InvalidProjectContextError as exc:
            raise ConflictError("项目上下文格式无效，需要修复后重试") from exc

    @staticmethod
    def _validate_version(context: ProjectContext, expected_version: int) -> None:
        if context.version != expected_version:
            raise ConflictError("项目上下文已被更新，请刷新后重试")

    @staticmethod
    def _seed_from_project(project: Project) -> ProjectContextSeed:
        return ProjectContextSeed(
            project_name=project.name,
            language=project.language,
            framework=project.framework,
            frontend=project.frontend,
            backend=project.backend,
            database=project.database,
            difficulty=project.difficulty,
            requirements=project.requirements,
            output_requirement=project.output_requirement,
        )

    @staticmethod
    def _node_descriptor(node: WorkflowNode) -> ContextNode:
        return ContextNode(id=node.id, node_type=node.node_type, config=node.config)

    @staticmethod
    def _stale_fields(project: Project, context: ProjectContext) -> list[str]:
        stale: list[str] = []
        for context_field, project_field in CORE_PROJECT_FIELD_MAP.items():
            project_value = getattr(project, project_field)
            context_value = getattr(context.values, context_field)
            if project_value != context_value:
                stale.append(context_field)
        return sorted(stale)

    def _to_context_data(
        self, project: Project, context: ProjectContext
    ) -> ProjectContextData:
        stale_node_ids = sorted(
            node.id
            for workflow in project.workflows
            for node in workflow.nodes
            if node.status == WorkflowNodeStatus.STALE
        )
        stale_fields = self._stale_fields(project, context)
        return ProjectContextData(
            project_id=project.id,
            version=context.version,
            values=context.values,
            field_metadata=dict(context.document.field_metadata),
            updated_at=context.document.updated_at,
            source=context.document.source,
            is_stale=bool(stale_fields),
            stale_fields=stale_fields,
            stale_node_ids=stale_node_ids,
        )
