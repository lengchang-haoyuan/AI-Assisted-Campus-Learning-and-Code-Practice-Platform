from datetime import UTC, datetime
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_current_user, get_project_service
from app.core.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.main import create_app
from app.models.enums import ProjectDifficulty, ProjectStatus
from app.models.project import Project
from app.models.user import User
from app.repositories.project import (
    ProjectPersistenceConflictError,
    ProjectRepository,
)
from app.services.auth import UserIdentity
from app.services.project import (
    ProjectCreateData,
    ProjectData,
    ProjectOwner,
    ProjectPage,
    ProjectService,
    ProjectUpdateData,
)
from tests.test_api_foundation import request

NOW = datetime(2026, 8, 30, 2, 0, tzinfo=UTC)


def create_project_model(
    *, project_id: int = 10, owner_id: int = 1, name: str = "ScholarHub"
) -> Project:
    owner = User(
        id=owner_id,
        username=f"student_{owner_id}",
        email=f"student_{owner_id}@example.com",
        password_hash="not-used",
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )
    project = Project(
        id=project_id,
        owner_id=owner_id,
        name=name,
        description="校园学习项目",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        language="Python",
        framework="FastAPI",
        frontend="Vue 3",
        backend="FastAPI",
        database="MySQL",
        requirements=[{"name": "认证", "required": True}],
        output_requirement="可运行系统",
        status=ProjectStatus.IN_PROGRESS,
        created_at=NOW,
        updated_at=NOW,
    )
    project.owner = owner
    return project


def create_project_data(*, project_id: int = 10, owner_id: int = 1) -> ProjectData:
    return ProjectData(
        id=project_id,
        name="ScholarHub",
        description="校园学习项目",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        language="Python",
        framework="FastAPI",
        frontend="Vue 3",
        backend="FastAPI",
        database="MySQL",
        requirements=[{"name": "认证", "required": True}],
        output_requirement="可运行系统",
        owner=ProjectOwner(id=owner_id, username=f"student_{owner_id}"),
        status=ProjectStatus.IN_PROGRESS,
        created_at=NOW,
        updated_at=NOW,
    )


def create_input() -> ProjectCreateData:
    return ProjectCreateData(
        name="ScholarHub",
        description=None,
        difficulty=ProjectDifficulty.BEGINNER,
        language="Python",
        framework="FastAPI",
        frontend="Vue 3",
        backend="FastAPI",
        database="MySQL",
        requirements=None,
        output_requirement=None,
        status=ProjectStatus.NOT_STARTED,
    )


class ProjectServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=ProjectRepository)
        self.service = ProjectService(self.repository)

    def test_create_uses_authenticated_owner(self) -> None:
        self.repository.create.side_effect = lambda project: create_project_model(
            project_id=20, owner_id=project.owner_id, name=project.name
        )

        result = self.service.create_project(7, create_input())

        submitted = self.repository.create.call_args.args[0]
        self.assertEqual(submitted.owner_id, 7)
        self.assertEqual(result.owner.id, 7)

    def test_list_is_owner_scoped_and_paginated(self) -> None:
        self.repository.count_by_owner.return_value = 21
        self.repository.list_by_owner.return_value = [create_project_model()]

        result = self.service.list_projects(1, page=3, page_size=10)

        self.repository.count_by_owner.assert_called_once_with(1)
        self.repository.list_by_owner.assert_called_once_with(
            1, offset=20, limit=10
        )
        self.assertEqual(result.total_pages, 3)
        self.assertEqual(len(result.items), 1)

    def test_empty_list_has_explicit_zero_semantics(self) -> None:
        self.repository.count_by_owner.return_value = 0
        self.repository.list_by_owner.return_value = []

        result = self.service.list_projects(1, page=1, page_size=20)

        self.assertEqual(result.items, [])
        self.assertEqual(result.total, 0)
        self.assertEqual(result.total_pages, 0)

    def test_get_rejects_other_owner_and_missing_project(self) -> None:
        self.repository.get_by_id.return_value = create_project_model(owner_id=2)
        with self.assertRaises(PermissionDeniedError):
            self.service.get_project(10, owner_id=1)

        self.repository.get_by_id.return_value = None
        with self.assertRaises(ResourceNotFoundError):
            self.service.get_project(999, owner_id=1)

    def test_update_checks_owner_and_changes_only_submitted_fields(self) -> None:
        project = create_project_model()
        self.repository.get_by_id.return_value = project
        self.repository.update.side_effect = lambda value: value

        result = self.service.update_project(
            10,
            1,
            ProjectUpdateData(
                {"description": None, "status": ProjectStatus.COMPLETED}
            ),
        )

        self.assertIsNone(result.description)
        self.assertEqual(result.status, ProjectStatus.COMPLETED)
        self.assertEqual(result.name, "ScholarHub")
        self.repository.update.assert_called_once_with(project)

    def test_delete_checks_owner(self) -> None:
        project = create_project_model()
        self.repository.get_by_id.return_value = project

        self.service.delete_project(10, owner_id=1)

        self.repository.delete.assert_called_once_with(project)

    def test_update_and_delete_reject_other_owner(self) -> None:
        self.repository.get_by_id.return_value = create_project_model(owner_id=2)

        with self.assertRaises(PermissionDeniedError):
            self.service.update_project(
                10, 1, ProjectUpdateData({"name": "越权修改"})
            )
        with self.assertRaises(PermissionDeniedError):
            self.service.delete_project(10, owner_id=1)

        self.repository.update.assert_not_called()
        self.repository.delete.assert_not_called()

    def test_persistence_conflict_becomes_api_conflict(self) -> None:
        project = create_project_model()
        self.repository.get_by_id.return_value = project
        self.repository.update.side_effect = ProjectPersistenceConflictError

        with self.assertRaises(ConflictError):
            self.service.update_project(
                10, 1, ProjectUpdateData({"name": "新的项目名称"})
            )


class ProjectAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=ProjectService)
        self.current_user = UserIdentity(
            id=1,
            username="student_1",
            email="student_1@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.app.dependency_overrides[get_project_service] = lambda: self.service

    def test_all_routes_require_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_project_service] = lambda: self.service

        for method, path, body in (
            ("GET", "/api/v1/projects", None),
            ("POST", "/api/v1/projects", {"name": "项目"}),
            ("GET", "/api/v1/projects/1", None),
            ("PUT", "/api/v1/projects/1", {"name": "新名称"}),
            ("DELETE", "/api/v1/projects/1", None),
        ):
            with self.subTest(method=method, path=path):
                response = request(app, method, path, body=body)
                self.assertEqual(response.status_code, 401)

    def test_create_ignores_no_client_owner_and_returns_201(self) -> None:
        self.service.create_project.return_value = create_project_data()

        response = request(
            self.app,
            "POST",
            "/api/v1/projects",
            body={"name": " ScholarHub ", "language": " Python "},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["owner"]["id"], 1)
        create_data = self.service.create_project.call_args.args[1]
        self.assertEqual(create_data.name, "ScholarHub")
        self.assertEqual(create_data.language, "Python")

        forged = request(
            self.app,
            "POST",
            "/api/v1/projects",
            body={"name": "伪造 owner", "owner_id": 2},
        )
        self.assertEqual(forged.status_code, 422)

    def test_list_supports_bounded_pagination(self) -> None:
        self.service.list_projects.return_value = ProjectPage(
            items=[create_project_data()],
            total=6,
            page=2,
            page_size=5,
            total_pages=2,
        )

        response = request(
            self.app, "GET", "/api/v1/projects?page=2&page_size=5"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 6)
        self.assertEqual(response.json()["page"], 2)
        self.service.list_projects.assert_called_once_with(1, page=2, page_size=5)

        invalid = request(self.app, "GET", "/api/v1/projects?page_size=101")
        self.assertEqual(invalid.status_code, 422)

    def test_detail_update_and_delete(self) -> None:
        self.service.get_project.return_value = create_project_data()
        self.service.update_project.return_value = create_project_data()

        detail = request(self.app, "GET", "/api/v1/projects/10")
        updated = request(
            self.app,
            "PUT",
            "/api/v1/projects/10",
            body={"status": "completed", "description": None},
        )
        deleted = request(self.app, "DELETE", "/api/v1/projects/10")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.body, b"")
        update_data = self.service.update_project.call_args.args[2]
        self.assertEqual(
            update_data.values,
            {"description": None, "status": ProjectStatus.COMPLETED},
        )
        self.service.delete_project.assert_called_once_with(10, 1)

    def test_validation_rejects_invalid_fields_and_empty_update(self) -> None:
        invalid_name = request(
            self.app,
            "POST",
            "/api/v1/projects",
            body={"name": "   "},
        )
        invalid_difficulty = request(
            self.app,
            "POST",
            "/api/v1/projects",
            body={"name": "项目", "difficulty": "expert"},
        )
        invalid_status = request(
            self.app,
            "POST",
            "/api/v1/projects",
            body={"name": "项目", "status": "unknown"},
        )
        optional_field_too_long = request(
            self.app,
            "POST",
            "/api/v1/projects",
            body={"name": "项目", "language": "x" * 101},
        )
        empty_update = request(
            self.app, "PUT", "/api/v1/projects/10", body={}
        )
        null_name = request(
            self.app, "PUT", "/api/v1/projects/10", body={"name": None}
        )

        for response in (
            invalid_name,
            invalid_difficulty,
            invalid_status,
            optional_field_too_long,
            empty_update,
            null_name,
        ):
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_permission_not_found_and_conflict_errors(self) -> None:
        for error, status_code, code in (
            (PermissionDeniedError("无权操作该项目"), 403, "permission_denied"),
            (ResourceNotFoundError("项目不存在"), 404, "resource_not_found"),
            (ConflictError("项目数据冲突"), 409, "conflict"),
        ):
            self.service.get_project.side_effect = error
            response = request(self.app, "GET", "/api/v1/projects/10")
            with self.subTest(status_code=status_code):
                self.assertEqual(response.status_code, status_code)
                self.assertEqual(response.json()["error"]["code"], code)


if __name__ == "__main__":
    unittest.main()
