from datetime import UTC, datetime
from decimal import Decimal
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

from pydantic import ValidationError

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_current_user, get_project_context_service
from app.context.context_manager import (
    ContextManager,
    ContextNode,
    InvalidContextPolicyError,
)
from app.context.context_schema import ContextSource, ContextSourceType
from app.context.project_context import ContextBuilder, ProjectContextSeed
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.main import create_app
from app.models.enums import (
    ProjectDifficulty,
    ProjectStatus,
    WorkflowNodeStatus,
    WorkflowStatus,
)
from app.models.project import Project
from app.models.workflow import Workflow, WorkflowEdge, WorkflowNode
from app.repositories.project_context import ProjectContextRepository
from app.schemas.project_context import ProjectContextUpdateRequest
from app.services.auth import UserIdentity
from app.services.project_context import (
    NodeContextReadData,
    NodeContextWriteData,
    ProjectContextData,
    ProjectContextMutationData,
    ProjectContextService,
    ProjectContextUpdateData,
)
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)


def make_context_data() -> dict[str, object]:
    return ContextBuilder().build(
        ProjectContextSeed(
            project_name="ScholarHub",
            language="Python",
            framework="FastAPI",
            frontend="Vue 3",
            backend="FastAPI",
            database="MySQL",
            difficulty=ProjectDifficulty.INTERMEDIATE,
            requirements=[{"title": "项目上下文"}],
            output_requirement="可运行代码",
        ),
        source=ContextSource(type=ContextSourceType.PROJECT, id=7),
        now=NOW,
    ).to_storage()


def make_node(
    node_id: int,
    node_key: str,
    node_type: str,
    *,
    config: dict[str, object] | None = None,
) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        workflow_id=11,
        node_key=node_key,
        node_type=node_type,
        name=node_key,
        position_x=Decimal("0.00"),
        position_y=Decimal("0.00"),
        config=config,
        status=WorkflowNodeStatus.PENDING,
        context_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def make_project(
    *,
    owner_id: int = 1,
    with_context: bool = True,
    with_workflow: bool = True,
) -> Project:
    project = Project(
        id=7,
        owner_id=owner_id,
        name="ScholarHub",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        status=ProjectStatus.IN_PROGRESS,
        language="Python",
        framework="FastAPI",
        frontend="Vue 3",
        backend="FastAPI",
        database="MySQL",
        requirements=[{"title": "项目上下文"}],
        output_requirement="可运行代码",
        context_data=make_context_data() if with_context else None,
        created_at=NOW,
        updated_at=NOW,
    )
    project.workflows = []
    if not with_workflow:
        return project

    tech = make_node(21, "tech", "tech_stack_analysis")
    structure = make_node(22, "structure", "project_structure")
    prompt = make_node(23, "prompt", "prompt")
    workflow = Workflow(
        id=11,
        project_id=7,
        name="项目分析",
        status=WorkflowStatus.DRAFT,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    workflow.project = project
    workflow.nodes = [tech, structure, prompt]
    workflow.edges = [
        WorkflowEdge(
            id=31,
            workflow_id=11,
            source_node_id=21,
            target_node_id=22,
            condition_data=None,
            created_at=NOW,
        ),
        WorkflowEdge(
            id=32,
            workflow_id=11,
            source_node_id=22,
            target_node_id=23,
            condition_data=None,
            created_at=NOW,
        ),
    ]
    project.workflows = [workflow]
    return project


class ProjectContextServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=ProjectContextRepository)
        self.service = ProjectContextService(
            self.repository,
            manager=ContextManager(),
            builder=ContextBuilder(),
        )

    def test_create_context_builds_versioned_document_from_project(self) -> None:
        project = make_project(with_context=False, with_workflow=False)
        self.repository.get_project.return_value = project
        self.repository.save.return_value = project

        result = self.service.create_context(7, 1)

        self.assertEqual(result.version, 1)
        self.assertEqual(result.values.project_name, "ScholarHub")
        self.assertEqual(result.values.language, "Python")
        self.assertEqual(result.source.type, ContextSourceType.PROJECT)
        self.assertEqual(result.field_metadata["language"].version, 1)
        self.repository.get_project.assert_called_once_with(7, for_update=True)
        self.repository.save.assert_called_once_with(project)

    def test_language_update_marks_structure_and_prompt_nodes_stale(self) -> None:
        project = make_project()
        self.repository.get_project.return_value = project
        self.repository.save.return_value = project

        result = self.service.update_context(
            7,
            1,
            ProjectContextUpdateData(
                expected_version=1,
                values={"language": "Java"},
            ),
        )

        self.assertEqual(result.context.version, 2)
        self.assertEqual(result.context.values.language, "Java")
        self.assertEqual(project.language, "Java")
        self.assertEqual(result.changed_fields, ["language"])
        self.assertEqual(result.stale_node_ids, [22, 23])
        self.assertEqual(
            project.workflows[0].nodes[0].status,
            WorkflowNodeStatus.PENDING,
        )
        self.assertEqual(project.workflows[0].nodes[1].status, WorkflowNodeStatus.STALE)
        self.assertEqual(project.workflows[0].nodes[2].status, WorkflowNodeStatus.STALE)

    def test_update_rejects_stale_version_without_saving(self) -> None:
        self.repository.get_project.return_value = make_project()

        with self.assertRaises(ConflictError):
            self.service.update_context(
                7,
                1,
                ProjectContextUpdateData(
                    expected_version=2,
                    values={"language": "Java"},
                ),
            )

        self.repository.save.assert_not_called()

    def test_update_rejects_invalid_node_policy_without_saving(self) -> None:
        project = make_project()
        project.workflows[0].nodes[2].config = {"context_writes": ["language"]}
        self.repository.get_project.return_value = project

        with self.assertRaises(ConflictError):
            self.service.update_context(
                7,
                1,
                ProjectContextUpdateData(1, {"language": "Java"}),
            )

        self.repository.save.assert_not_called()

    def test_project_column_drift_is_reported_and_blocks_node_read(self) -> None:
        project = make_project()
        project.language = "Java"
        self.repository.get_project.return_value = project
        self.repository.get_node.return_value = project.workflows[0].nodes[1]

        result = self.service.get_context(7, 1)
        self.assertTrue(result.is_stale)
        self.assertEqual(result.stale_fields, ["language"])
        with self.assertRaises(ConflictError):
            self.service.read_node_context(
                11,
                22,
                1,
                NodeContextReadData(fields=["language"]),
            )

    def test_node_reads_only_allowed_fields(self) -> None:
        project = make_project()
        node = project.workflows[0].nodes[1]
        self.repository.get_node.return_value = node

        result = self.service.read_node_context(
            11,
            22,
            1,
            NodeContextReadData(fields=["language", "architecture"]),
        )
        self.assertEqual(result.values["language"], "Python")
        self.assertIn("architecture", result.values)

        with self.assertRaises(PermissionDeniedError):
            self.service.read_node_context(
                11,
                22,
                1,
                NodeContextReadData(fields=["extensions"]),
            )

    def test_node_write_updates_version_and_invalidates_descendants(self) -> None:
        project = make_project()
        source_node = project.workflows[0].nodes[0]
        self.repository.get_node.return_value = source_node
        self.repository.get_project.return_value = project
        self.repository.save.return_value = project

        result = self.service.write_node_context(
            11,
            21,
            1,
            NodeContextWriteData(
                expected_version=1,
                values={"language": "Java", "framework": "Spring Boot"},
            ),
        )

        self.assertEqual(result.context.version, 2)
        self.assertEqual(result.stale_node_ids, [22, 23])
        self.assertEqual(source_node.context_version, 2)
        self.assertEqual(result.context.source.type, ContextSourceType.WORKFLOW_NODE)

    def test_prompt_node_cannot_overwrite_language(self) -> None:
        project = make_project()
        prompt = project.workflows[0].nodes[2]
        self.repository.get_node.return_value = prompt
        self.repository.get_project.return_value = project

        with self.assertRaises(PermissionDeniedError):
            self.service.write_node_context(
                11,
                23,
                1,
                NodeContextWriteData(1, {"language": "Java"}),
            )

        self.repository.save.assert_not_called()

    def test_context_access_is_isolated_by_project_owner(self) -> None:
        self.repository.get_project.return_value = make_project(owner_id=2)
        with self.assertRaises(PermissionDeniedError):
            self.service.get_context(7, 1)


class ProjectContextSchemaTests(unittest.TestCase):
    def test_schema_rejects_extra_and_sensitive_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectContextUpdateRequest.model_validate(
                {
                    "expected_version": 1,
                    "values": {"unknown": "value"},
                }
            )
        with self.assertRaises(ValidationError):
            ProjectContextUpdateRequest.model_validate(
                {
                    "expected_version": 1,
                    "values": {"extensions": {"api_key": "not-allowed"}},
                }
            )

    def test_merge_deep_merges_objects_and_preserves_version_on_noop(self) -> None:
        context = ContextBuilder().build(
            ProjectContextSeed(
                project_name="ScholarHub",
                language="Python",
                framework="FastAPI",
                frontend="Vue 3",
                backend="FastAPI",
                database="MySQL",
                difficulty=ProjectDifficulty.INTERMEDIATE,
                requirements=None,
                output_requirement=None,
            ),
            source=ContextSource(type=ContextSourceType.PROJECT, id=7),
            now=NOW,
        )
        manager = ContextManager()
        source = ContextSource(type=ContextSourceType.USER, id=1)
        first = manager.merge(
            context,
            {
                "architecture": {"api": {"style": "REST", "version": 1}},
                "features": [" 认证 ", "认证"],
            },
            source=source,
            now=NOW,
        )
        second = manager.merge(
            first.context,
            {"architecture": {"api": {"version": None, "prefix": "/api/v1"}}},
            source=source,
            now=NOW,
        )
        noop = manager.merge(
            second.context,
            {"features": ["认证"]},
            source=source,
            now=NOW,
        )

        self.assertEqual(first.context.values.features, ["认证"])
        self.assertEqual(
            second.context.values.architecture,
            {"api": {"style": "REST", "prefix": "/api/v1"}},
        )
        self.assertEqual(second.context.version, 3)
        self.assertEqual(noop.context.version, 3)
        self.assertEqual(noop.changed_fields, frozenset())

    def test_node_config_can_narrow_but_not_expand_default_policy(self) -> None:
        manager = ContextManager()
        narrowed = manager.get_node_policy(
            ContextNode(
                id=21,
                node_type="tech_stack_analysis",
                config={"context_writes": ["language"]},
            )
        )
        self.assertEqual(narrowed.writes, frozenset({"language"}))
        with self.assertRaises(InvalidContextPolicyError):
            manager.get_node_policy(
                ContextNode(
                    id=23,
                    node_type="prompt",
                    config={"context_writes": ["language"]},
                )
            )

    def test_context_metadata_rejects_naive_datetime(self) -> None:
        source = ContextSource(type=ContextSourceType.USER, id=1)
        context = ContextBuilder().build(
            ProjectContextSeed(
                project_name="ScholarHub",
                language=None,
                framework=None,
                frontend=None,
                backend=None,
                database=None,
                difficulty=ProjectDifficulty.BEGINNER,
                requirements=None,
                output_requirement=None,
            ),
            source=source,
            now=NOW,
        )
        payload = context.to_storage()
        payload["updated_at"] = "2026-09-02T08:00:00"
        with self.assertRaises(ValidationError):
            type(context.document).model_validate(payload)


class ProjectContextAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=ProjectContextService)
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="student",
            email="student@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_project_context_service] = (
            lambda: self.service
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    @staticmethod
    def context_data() -> ProjectContextData:
        project = make_project()
        service = ProjectContextService(Mock(spec=ProjectContextRepository))
        context = service._load_context(project)
        return service._to_context_data(project, context)

    def test_context_routes_require_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_project_context_service] = lambda: self.service
        for method, path, body in (
            ("POST", "/api/v1/projects/7/context", None),
            ("GET", "/api/v1/projects/7/context", None),
            (
                "POST",
                "/api/v1/workflows/11/nodes/21/context/read",
                {"fields": ["requirements"]},
            ),
        ):
            with self.subTest(method=method, path=path):
                response = request(app, method, path, body=body)
                self.assertEqual(response.status_code, 401)

    def test_update_route_maps_version_and_changes(self) -> None:
        context = self.context_data()
        self.service.update_context.return_value = ProjectContextMutationData(
            context=context,
            changed_fields=["language"],
            stale_node_ids=[22, 23],
        )

        response = request(
            self.app,
            "PUT",
            "/api/v1/projects/7/context",
            body={"expected_version": 1, "values": {"language": "Java"}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["changed_fields"], ["language"])
        call = self.service.update_context.call_args.args
        self.assertEqual(call[0:2], (7, 1))
        self.assertEqual(call[2].expected_version, 1)
        self.assertEqual(call[2].values, {"language": "Java"})

    def test_invalid_context_payload_returns_422(self) -> None:
        response = request(
            self.app,
            "PUT",
            "/api/v1/projects/7/context",
            body={"expected_version": 1, "values": {"project_name": None}},
        )
        self.assertEqual(response.status_code, 422)
        self.service.update_context.assert_not_called()


if __name__ == "__main__":
    unittest.main()
