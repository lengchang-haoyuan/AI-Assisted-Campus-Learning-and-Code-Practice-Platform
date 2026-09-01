from datetime import UTC, datetime
from decimal import Decimal
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

from pydantic import ValidationError
from sqlalchemy.orm import Session

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_current_user, get_workflow_service
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
from app.repositories.workflow import (
    WorkflowRepository,
    WorkflowVersionConflictError,
)
from app.schemas.workflow import WorkflowGraphUpdate
from app.services.auth import UserIdentity
from app.services.workflow import (
    WorkflowCreateData,
    WorkflowData,
    WorkflowEdgeCreateData,
    WorkflowEdgeData,
    WorkflowGraphData,
    WorkflowGraphEdgeData,
    WorkflowGraphNodeData,
    WorkflowGraphUpdateData,
    WorkflowNodeData,
    WorkflowPage,
    WorkflowProjectData,
    WorkflowService,
)
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def make_project(*, owner_id: int = 1) -> Project:
    return Project(
        id=7,
        owner_id=owner_id,
        name="ScholarHub",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        status=ProjectStatus.IN_PROGRESS,
        created_at=NOW,
        updated_at=NOW,
    )


def make_node(node_id: int, node_key: str, name: str) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        workflow_id=11,
        node_key=node_key,
        node_type=node_key,
        name=name,
        position_x=Decimal("120.00"),
        position_y=Decimal("180.00"),
        config={"instruction": name},
        status=WorkflowNodeStatus.PENDING,
        context_version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def make_edge(edge_id: int, source_id: int, target_id: int) -> WorkflowEdge:
    return WorkflowEdge(
        id=edge_id,
        workflow_id=11,
        source_node_id=source_id,
        target_node_id=target_id,
        condition_data=None,
        created_at=NOW,
    )


def make_workflow(
    *,
    owner_id: int = 1,
    version: int = 3,
    nodes: list[WorkflowNode] | None = None,
    edges: list[WorkflowEdge] | None = None,
) -> Workflow:
    workflow = Workflow(
        id=11,
        project_id=7,
        name="课程项目分析",
        description=None,
        status=WorkflowStatus.DRAFT,
        version=version,
        created_at=NOW,
        updated_at=NOW,
    )
    workflow.project = make_project(owner_id=owner_id)
    workflow.nodes = nodes or []
    workflow.edges = edges or []
    return workflow


def graph_node(node_key: str, name: str) -> WorkflowGraphNodeData:
    return WorkflowGraphNodeData(
        node_key=node_key,
        node_type=node_key,
        name=name,
        position_x=120.0,
        position_y=180.0,
        config={"instruction": name},
    )


class WorkflowServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=WorkflowRepository)
        self.service = WorkflowService(self.repository)

    def test_create_workflow_checks_project_ownership(self) -> None:
        self.repository.get_project.return_value = make_project(owner_id=2)

        with self.assertRaises(PermissionDeniedError):
            self.service.create_workflow(
                1,
                WorkflowCreateData(
                    project_id=7,
                    name="越权工作流",
                    description=None,
                    status=WorkflowStatus.DRAFT,
                ),
            )

        self.repository.create_workflow.assert_not_called()

    def test_replace_graph_persists_two_nodes_and_one_edge(self) -> None:
        empty = make_workflow()
        self.repository.get_workflow.return_value = empty
        saved_nodes = [
            make_node(21, "requirements_analysis", "需求分析"),
            make_node(22, "tech_stack_analysis", "技术栈分析"),
        ]
        saved = make_workflow(
            version=4,
            nodes=saved_nodes,
            edges=[make_edge(31, 21, 22)],
        )
        self.repository.replace_graph.return_value = saved

        result = self.service.replace_graph(
            11,
            1,
            WorkflowGraphUpdateData(
                version=3,
                nodes=[
                    graph_node("requirements_analysis", "需求分析"),
                    graph_node("tech_stack_analysis", "技术栈分析"),
                ],
                edges=[
                    WorkflowGraphEdgeData(
                        source_node_key="requirements_analysis",
                        target_node_key="tech_stack_analysis",
                        condition_data=None,
                    )
                ],
            ),
        )

        self.assertEqual(result.workflow.version, 4)
        self.assertEqual(result.edges[0].source_node_key, "requirements_analysis")
        self.assertEqual(result.edges[0].target_node_key, "tech_stack_analysis")
        call = self.repository.replace_graph.call_args
        self.assertEqual(call.kwargs["expected_version"], 3)
        self.assertEqual(len(call.kwargs["nodes"]), 2)
        self.assertEqual(len(call.kwargs["edges"]), 1)

    def test_replace_graph_rejects_stale_version(self) -> None:
        self.repository.get_workflow.return_value = make_workflow(version=4)
        with self.assertRaises(ConflictError):
            self.service.replace_graph(
                11,
                1,
                WorkflowGraphUpdateData(version=3, nodes=[], edges=[]),
            )
        self.repository.replace_graph.assert_not_called()

    def test_graph_rejects_missing_duplicate_self_and_cycle_edges(self) -> None:
        self.repository.get_workflow.return_value = make_workflow()
        nodes = [graph_node("a", "需求分析"), graph_node("b", "技术栈分析")]
        invalid_edges = (
            [WorkflowGraphEdgeData("a", "missing", None)],
            [
                WorkflowGraphEdgeData("a", "b", None),
                WorkflowGraphEdgeData("a", "b", None),
            ],
            [WorkflowGraphEdgeData("a", "a", None)],
            [
                WorkflowGraphEdgeData("a", "b", None),
                WorkflowGraphEdgeData("b", "a", None),
            ],
        )

        for edges in invalid_edges:
            with self.subTest(edges=edges), self.assertRaises(ConflictError):
                self.service.replace_graph(
                    11,
                    1,
                    WorkflowGraphUpdateData(version=3, nodes=nodes, edges=edges),
                )
        self.repository.replace_graph.assert_not_called()

    def test_individual_edge_creation_rejects_cycle(self) -> None:
        nodes = [make_node(21, "a", "需求分析"), make_node(22, "b", "技术栈分析")]
        self.repository.get_workflow.return_value = make_workflow(
            nodes=nodes, edges=[make_edge(31, 21, 22)]
        )

        with self.assertRaises(ConflictError):
            self.service.create_edge(
                11,
                1,
                WorkflowEdgeCreateData(
                    source_node_id=22,
                    target_node_id=21,
                    condition_data=None,
                ),
            )
        self.repository.create_edge.assert_not_called()

    def test_graph_schema_limits_nodes_and_normalizes_keys(self) -> None:
        payload = {
            "version": 1,
            "nodes": [
                {
                    "node_key": f"n{index}",
                    "node_type": "analysis",
                    "name": "节点",
                    "position_x": 0,
                    "position_y": 0,
                }
                for index in range(101)
            ],
            "edges": [],
        }
        with self.assertRaises(ValidationError):
            WorkflowGraphUpdate.model_validate(payload)


class WorkflowRepositoryTests(unittest.TestCase):
    def test_replace_graph_rechecks_version_inside_transaction(self) -> None:
        session = Mock(spec=Session)
        session.scalar.return_value = 4
        repository = WorkflowRepository(session)

        with self.assertRaises(WorkflowVersionConflictError):
            repository.replace_graph(
                make_workflow(version=3),
                expected_version=3,
                nodes=[],
                edges=[],
            )

        session.rollback.assert_called_once_with()
        session.commit.assert_not_called()


class WorkflowAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=WorkflowService)
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="student",
            email="student@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_workflow_service] = lambda: self.service

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_workflow_routes_require_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_workflow_service] = lambda: self.service
        for method, path, body in (
            ("GET", "/api/v1/workflows", None),
            ("GET", "/api/v1/workflows/1/graph", None),
            ("POST", "/api/v1/workflows/1/nodes", {}),
            ("POST", "/api/v1/workflows/1/edges", {}),
        ):
            with self.subTest(method=method, path=path):
                response = request(app, method, path, body=body)
                self.assertEqual(response.status_code, 401)

    def test_list_and_graph_routes_map_service_results(self) -> None:
        workflow = WorkflowData(
            id=11,
            project=WorkflowProjectData(id=7, name="ScholarHub"),
            name="课程项目分析",
            description=None,
            status=WorkflowStatus.DRAFT,
            version=4,
            node_count=2,
            edge_count=1,
            created_at=NOW,
            updated_at=NOW,
        )
        nodes = [
            WorkflowNodeData(
                id=21,
                workflow_id=11,
                node_key="requirements_analysis",
                node_type="requirements_analysis",
                name="需求分析",
                position_x=120.0,
                position_y=180.0,
                config={"instruction": "梳理需求"},
                status=WorkflowNodeStatus.PENDING,
                context_version=1,
                created_at=NOW,
                updated_at=NOW,
            ),
            WorkflowNodeData(
                id=22,
                workflow_id=11,
                node_key="tech_stack_analysis",
                node_type="tech_stack_analysis",
                name="技术栈分析",
                position_x=420.0,
                position_y=180.0,
                config=None,
                status=WorkflowNodeStatus.PENDING,
                context_version=1,
                created_at=NOW,
                updated_at=NOW,
            ),
        ]
        edge = WorkflowEdgeData(
            id=31,
            workflow_id=11,
            source_node_id=21,
            target_node_id=22,
            source_node_key="requirements_analysis",
            target_node_key="tech_stack_analysis",
            condition_data=None,
            created_at=NOW,
        )
        self.service.list_workflows.return_value = WorkflowPage(
            [workflow], 1, 1, 20, 1
        )
        self.service.get_graph.return_value = WorkflowGraphData(
            workflow, nodes, [edge]
        )

        listing = request(self.app, "GET", "/api/v1/workflows")
        graph = request(self.app, "GET", "/api/v1/workflows/11/graph")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["items"][0]["node_count"], 2)
        self.assertEqual(graph.status_code, 200)
        self.assertEqual(graph.json()["nodes"][0]["name"], "需求分析")
        self.assertEqual(graph.json()["edges"][0]["target_node_key"], "tech_stack_analysis")

    def test_graph_payload_boundary_returns_422(self) -> None:
        response = request(
            self.app,
            "PUT",
            "/api/v1/workflows/11/graph",
            body={
                "version": 1,
                "nodes": [
                    {
                        "node_key": "duplicate",
                        "node_type": "analysis",
                        "name": "节点",
                        "position_x": 0,
                        "position_y": 0,
                    },
                    {
                        "node_key": "duplicate",
                        "node_type": "analysis",
                        "name": "重复节点",
                        "position_x": 100,
                        "position_y": 0,
                    },
                ],
                "edges": [],
            },
        )
        self.assertEqual(response.status_code, 422)
        self.service.replace_graph.assert_not_called()
