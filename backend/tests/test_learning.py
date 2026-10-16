from datetime import UTC, date, datetime
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from sqlalchemy import Column, Date, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session
from pydantic import ValidationError

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
from app.models.submission import Feedback, FeedbackDecision
from app.schemas.learning import LearningRecordCreate, LearningRecordUpdate
from app.repositories.learning import LearningRepository
from app.services.auth import UserIdentity
from app.services.course import CourseData, CoursePage, CourseService
from app.services.learning import (
    LearningService,
    PlanCreateData,
    PlanData,
    PlanPage,
    PlanUpdateData,
    RecordCreateData,
    RecordData,
    RecordPage,
    RecordUpdateData,
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


def task_create_data(plan_id: int | None) -> TaskCreateData:
    return TaskCreateData(
        title="终态约束回归任务",
        description=None,
        priority=TaskPriority.MEDIUM,
        scheduled_date=TODAY,
        start_time=None,
        end_time=None,
        estimated_minutes=30,
        plan_id=plan_id,
        project_id=None,
    )


def task_snapshot(task: DailyTask) -> tuple[object, ...]:
    return (task.title, task.plan_id, task.project_id, task.status, task.completed_at)


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

    def test_terminal_transition_rejects_new_task_without_saving(self) -> None:
        for status in (LearningPlanStatus.COMPLETED, LearningPlanStatus.CANCELLED):
            with self.subTest(status=status):
                plan = make_plan(progress=100 if status == LearningPlanStatus.COMPLETED else 0)
                existing = make_task(completed=status == LearningPlanStatus.COMPLETED)
                existing.plan = plan
                self.repository.get_plan.return_value = plan
                self.repository.get_project.return_value = plan.project
                self.repository.get_course.return_value = plan.course
                self.repository.save_plan.side_effect = lambda item: item
                self.repository.save_task.side_effect = lambda item, **_: item
                self.repository.get_plan_task_counts.return_value = (1, 1)
                self.service.update_plan(11, 1, PlanUpdateData({"status": status}))
                before = task_snapshot(existing)

                with self.assertRaises(ConflictError):
                    self.service.create_task(1, task_create_data(11))

                self.repository.save_task.assert_not_called()
                self.assertEqual(task_snapshot(existing), before)
                self.assertEqual(plan.status, status)
                self.assertEqual(plan.progress, 100 if status == LearningPlanStatus.COMPLETED else 0)

    def test_cannot_move_tasks_into_or_out_of_terminal_plans(self) -> None:
        for status in (LearningPlanStatus.COMPLETED, LearningPlanStatus.CANCELLED):
            for source_id, target_id in ((None, 11), (12, 11), (11, None), (11, 12)):
                with self.subTest(status=status, source=source_id, target=target_id):
                    terminal = make_plan(progress=50)
                    terminal.status = status
                    active = make_plan()
                    active.id = 12
                    plans = {11: terminal, 12: active}
                    task = make_task()
                    task.plan_id = source_id
                    task.plan = plans.get(source_id)
                    self.repository.get_task.return_value = task
                    self.repository.get_plan.side_effect = lambda plan_id, **_: plans.get(plan_id)
                    self.repository.get_project.return_value = make_project()
                    self.repository.save_task.side_effect = lambda item, **_: item
                    self.repository.save_task.reset_mock()
                    before = task_snapshot(task)

                    with self.assertRaises(ConflictError):
                        self.service.update_task(13, 1, TaskUpdateData({
                            "plan_id": target_id, "title": "非法移动不应修改标题",
                        }))

                    self.repository.save_task.assert_not_called()
                    self.assertEqual(task_snapshot(task), before)
                    self.assertEqual((terminal.status, terminal.progress), (status, 50))

    def test_terminal_plans_reject_delete_and_first_completion(self) -> None:
        for status in (LearningPlanStatus.COMPLETED, LearningPlanStatus.CANCELLED):
            for operation in ("delete", "complete", "update_complete"):
                with self.subTest(status=status, operation=operation):
                    task = make_task()
                    task.plan.status = status
                    self.repository.get_task.return_value = task
                    self.repository.get_plan.return_value = task.plan
                    self.repository.get_project.return_value = task.project
                    self.repository.save_task.side_effect = lambda item, **_: item
                    self.repository.save_task.reset_mock()
                    self.repository.delete_task.reset_mock()
                    before = task_snapshot(task)

                    with self.assertRaises(ConflictError):
                        if operation == "delete":
                            self.service.delete_task(13, 1)
                        elif operation == "complete":
                            self.service.complete_task(13, 1)
                        else:
                            self.service.update_task(13, 1, TaskUpdateData({
                                "status": TaskStatus.COMPLETED, "title": "非法完成",
                            }))

                    self.repository.save_task.assert_not_called()
                    self.repository.delete_task.assert_not_called()
                    self.assertEqual(task_snapshot(task), before)
                    self.assertEqual(task.plan.progress, 0)

    def test_terminal_history_edits_preserve_membership_and_progress(self) -> None:
        for status in (LearningPlanStatus.COMPLETED, LearningPlanStatus.CANCELLED):
            for completed in (False, True):
                with self.subTest(status=status, completed=completed):
                    task = make_task(completed=completed)
                    task.plan.status = status
                    task.plan.progress = 37  # 存量快照不应因改标题被隐式重算。
                    self.repository.get_task.return_value = task
                    self.repository.get_plan.return_value = task.plan
                    self.repository.get_project.return_value = task.project
                    self.repository.save_task.side_effect = lambda item, **_: item
                    changes = {"title": "历史任务的新标题", "plan_id": 11, "status": task.status}
                    result = self.service.update_task(13, 1, TaskUpdateData(changes))

                    self.assertEqual(result.title, changes["title"])
                    self.assertEqual(result.plan.id, 11)
                    self.assertEqual(task.plan.progress, 37)
                    self.assertEqual(self.repository.save_task.call_args.kwargs["recalculate_plan_ids"], set())
                    if completed:
                        self.repository.save_task.reset_mock()
                        result = self.service.complete_task(13, 1)
                        self.assertEqual(result.completed_at, NOW)
                        self.repository.save_task.assert_not_called()

    def test_terminal_plan_allows_status_edits_that_do_not_change_completed_count(self) -> None:
        task = make_task()
        task.plan.status = LearningPlanStatus.CANCELLED
        self.repository.get_task.return_value = task
        self.repository.get_plan.return_value = task.plan
        self.repository.get_project.return_value = task.project
        self.repository.save_task.side_effect = lambda item, **_: item

        for status in (TaskStatus.IN_PROGRESS, TaskStatus.PENDING, TaskStatus.CANCELLED):
            result = self.service.update_task(13, 1, TaskUpdateData({"status": status}))
            self.assertEqual(result.status, status)
            self.assertEqual(self.repository.save_task.call_args.kwargs["recalculate_plan_ids"], set())

    def test_open_plans_still_allow_task_create_move_complete_and_delete(self) -> None:
        for status in (LearningPlanStatus.DRAFT, LearningPlanStatus.ACTIVE):
            with self.subTest(status=status):
                source = make_plan()
                target = make_plan()
                target.id = 12
                source.status = target.status = status
                self.repository.get_plan.side_effect = lambda plan_id, **_: {11: source, 12: target}.get(plan_id)
                self.repository.get_project.return_value = source.project
                self.repository.save_task.side_effect = lambda item, **_: item
                self.service.create_task(1, task_create_data(11))
                self.assertEqual(self.repository.save_task.call_args.kwargs["recalculate_plan_ids"], {11})

                task = make_task()
                task.plan = source
                self.repository.get_task.return_value = task
                self.service.update_task(13, 1, TaskUpdateData({"plan_id": 12}))
                self.assertEqual(self.repository.save_task.call_args.kwargs["recalculate_plan_ids"], {11, 12})
                self.service.complete_task(13, 1)
                self.assertEqual(task.status, TaskStatus.COMPLETED)
                self.assertEqual(self.repository.save_task.call_args.kwargs["recalculate_plan_ids"], {12})
                self.service.delete_task(13, 1)
                self.repository.delete_task.assert_called_with(task)

    def test_terminal_plan_ownership_is_checked_before_association(self) -> None:
        foreign_plan = make_plan(user_id=2)
        foreign_plan.status = LearningPlanStatus.COMPLETED
        self.repository.get_plan.return_value = foreign_plan
        task = make_task()
        task.plan_id = None
        task.plan = None
        self.repository.get_task.return_value = task

        with self.assertRaises(PermissionDeniedError):
            self.service.create_task(1, task_create_data(11))
        with self.assertRaises(PermissionDeniedError):
            self.service.update_task(13, 1, TaskUpdateData({"plan_id": 11}))

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

    def test_teaching_pass_record_cannot_be_edited_manually(self) -> None:
        record = make_record()
        record.record_metadata = {
            "source": "teaching_submission",
            "submission_id": 23,
        }
        self.repository.get_record.return_value = record
        record.teaching_feedback = Feedback(id=30, learning_record_id=record.id,
            submission_id=23, version_number=1, decision=FeedbackDecision.ACCEPT)

        with self.assertRaises(ConflictError):
            self.service.update_record(
                17,
                1,
                RecordUpdateData({"title": "手工伪造通过记录"}),
            )

        self.repository.save_record.assert_not_called()

        record.duration_minutes = None
        result = self.service.get_record(17, 1)
        self.assertIsNone(result.duration_minutes)

    def test_client_cannot_inject_reserved_record_metadata(self):
        for key, value in [('source', 'teaching_submission'), ('submission_id', 999),
                           ('version_number', 1)]:
            for schema, data in [
                (LearningRecordCreate, {'title': '普通记录', 'record_type': 'study', 'duration_minutes': 1}),
                (LearningRecordUpdate, {'title': '普通更新'}),
            ]:
                with self.subTest(key=key, schema=schema):
                    with self.assertRaises(ValidationError):
                        schema.model_validate({**data, 'record_metadata': {key: value}})

    def test_untrusted_historical_tag_is_not_presented_as_teaching_feedback(self):
        record = make_record()
        record.record_metadata = {'source': 'teaching_submission', 'submission_id': 999,
                                  'version_number': 1, 'notes': '保留普通元数据'}
        self.repository.get_record.return_value = record
        result = self.service.get_record(record.id, 1)
        self.assertEqual(result.record_metadata, {'notes': '保留普通元数据'})


class PlanTaskConstraintServiceTests(unittest.TestCase):
    def test_display_rounding_does_not_grant_completion(self):
        self.plan.progress = 100
        self.repository.get_plan_task_counts = Mock(return_value=(200, 199))
        with self.assertRaises(ConflictError):
            self.service.update_plan(11, 1, PlanUpdateData({'status': LearningPlanStatus.COMPLETED}))
        self.assertEqual(self.plan.status, LearningPlanStatus.ACTIVE)
        self.repository.save_plan.assert_not_called()

    def test_completion_requires_nonempty_all_completed_tasks(self):
        for total, completed in [(0, 0), (1, 0), (200, 199), (200, 200)]:
            with self.subTest(total=total, completed=completed):
                self.setUp()
                self.repository.get_plan_task_counts = Mock(return_value=(total, completed))
                if total and total == completed:
                    result = self.service.update_plan(11, 1, PlanUpdateData({'status': LearningPlanStatus.COMPLETED}))
                    self.assertEqual(result.status, LearningPlanStatus.COMPLETED)
                else:
                    with self.assertRaises(ConflictError):
                        self.service.update_plan(11, 1, PlanUpdateData({'status': LearningPlanStatus.COMPLETED}))

    def setUp(self) -> None:
        self.plan = make_plan()
        task = make_task()
        task.plan = self.plan
        task.scheduled_date = date(2026, 9, 15)
        self.tasks = [task]
        project_b = make_project()
        project_b.id = 8
        self.projects = {7: self.plan.project, 8: project_b}
        self.repository = Mock(spec=LearningRepository)
        self.repository.get_plan.return_value = self.plan
        self.repository.get_task.side_effect = lambda task_id: next(
            (item for item in self.tasks if item.id == task_id), None
        )
        self.repository.get_project.side_effect = self.projects.get
        self.repository.get_course.return_value = self.plan.course
        self.repository.list_plan_task_project_ids.side_effect = (
            lambda *_: {item.project_id for item in self.tasks}
        )
        self.repository.get_plan_task_date_bounds.side_effect = lambda *_: (
            min((item.scheduled_date for item in self.tasks), default=None),
            max((item.scheduled_date for item in self.tasks), default=None),
        )
        self.repository.save_plan.side_effect = self.save_plan
        self.repository.save_task.side_effect = self.save_task
        self.service = LearningService(self.repository)

    def save_plan(self, plan: LearningPlan) -> LearningPlan:
        plan.project = self.projects.get(plan.project_id)
        if plan.course_id is None:
            plan.course = None
        return plan

    def save_task(self, task: DailyTask, **_: object) -> DailyTask:
        task.plan = self.plan if task.plan_id == self.plan.id else None
        task.project = self.projects.get(task.project_id)
        return task

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.plan.title, self.plan.project_id, self.plan.course_id,
            self.plan.start_date, self.plan.end_date, self.plan.status, self.plan.progress,
            tuple((task_snapshot(item), item.scheduled_date) for item in self.tasks),
        )

    def assert_plan_conflict(self, changes: dict[str, object]) -> None:
        before = self.snapshot()
        with self.assertRaises(ConflictError):
            self.service.update_plan(11, 1, PlanUpdateData({"title": "不应部分保存", **changes}))
        self.assertEqual(self.snapshot(), before)
        self.repository.save_plan.assert_not_called()
        self.repository.save_task.assert_not_called()

    def test_incompatible_project_change_rejects_tasks_in_every_status(self) -> None:
        for status in TaskStatus:
            with self.subTest(status=status):
                self.setUp()
                self.tasks[0].status = status
                self.assert_plan_conflict({"project_id": 8})
                self.repository.list_plan_task_project_ids.assert_called_once_with(11, 1)

    def test_nonempty_project_cannot_leave_tasks_with_null_project(self) -> None:
        self.plan.project_id = None
        self.plan.project = None
        self.tasks[0].project_id = None
        self.tasks[0].project = None
        self.assert_plan_conflict({"project_id": 8})

    def test_date_changes_cannot_exclude_existing_tasks(self) -> None:
        for changes in (
            {"start_date": date(2026, 9, 16)},
            {"end_date": date(2026, 9, 14)},
            {"start_date": date(2026, 9, 16), "end_date": date(2026, 9, 20)},
        ):
            with self.subTest(changes=changes):
                self.setUp()
                self.assert_plan_conflict(changes)
                self.repository.get_plan_task_date_bounds.assert_called_once_with(11, 1)

    def test_compatible_narrowing_expansion_and_null_boundaries_are_allowed(self) -> None:
        for changes in (
            {"start_date": date(2026, 9, 15), "end_date": date(2026, 9, 15)},
            {"start_date": date(2026, 8, 1), "end_date": date(2026, 10, 1)},
            {"start_date": None},
            {"end_date": None},
            {"start_date": None, "end_date": None},
        ):
            with self.subTest(changes=changes):
                self.setUp()
                before = task_snapshot(self.tasks[0])
                self.service.update_plan(11, 1, PlanUpdateData(changes))
                self.repository.save_plan.assert_called_once()
                self.assertEqual(task_snapshot(self.tasks[0]), before)
                self.assertEqual(self.tasks[0].scheduled_date, date(2026, 9, 15))

    def test_empty_plan_allows_project_and_date_changes(self) -> None:
        self.tasks = []
        result = self.service.update_plan(11, 1, PlanUpdateData({
            "project_id": 8, "start_date": date(2026, 10, 1), "end_date": date(2026, 10, 2),
        }))
        self.assertEqual(result.project.id, 8)
        self.assertEqual(result.start_date, date(2026, 10, 1))
        self.assertEqual(result.end_date, date(2026, 10, 2))

    def test_same_values_and_metadata_do_not_revalidate_legacy_tasks(self) -> None:
        self.tasks[0].project_id = 8
        self.tasks[0].scheduled_date = date(2026, 10, 1)
        result = self.service.update_plan(11, 1, PlanUpdateData({
            "title": "只改标题", "project_id": 7,
            "start_date": TODAY, "end_date": date(2026, 9, 30),
        }))
        self.assertEqual(result.title, "只改标题")
        self.repository.list_plan_task_project_ids.assert_not_called()
        self.repository.get_plan_task_date_bounds.assert_not_called()
        self.assertEqual(self.tasks[0].project_id, 8)
        self.assertEqual(self.tasks[0].scheduled_date, date(2026, 10, 1))

    def test_optional_fields_can_be_cleared_without_rewriting_tasks(self) -> None:
        before = task_snapshot(self.tasks[0])
        result = self.service.update_plan(11, 1, PlanUpdateData({
            "project_id": None, "course_id": None, "start_date": None, "end_date": None,
            "description": None, "goal_data": None,
        }))
        self.assertIsNone(result.project)
        self.assertIsNone(result.course)
        self.assertIsNone(result.start_date)
        self.assertIsNone(result.end_date)
        self.assertEqual(task_snapshot(self.tasks[0]), before)
        self.repository.save_task.assert_not_called()
        self.repository.list_plan_task_project_ids.assert_not_called()
        self.repository.get_plan_task_date_bounds.assert_not_called()

    def test_terminal_plans_apply_compatibility_without_blanket_freezing(self) -> None:
        for status in (LearningPlanStatus.COMPLETED, LearningPlanStatus.CANCELLED):
            with self.subTest(status=status):
                self.setUp()
                self.plan.status = status
                self.plan.progress = 100 if status == LearningPlanStatus.COMPLETED else 0
                self.assert_plan_conflict({"project_id": 8})
                self.assert_plan_conflict({"end_date": date(2026, 9, 14)})
                self.plan.project_id = None
                self.plan.project = None
                self.tasks[0].project_id = 8
                before = task_snapshot(self.tasks[0])
                self.service.update_plan(11, 1, PlanUpdateData({
                    "project_id": 8, "start_date": date(2026, 9, 15),
                    "end_date": date(2026, 9, 15), "title": "相容历史编辑",
                }))
                self.assertEqual(self.plan.status, status)
                self.assertEqual(self.plan.progress, 100 if status == LearningPlanStatus.COMPLETED else 0)
                self.assertEqual(task_snapshot(self.tasks[0]), before)

    def test_tasks_can_be_explicitly_reassociated_before_setting_new_plan_project(self) -> None:
        self.service.update_plan(11, 1, PlanUpdateData({"project_id": None}))
        self.assertEqual(self.tasks[0].project_id, 7)
        self.service.update_task(13, 1, TaskUpdateData({"project_id": 8}))
        result = self.service.update_plan(11, 1, PlanUpdateData({"project_id": 8}))
        self.assertEqual(result.project.id, 8)
        self.assertEqual(self.tasks[0].plan_id, 11)
        self.assertEqual(self.tasks[0].project_id, 8)
        self.repository.save_task.assert_called_once()
        self.repository.save_record.assert_not_called()

    def test_update_preserves_plan_project_and_task_ownership_checks(self) -> None:
        self.projects[8].owner_id = 2
        before = self.snapshot()
        with self.assertRaises(PermissionDeniedError):
            self.service.update_plan(11, 1, PlanUpdateData({"project_id": 8}))
        self.plan.user_id = 2
        with self.assertRaises(PermissionDeniedError):
            self.service.update_plan(11, 1, PlanUpdateData({"start_date": None}))
        self.plan.user_id = 1
        self.tasks[0].user_id = 2
        with self.assertRaises(PermissionDeniedError):
            self.service.update_task(13, 1, TaskUpdateData({"project_id": 8}))
        self.assertEqual(self.snapshot(), before)
        self.repository.save_plan.assert_not_called()
        self.repository.save_task.assert_not_called()
        self.repository.list_plan_task_project_ids.assert_not_called()
        self.repository.get_plan_task_date_bounds.assert_not_called()


class PlanTaskConstraintQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        metadata = MetaData()
        # 沿用已有隔离查询测试方式；仅建立查询所需列，不修改生产模型或 MySQL。
        self.table = Table(
            "daily_tasks", metadata,
            Column("id", Integer, primary_key=True),
            Column("user_id", Integer), Column("plan_id", Integer),
            Column("project_id", Integer), Column("scheduled_date", Date),
            Column("status", String),
        )
        metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.repository = LearningRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_empty_plan_has_no_projects_or_date_bounds(self) -> None:
        self.assertEqual(self.repository.list_plan_task_project_ids(11, 1), set())
        self.assertEqual(self.repository.get_plan_task_date_bounds(11, 1), (None, None))

    def test_queries_include_all_statuses_and_scope_owner_and_plan(self) -> None:
        rows = [
            {"id": index, "user_id": 1, "plan_id": 11, "project_id": project_id,
             "scheduled_date": date(2026, 9, day), "status": status.value}
            for index, (project_id, day, status) in enumerate((
                (7, 5, TaskStatus.PENDING), (7, 10, TaskStatus.IN_PROGRESS),
                (8, 20, TaskStatus.COMPLETED), (None, 25, TaskStatus.CANCELLED),
            ), start=1)
        ]
        rows.extend([
            {"id": 5, "user_id": 2, "plan_id": 11, "project_id": 90,
             "scheduled_date": date(2026, 10, 1), "status": "pending"},
            {"id": 6, "user_id": 1, "plan_id": 12, "project_id": 91,
             "scheduled_date": date(2026, 8, 1), "status": "pending"},
            {"id": 1000, "user_id": 1, "plan_id": 11, "project_id": 9,
             "scheduled_date": date(2026, 9, 28), "status": "pending"},
        ])
        self.session.execute(self.table.insert(), rows)
        self.assertEqual(self.repository.list_plan_task_project_ids(11, 1), {7, 8, 9, None})
        self.assertEqual(self.repository.get_plan_task_date_bounds(11, 1),
                         (date(2026, 9, 5), date(2026, 9, 28)))


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

    def test_terminal_task_conflicts_use_existing_api_error_contract(self) -> None:
        repository = Mock(spec=LearningRepository)
        service = LearningService(repository)
        self.app.dependency_overrides[get_learning_service] = lambda: service
        for status in (LearningPlanStatus.COMPLETED, LearningPlanStatus.CANCELLED):
            for method, path, body in (
                ("POST", "/api/v1/learning/tasks", {"title": "新任务", "scheduled_date": "2026-09-01", "plan_id": 11}),
                ("PUT", "/api/v1/learning/tasks/13", {"plan_id": 11}),
                ("PUT", "/api/v1/learning/tasks/13", {"status": "completed"}),
                ("POST", "/api/v1/learning/tasks/13/complete", None),
                ("DELETE", "/api/v1/learning/tasks/13", None),
            ):
                with self.subTest(status=status, method=method, path=path):
                    plan = make_plan(progress=50)
                    plan.status = status
                    task = make_task()
                    task.plan = plan
                    if method == "PUT" and body == {"plan_id": 11}:
                        task.plan_id = None
                        task.plan = None
                    repository.get_task.return_value = task
                    repository.get_plan.return_value = plan
                    repository.get_project.return_value = task.project
                    before = task_snapshot(task)

                    response = request(self.app, method, path, body=body)

                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.json()["error"]["code"], "conflict")
                    self.assertEqual(task_snapshot(task), before)
                    self.assertEqual((plan.status, plan.progress), (status, 50))
        repository.save_task.assert_not_called()
        repository.delete_task.assert_not_called()

    def test_plan_task_conflicts_return_409_without_partial_changes(self) -> None:
        repository = Mock(spec=LearningRepository)
        service = LearningService(repository)
        self.app.dependency_overrides[get_learning_service] = lambda: service
        for changes, expected_message in (
            ({"project_id": 8}, "项目"),
            ({"start_date": "2026-09-16"}, "开始日期"),
            ({"end_date": "2026-09-14"}, "结束日期"),
        ):
            with self.subTest(changes=changes):
                plan = make_plan()
                project_b = make_project()
                project_b.id = 8
                repository.get_plan.return_value = plan
                repository.get_project.side_effect = {7: plan.project, 8: project_b}.get
                repository.get_course.return_value = plan.course
                repository.list_plan_task_project_ids.return_value = {7}
                repository.get_plan_task_date_bounds.return_value = (date(2026, 9, 15), date(2026, 9, 15))
                repository.save_plan.side_effect = lambda item: item

                response = request(self.app, "PUT", "/api/v1/learning/plans/11", body={
                    "title": "失败不应改标题", **changes,
                })

                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["error"]["code"], "conflict")
                self.assertIn(expected_message, response.json()["error"]["message"])
                self.assertEqual(plan.title, "完成课程项目")
                self.assertEqual(plan.project_id, 7)
                self.assertEqual((plan.start_date, plan.end_date), (TODAY, date(2026, 9, 30)))
        repository.save_plan.assert_not_called()
        repository.save_task.assert_not_called()

    def test_plan_optional_fields_keep_existing_null_contract(self) -> None:
        repository = Mock(spec=LearningRepository)
        plan = make_plan()
        repository.get_plan.return_value = plan

        def save_plan(item: LearningPlan) -> LearningPlan:
            item.project = item.course = None
            return item

        repository.save_plan.side_effect = save_plan
        service = LearningService(repository)
        self.app.dependency_overrides[get_learning_service] = lambda: service
        response = request(self.app, "PUT", "/api/v1/learning/plans/11", body={
            "project_id": None, "course_id": None, "start_date": None, "end_date": None,
        })
        self.assertEqual(response.status_code, 200)
        for field in ("project", "course", "start_date", "end_date"):
            self.assertIsNone(response.json()[field])
        repository.save_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
