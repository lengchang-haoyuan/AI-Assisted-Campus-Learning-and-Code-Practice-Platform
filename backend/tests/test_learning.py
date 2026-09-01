from datetime import UTC, date, datetime
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_course_service, get_current_user, get_learning_service
from app.core.exceptions import ConflictError, PermissionDeniedError
from app.main import create_app
from app.models.course import Course
from app.models.enums import (
    CourseStatus,
    LearningPlanStatus,
    ProjectDifficulty,
    ProjectStatus,
    RecordType,
    TaskPriority,
    TaskStatus,
)
from app.models.learning import DailyTask, LearningPlan, LearningRecord
from app.models.project import Project
from app.repositories.course import CourseRepository
from app.repositories.learning import LearningRepository
from app.services.auth import UserIdentity
from app.services.course import CourseData, CoursePage, CourseService
from app.services.learning import (
    LearningService,
    PlanCreateData,
    PlanData,
    PlanPage,
    RecordCreateData,
    RecordData,
    RecordPage,
    ResourceRefData,
    TaskCreateData,
    TaskData,
    TaskPage,
    TaskUpdateData,
)
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
TODAY = date(2026, 9, 1)


def make_project(*, owner_id: int = 1) -> Project:
    return Project(
        id=7,
        owner_id=owner_id,
        name="ScholarHub",
        difficulty=ProjectDifficulty.INTERMEDIATE,
        status=ProjectStatus.IN_PROGRESS,
        progress=20,
        created_at=NOW,
        updated_at=NOW,
    )


def make_course(*, owner_id: int = 1) -> Course:
    return Course(
        id=5,
        owner_id=owner_id,
        name="软件工程",
        code="SE101",
        description=None,
        instructor="张老师",
        schedule_data=None,
        status=CourseStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )


def make_plan(*, user_id: int = 1, progress: int = 0) -> LearningPlan:
    plan = LearningPlan(
        id=11,
        user_id=user_id,
        project_id=7,
        course_id=5,
        title="完成课程项目",
        status=LearningPlanStatus.ACTIVE,
        start_date=TODAY,
        end_date=date(2026, 9, 30),
        progress=progress,
        created_at=NOW,
        updated_at=NOW,
    )
    plan.project = make_project(owner_id=user_id)
    plan.course = make_course(owner_id=user_id)
    return plan


def make_task(*, user_id: int = 1, completed: bool = False) -> DailyTask:
    task = DailyTask(
        id=13,
        user_id=user_id,
        plan_id=11,
        project_id=7,
        title="实现学习接口",
        priority=TaskPriority.HIGH,
        status=TaskStatus.COMPLETED if completed else TaskStatus.PENDING,
        scheduled_date=TODAY,
        estimated_minutes=60,
        completed_at=NOW if completed else None,
        created_at=NOW,
        updated_at=NOW,
    )
    task.plan = make_plan(user_id=user_id)
    task.project = make_project(owner_id=user_id)
    return task


def make_record(*, user_id: int = 1) -> LearningRecord:
    record = LearningRecord(
        id=17,
        user_id=user_id,
        project_id=7,
        course_id=5,
        task_id=13,
        title="学习系统复盘",
        content="完成课程到记录闭环",
        record_type=RecordType.TASK,
        duration_minutes=45,
        occurred_at=NOW,
        created_at=NOW,
    )
    record.project = make_project(owner_id=user_id)
    record.course = make_course(owner_id=user_id)
    record.task = make_task(user_id=user_id)
    return record


class LearningServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=LearningRepository)
        self.service = LearningService(self.repository)

    def test_create_plan_checks_related_resource_ownership(self) -> None:
        self.repository.get_project.return_value = make_project(owner_id=2)

        with self.assertRaises(PermissionDeniedError):
            self.service.create_plan(
                1,
                PlanCreateData(
                    title="越权计划",
                    description=None,
                    status=LearningPlanStatus.DRAFT,
                    start_date=TODAY,
                    end_date=None,
                    goal_data=None,
                    project_id=7,
                    course_id=None,
                ),
            )

        self.repository.save_plan.assert_not_called()

    def test_task_inherits_plan_project_and_recalculates_progress(self) -> None:
        plan = make_plan()
        self.repository.get_plan.return_value = plan

        def save_task(task: DailyTask, **_: object) -> DailyTask:
            task.plan = plan
            task.project = plan.project
            return task

        self.repository.save_task.side_effect = save_task

        result = self.service.create_task(
            1,
            TaskCreateData(
                title="实现学习接口",
                description=None,
                priority=TaskPriority.HIGH,
                scheduled_date=TODAY,
                start_time=None,
                end_time=None,
                estimated_minutes=60,
                plan_id=11,
                project_id=None,
            ),
        )

        self.assertEqual(result.project.id, 7)
        saved_task = self.repository.save_task.call_args.args[0]
        self.assertEqual(saved_task.project_id, 7)
        self.assertEqual(
            self.repository.save_task.call_args.kwargs["recalculate_plan_ids"],
            {11},
        )

    def test_task_rejects_date_outside_plan_and_invalid_transition(self) -> None:
        self.repository.get_plan.return_value = make_plan()
        with self.assertRaises(ConflictError):
            self.service.create_task(
                1,
                TaskCreateData(
                    title="超期任务",
                    description=None,
                    priority=TaskPriority.MEDIUM,
                    scheduled_date=date(2026, 10, 1),
                    start_time=None,
                    end_time=None,
                    estimated_minutes=30,
                    plan_id=11,
                    project_id=None,
                ),
            )

        cancelled = make_task()
        cancelled.status = TaskStatus.CANCELLED
        cancelled.plan_id = None
        cancelled.project_id = None
        cancelled.plan = None
        cancelled.project = None
        self.repository.get_task.return_value = cancelled
        with self.assertRaises(ConflictError):
            self.service.update_task(
                13,
                1,
                TaskUpdateData({"status": TaskStatus.COMPLETED}),
            )

    def test_complete_task_is_idempotent(self) -> None:
        self.repository.get_task.return_value = make_task(completed=True)

        result = self.service.complete_task(13, 1)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.repository.save_task.assert_not_called()

    def test_record_inherits_task_sources_and_requires_declared_source(self) -> None:
        task = make_task()
        self.repository.get_task.return_value = task

        def save_record(record: LearningRecord) -> LearningRecord:
            record.project = task.project
            record.course = task.plan.course
            record.task = task
            return record

        self.repository.save_record.side_effect = save_record

        result = self.service.create_record(
            1,
            RecordCreateData(
                title="学习系统复盘",
                content="完成闭环",
                record_type=RecordType.TASK,
                duration_minutes=45,
                occurred_at=NOW,
                project_id=None,
                course_id=None,
                task_id=13,
                record_metadata=None,
            ),
        )

        self.assertEqual(result.project.id, 7)
        self.assertEqual(result.course.id, 5)

        with self.assertRaises(ConflictError):
            self.service.create_record(
                1,
                RecordCreateData(
                    title="缺少课程",
                    content=None,
                    record_type=RecordType.COURSE,
                    duration_minutes=20,
                    occurred_at=NOW,
                    project_id=None,
                    course_id=None,
                    task_id=None,
                    record_metadata=None,
                ),
            )


class LearningAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.learning_service = Mock(spec=LearningService)
        self.course_service = Mock(spec=CourseService)
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="student",
            email="student@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_learning_service] = (
            lambda: self.learning_service
        )
        self.app.dependency_overrides[get_course_service] = lambda: self.course_service

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_learning_routes_require_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_learning_service] = lambda: self.learning_service
        app.dependency_overrides[get_course_service] = lambda: self.course_service

        for method, path, body in (
            ("GET", "/api/v1/courses", None),
            ("GET", "/api/v1/learning/plans", None),
            ("POST", "/api/v1/learning/tasks", {"title": "任务"}),
            ("GET", "/api/v1/learning/records", None),
        ):
            with self.subTest(method=method, path=path):
                response = request(app, method, path, body=body)
                self.assertEqual(response.status_code, 401)

    def test_course_plan_task_record_chain_maps_service_results(self) -> None:
        course = CourseData(
            5,
            "软件工程",
            "SE101",
            None,
            "张老师",
            None,
            CourseStatus.ACTIVE,
            NOW,
            NOW,
        )
        plan = PlanData(
            11,
            "完成课程项目",
            None,
            LearningPlanStatus.ACTIVE,
            TODAY,
            date(2026, 9, 30),
            None,
            0,
            ResourceRefData(7, "ScholarHub"),
            ResourceRefData(5, "软件工程"),
            NOW,
            NOW,
        )
        task = TaskData(
            13,
            "实现学习接口",
            None,
            TaskPriority.HIGH,
            TaskStatus.PENDING,
            TODAY,
            None,
            None,
            60,
            None,
            ResourceRefData(11, "完成课程项目"),
            ResourceRefData(7, "ScholarHub"),
            NOW,
            NOW,
        )
        record = RecordData(
            17,
            "学习系统复盘",
            "完成闭环",
            RecordType.TASK,
            45,
            NOW,
            ResourceRefData(7, "ScholarHub"),
            ResourceRefData(5, "软件工程"),
            ResourceRefData(13, "实现学习接口"),
            None,
            NOW,
        )
        self.course_service.list_courses.return_value = CoursePage(
            [course], 1, 1, 20, 1
        )
        self.learning_service.list_plans.return_value = PlanPage(
            [plan], 1, 1, 20, 1
        )
        self.learning_service.list_tasks.return_value = TaskPage(
            [task], 1, 1, 20, 1
        )
        self.learning_service.list_records.return_value = RecordPage(
            [record], 1, 1, 20, 1
        )

        courses = request(self.app, "GET", "/api/v1/courses")
        plans = request(self.app, "GET", "/api/v1/learning/plans")
        tasks = request(self.app, "GET", "/api/v1/learning/tasks")
        records = request(self.app, "GET", "/api/v1/learning/records")

        self.assertEqual(courses.status_code, 200)
        self.assertEqual(plans.json()["items"][0]["course"]["id"], 5)
        self.assertEqual(tasks.json()["items"][0]["plan"]["id"], 11)
        self.assertEqual(records.json()["items"][0]["task"]["id"], 13)

    def test_input_boundaries_and_timezone_are_validated(self) -> None:
        invalid_plan = request(
            self.app,
            "POST",
            "/api/v1/learning/plans",
            body={
                "title": "计划",
                "start_date": "2026-09-02",
                "end_date": "2026-09-01",
            },
        )
        invalid_task = request(
            self.app,
            "POST",
            "/api/v1/learning/tasks",
            body={
                "title": "任务",
                "scheduled_date": "2026-09-01",
                "estimated_minutes": 1441,
            },
        )
        invalid_record = request(
            self.app,
            "POST",
            "/api/v1/learning/records",
            body={
                "title": "记录",
                "record_type": "study",
                "duration_minutes": 30,
                "occurred_at": "2026-09-01T08:00:00",
            },
        )

        self.assertEqual(invalid_plan.status_code, 422)
        self.assertEqual(invalid_task.status_code, 422)
        self.assertEqual(invalid_record.status_code, 422)


if __name__ == "__main__":
    unittest.main()
