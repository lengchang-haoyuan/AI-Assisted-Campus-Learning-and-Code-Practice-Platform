from datetime import UTC, date, datetime
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_current_user, get_workspace_service
from app.core.exceptions import PermissionDeniedError
from app.main import create_app
from app.models.enums import (
    ProjectDifficulty,
    ProjectStatus,
    RecordType,
    TaskPriority,
    TaskStatus,
)
from app.models.learning import DailyTask, LearningRecord
from app.models.project import Project
from app.repositories.workspace import (
    TaskStatsRecord,
    WorkspaceProjectRecord,
    WorkspaceRepository,
)
from app.services.auth import UserIdentity
from app.services.workspace import (
    LearningRecordData,
    LearningRecordPage,
    TaskCreateData,
    TaskData,
    TaskPage,
    WorkspaceDashboardData,
    WorkspaceProjectData,
    WorkspaceProjectPage,
    WorkspaceProjectRefData,
    WorkspaceService,
    WorkspaceStatsData,
)
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
TODAY = date(2026, 9, 1)


def make_project_record(*, owner_id: int = 1) -> WorkspaceProjectRecord:
    project = Project(
        id=7,
        owner_id=owner_id,
        name="ScholarHub",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        status=ProjectStatus.IN_PROGRESS,
        progress=20,
        created_at=NOW,
        updated_at=NOW,
    )
    return WorkspaceProjectRecord(
        project=project,
        linked_task_count=2,
        completed_task_count=1,
        recorded_minutes=90,
    )


def make_task_model(*, owner_id: int = 1, completed: bool = False) -> DailyTask:
    task = DailyTask(
        id=3,
        user_id=owner_id,
        project_id=None,
        title="完成工作台接口",
        priority=TaskPriority.HIGH,
        status=TaskStatus.COMPLETED if completed else TaskStatus.PENDING,
        scheduled_date=TODAY,
        estimated_minutes=60,
        completed_at=NOW if completed else None,
        created_at=NOW,
        updated_at=NOW,
    )
    task.project = None
    return task


def make_task_data() -> TaskData:
    return TaskData(
        id=3,
        title="完成工作台接口",
        description=None,
        priority=TaskPriority.HIGH,
        status=TaskStatus.PENDING,
        scheduled_date=TODAY,
        start_time=None,
        end_time=None,
        estimated_minutes=60,
        completed_at=None,
        project=WorkspaceProjectRefData(id=7, name="ScholarHub"),
        created_at=NOW,
        updated_at=NOW,
    )


def make_record_data() -> LearningRecordData:
    return LearningRecordData(
        id=5,
        title="学习 SQLAlchemy 聚合查询",
        content="完成工作台统计查询",
        record_type=RecordType.STUDY,
        duration_minutes=45,
        occurred_at=NOW,
        project=WorkspaceProjectRefData(id=7, name="ScholarHub"),
        created_at=NOW,
    )


def make_project_data() -> WorkspaceProjectData:
    return WorkspaceProjectData(
        id=7,
        name="ScholarHub",
        description="校园学习与代码实践平台",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        status=ProjectStatus.IN_PROGRESS,
        language="Python",
        progress=50,
        linked_task_count=2,
        completed_task_count=1,
        recorded_minutes=90,
        updated_at=NOW,
    )


class WorkspaceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=WorkspaceRepository)
        self.service = WorkspaceService(self.repository)

    def test_create_task_rejects_project_owned_by_another_user(self) -> None:
        self.repository.get_project.return_value = make_project_record(owner_id=2)

        with self.assertRaises(PermissionDeniedError):
            self.service.create_task(
                1,
                TaskCreateData(
                    title="越权任务",
                    description=None,
                    priority=TaskPriority.MEDIUM,
                    scheduled_date=TODAY,
                    start_time=None,
                    end_time=None,
                    estimated_minutes=30,
                    project_id=7,
                ),
            )

        self.repository.create_task.assert_not_called()

    def test_complete_task_is_owner_scoped_and_idempotent(self) -> None:
        self.repository.get_task.return_value = make_task_model(owner_id=2)
        with self.assertRaises(PermissionDeniedError):
            self.service.complete_task(3, 1)

        self.repository.get_task.return_value = make_task_model(completed=True)
        result = self.service.complete_task(3, 1)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.repository.update_task.assert_not_called()

    def test_workspace_lists_system_record_without_fabricated_duration(self) -> None:
        record = LearningRecord(
            id=5,
            user_id=1,
            title="教学任务通过：字符串练习",
            content="教学提交已由教师确认通过。",
            record_type=RecordType.TASK,
            duration_minutes=None,
            occurred_at=NOW,
            created_at=NOW,
        )
        record.project = None
        self.repository.count_records.return_value = 1
        self.repository.list_records.return_value = [record]

        result = self.service.list_records(1, page=1, page_size=20)

        self.assertIsNone(result.items[0].duration_minutes)

    def test_dashboard_uses_user_date_and_utc_day_bounds(self) -> None:
        self.repository.get_task_stats.return_value = TaskStatsRecord(4, 3, 150)
        self.repository.sum_recorded_minutes.return_value = 45
        self.repository.list_projects.return_value = [make_project_record()]
        self.repository.list_tasks.return_value = [make_task_model()]
        self.repository.list_records.return_value = []
        self.repository.count_projects.return_value = 2
        self.repository.count_active_projects.return_value = 1

        result = self.service.get_dashboard(
            1, selected_date=TODAY, utc_offset_minutes=480
        )

        self.assertEqual(result.stats.learning_progress, 75)
        self.assertEqual(result.stats.today_recorded_minutes, 45)
        bounds = self.repository.sum_recorded_minutes.call_args.kwargs
        self.assertEqual(bounds["occurred_from"], datetime(2026, 8, 31, 16, tzinfo=UTC))
        self.assertEqual(bounds["occurred_to"], datetime(2026, 9, 1, 16, tzinfo=UTC))

    def test_list_tasks_has_explicit_empty_pagination(self) -> None:
        self.repository.count_tasks.return_value = 0
        self.repository.list_tasks.return_value = []

        result = self.service.list_tasks(
            1, page=1, page_size=20, scheduled_date=None
        )

        self.assertEqual(result.items, [])
        self.assertEqual(result.total_pages, 0)
        self.repository.list_tasks.assert_called_once_with(
            1, offset=0, limit=20, scheduled_date=None
        )


class WorkspaceAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=WorkspaceService)
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="student",
            email="student@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_workspace_service] = lambda: self.service

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_workspace_routes_require_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_workspace_service] = lambda: self.service

        for method, path, body in (
            ("GET", "/api/v1/workspace/tasks", None),
            ("POST", "/api/v1/workspace/tasks", {"title": "任务"}),
            ("GET", "/api/v1/workspace/records", None),
            ("GET", "/api/v1/workspace/projects", None),
        ):
            with self.subTest(method=method, path=path):
                response = request(app, method, path, body=body)
                self.assertEqual(response.status_code, 401)

    def test_dashboard_and_lists_map_service_results(self) -> None:
        task = make_task_data()
        record = make_record_data()
        project = make_project_data()
        self.service.get_dashboard.return_value = WorkspaceDashboardData(
            date=TODAY,
            stats=WorkspaceStatsData(1, 0, 60, 45, 0, 1, 1),
            today_tasks=[task],
            recent_projects=[project],
            recent_records=[record],
        )
        self.service.list_tasks.return_value = TaskPage([task], 1, 1, 20, 1)
        self.service.list_records.return_value = LearningRecordPage(
            [record], 1, 1, 20, 1
        )
        self.service.list_projects.return_value = WorkspaceProjectPage(
            [project], 1, 1, 20, 1
        )

        dashboard = request(
            self.app,
            "GET",
            "/api/v1/workspace/dashboard?date=2026-09-01&utc_offset_minutes=480",
        )
        tasks = request(self.app, "GET", "/api/v1/workspace/tasks")
        records = request(self.app, "GET", "/api/v1/workspace/records")
        projects = request(self.app, "GET", "/api/v1/workspace/projects")

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["stats"]["today_recorded_minutes"], 45)
        self.assertEqual(tasks.json()["items"][0]["project"]["id"], 7)
        self.assertEqual(records.json()["items"][0]["duration_minutes"], 45)
        self.assertEqual(projects.json()["items"][0]["progress"], 50)

    def test_create_validation_and_completion_mapping(self) -> None:
        task = make_task_data()
        self.service.create_task.return_value = task
        self.service.complete_task.return_value = task

        invalid = request(
            self.app,
            "POST",
            "/api/v1/workspace/tasks",
            body={
                "title": "任务",
                "scheduled_date": "2026-09-01",
                "start_time": "10:00:00",
                "end_time": "09:00:00",
            },
        )
        created = request(
            self.app,
            "POST",
            "/api/v1/workspace/tasks",
            body={
                "title": " 完成工作台接口 ",
                "priority": "high",
                "scheduled_date": "2026-09-01",
                "estimated_minutes": 60,
                "project_id": 7,
            },
        )
        completed = request(
            self.app, "POST", "/api/v1/workspace/tasks/3/complete"
        )

        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(completed.status_code, 200)
        create_data = self.service.create_task.call_args.args[1]
        self.assertEqual(create_data.title, "完成工作台接口")
        self.assertEqual(create_data.project_id, 7)


if __name__ == "__main__":
    unittest.main()
