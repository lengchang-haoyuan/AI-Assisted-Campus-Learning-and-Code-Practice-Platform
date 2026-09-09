from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from math import ceil
from typing import Any

from app.core.exceptions import ConflictError, PermissionDeniedError, ResourceNotFoundError
from app.models.course import Course
from app.models.enums import (
    LearningPlanStatus,
    RecordType,
    TaskPriority,
    TaskStatus,
)
from app.models.learning import DailyTask, LearningPlan, LearningRecord
from app.models.project import Project
from app.repositories.learning import LearningPersistenceConflictError, LearningRepository

PLAN_TRANSITIONS: dict[LearningPlanStatus, set[LearningPlanStatus]] = {
    LearningPlanStatus.DRAFT: {LearningPlanStatus.ACTIVE, LearningPlanStatus.CANCELLED},
    LearningPlanStatus.ACTIVE: {
        LearningPlanStatus.COMPLETED,
        LearningPlanStatus.CANCELLED,
    },
    LearningPlanStatus.COMPLETED: set(),
    LearningPlanStatus.CANCELLED: set(),
}
TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.IN_PROGRESS: {
        TaskStatus.PENDING,
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


@dataclass(frozen=True, slots=True)
class ResourceRefData:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class PlanCreateData:
    title: str
    description: str | None
    status: LearningPlanStatus
    start_date: date | None
    end_date: date | None
    goal_data: dict[str, Any] | None
    project_id: int | None
    course_id: int | None


@dataclass(frozen=True, slots=True)
class PlanUpdateData:
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PlanData:
    id: int
    title: str
    description: str | None
    status: LearningPlanStatus
    start_date: date | None
    end_date: date | None
    goal_data: dict[str, Any] | None
    progress: int
    project: ResourceRefData | None
    course: ResourceRefData | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlanPage:
    items: list[PlanData]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class TaskCreateData:
    title: str
    description: str | None
    priority: TaskPriority
    scheduled_date: date
    start_time: time | None
    end_time: time | None
    estimated_minutes: int | None
    plan_id: int | None
    project_id: int | None


@dataclass(frozen=True, slots=True)
class TaskUpdateData:
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TaskData:
    id: int
    title: str
    description: str | None
    priority: TaskPriority
    status: TaskStatus
    scheduled_date: date
    start_time: time | None
    end_time: time | None
    estimated_minutes: int | None
    completed_at: datetime | None
    plan: ResourceRefData | None
    project: ResourceRefData | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TaskPage:
    items: list[TaskData]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class RecordCreateData:
    title: str
    content: str | None
    record_type: RecordType
    duration_minutes: int
    occurred_at: datetime | None
    project_id: int | None
    course_id: int | None
    task_id: int | None
    record_metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class RecordUpdateData:
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RecordData:
    id: int
    title: str
    content: str | None
    record_type: RecordType
    duration_minutes: int | None
    occurred_at: datetime
    project: ResourceRefData | None
    course: ResourceRefData | None
    task: ResourceRefData | None
    record_metadata: dict[str, Any] | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RecordPage:
    items: list[RecordData]
    total: int
    page: int
    page_size: int
    total_pages: int


class LearningService:
    def __init__(self, repository: LearningRepository) -> None:
        self._repository = repository

    def list_plans(self, user_id: int, *, page: int, page_size: int) -> PlanPage:
        total = self._repository.count_plans(user_id)
        items = self._repository.list_plans(
            user_id, offset=(page - 1) * page_size, limit=page_size
        )
        return PlanPage(
            [self._to_plan_data(item) for item in items],
            total,
            page,
            page_size,
            ceil(total / page_size) if total else 0,
        )

    def get_plan(self, plan_id: int, user_id: int) -> PlanData:
        return self._to_plan_data(self._get_owned_plan(plan_id, user_id))

    def create_plan(self, user_id: int, data: PlanCreateData) -> PlanData:
        self._validate_plan_relations(data.project_id, data.course_id, user_id)
        if data.status not in {LearningPlanStatus.DRAFT, LearningPlanStatus.ACTIVE}:
            raise ConflictError("新计划只能是草稿或进行中状态")
        plan = LearningPlan(
            user_id=user_id,
            title=data.title,
            description=data.description,
            status=data.status,
            start_date=data.start_date,
            end_date=data.end_date,
            goal_data=data.goal_data,
            progress=0,
            project_id=data.project_id,
            course_id=data.course_id,
        )
        return self._save_plan(plan)

    def update_plan(self, plan_id: int, user_id: int, data: PlanUpdateData) -> PlanData:
        plan = self._get_owned_plan(plan_id, user_id)
        changes = data.changes
        project_id = changes.get("project_id", plan.project_id)
        course_id = changes.get("course_id", plan.course_id)
        self._validate_plan_relations(project_id, course_id, user_id)
        start_date = changes.get("start_date", plan.start_date)
        end_date = changes.get("end_date", plan.end_date)
        if start_date and end_date and end_date < start_date:
            raise ConflictError("计划结束日期不能早于开始日期")
        if "status" in changes and changes["status"] != plan.status:
            self._validate_transition(plan.status, changes["status"], PLAN_TRANSITIONS, "计划")
            if changes["status"] == LearningPlanStatus.COMPLETED and plan.progress < 100:
                raise ConflictError("仍有未完成任务，不能完成学习计划")
        for field_name, value in changes.items():
            setattr(plan, field_name, value)
        return self._save_plan(plan)

    def delete_plan(self, plan_id: int, user_id: int) -> None:
        plan = self._get_owned_plan(plan_id, user_id)
        try:
            self._repository.delete_plan(plan)
        except LearningPersistenceConflictError as exc:
            raise ConflictError("学习计划当前无法删除") from exc

    def list_tasks(
        self,
        user_id: int,
        *,
        page: int,
        page_size: int,
        scheduled_date: date | None,
        plan_id: int | None,
    ) -> TaskPage:
        if plan_id is not None:
            self._get_owned_plan(plan_id, user_id)
        total = self._repository.count_tasks(
            user_id, scheduled_date=scheduled_date, plan_id=plan_id
        )
        items = self._repository.list_tasks(
            user_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            scheduled_date=scheduled_date,
            plan_id=plan_id,
        )
        return TaskPage(
            [self._to_task_data(item) for item in items],
            total,
            page,
            page_size,
            ceil(total / page_size) if total else 0,
        )

    def get_task(self, task_id: int, user_id: int) -> TaskData:
        return self._to_task_data(self._get_owned_task(task_id, user_id))

    def create_task(self, user_id: int, data: TaskCreateData) -> TaskData:
        plan, project_id = self._resolve_task_relations(
            data.plan_id, data.project_id, user_id, data.scheduled_date
        )
        task = DailyTask(
            user_id=user_id,
            title=data.title,
            description=data.description,
            priority=data.priority,
            status=TaskStatus.PENDING,
            scheduled_date=data.scheduled_date,
            start_time=data.start_time,
            end_time=data.end_time,
            estimated_minutes=data.estimated_minutes,
            plan_id=plan.id if plan else None,
            project_id=project_id,
        )
        return self._save_task(task, {plan.id} if plan else set())

    def update_task(self, task_id: int, user_id: int, data: TaskUpdateData) -> TaskData:
        task = self._get_owned_task(task_id, user_id)
        changes = data.changes
        old_plan_id = task.plan_id
        plan_id = changes.get("plan_id", task.plan_id)
        project_id = changes.get("project_id", task.project_id)
        scheduled_date = changes.get("scheduled_date", task.scheduled_date)
        plan, project_id = self._resolve_task_relations(
            plan_id, project_id, user_id, scheduled_date
        )
        start_time = changes.get("start_time", task.start_time)
        end_time = changes.get("end_time", task.end_time)
        if start_time and end_time and end_time <= start_time:
            raise ConflictError("结束时间必须晚于开始时间")
        if "status" in changes and changes["status"] != task.status:
            self._validate_transition(task.status, changes["status"], TASK_TRANSITIONS, "任务")
            task.completed_at = (
                datetime.now(UTC) if changes["status"] == TaskStatus.COMPLETED else None
            )
        for field_name, value in changes.items():
            setattr(task, field_name, value)
        task.plan_id = plan.id if plan else None
        task.project_id = project_id
        plan_ids = {item for item in (old_plan_id, task.plan_id) if item is not None}
        return self._save_task(task, plan_ids)

    def complete_task(self, task_id: int, user_id: int) -> TaskData:
        task = self._get_owned_task(task_id, user_id)
        if task.status == TaskStatus.COMPLETED:
            return self._to_task_data(task)
        self._validate_transition(task.status, TaskStatus.COMPLETED, TASK_TRANSITIONS, "任务")
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        return self._save_task(task, {task.plan_id} if task.plan_id else set())

    def delete_task(self, task_id: int, user_id: int) -> None:
        task = self._get_owned_task(task_id, user_id)
        try:
            self._repository.delete_task(task)
        except LearningPersistenceConflictError as exc:
            raise ConflictError("任务当前无法删除") from exc

    def list_records(self, user_id: int, *, page: int, page_size: int) -> RecordPage:
        total = self._repository.count_records(user_id)
        items = self._repository.list_records(
            user_id, offset=(page - 1) * page_size, limit=page_size
        )
        return RecordPage(
            [self._to_record_data(item) for item in items],
            total,
            page,
            page_size,
            ceil(total / page_size) if total else 0,
        )

    def get_record(self, record_id: int, user_id: int) -> RecordData:
        return self._to_record_data(self._get_owned_record(record_id, user_id))

    def create_record(self, user_id: int, data: RecordCreateData) -> RecordData:
        project_id, course_id, task_id = self._resolve_record_relations(
            data.project_id, data.course_id, data.task_id, user_id
        )
        self._validate_record_source(data.record_type, project_id, course_id, task_id)
        record = LearningRecord(
            user_id=user_id,
            title=data.title,
            content=data.content,
            record_type=data.record_type,
            duration_minutes=data.duration_minutes,
            occurred_at=data.occurred_at or datetime.now(UTC),
            project_id=project_id,
            course_id=course_id,
            task_id=task_id,
            record_metadata=data.record_metadata,
        )
        return self._save_record(record)

    def update_record(
        self, record_id: int, user_id: int, data: RecordUpdateData
    ) -> RecordData:
        record = self._get_owned_record(record_id, user_id)
        if (record.record_metadata or {}).get("source") == "teaching_submission":
            raise ConflictError("教学通过记录由评阅结果生成，不能手工修改")
        changes = data.changes
        project_id, course_id, task_id = self._resolve_record_relations(
            changes.get("project_id", record.project_id),
            changes.get("course_id", record.course_id),
            changes.get("task_id", record.task_id),
            user_id,
        )
        record_type = changes.get("record_type", record.record_type)
        self._validate_record_source(record_type, project_id, course_id, task_id)
        for field_name, value in changes.items():
            setattr(record, field_name, value)
        record.project_id = project_id
        record.course_id = course_id
        record.task_id = task_id
        return self._save_record(record)

    def delete_record(self, record_id: int, user_id: int) -> None:
        record = self._get_owned_record(record_id, user_id)
        try:
            self._repository.delete_record(record)
        except LearningPersistenceConflictError as exc:
            raise ConflictError("学习记录当前无法删除") from exc

    def _resolve_task_relations(
        self,
        plan_id: int | None,
        project_id: int | None,
        user_id: int,
        scheduled_date: date,
    ) -> tuple[LearningPlan | None, int | None]:
        plan = self._get_owned_plan(plan_id, user_id) if plan_id else None
        if project_id is not None:
            self._get_owned_project(project_id, user_id)
        if plan:
            if plan.start_date and scheduled_date < plan.start_date:
                raise ConflictError("任务日期早于计划开始日期")
            if plan.end_date and scheduled_date > plan.end_date:
                raise ConflictError("任务日期晚于计划结束日期")
            if plan.project_id is not None:
                if project_id is not None and project_id != plan.project_id:
                    raise ConflictError("任务项目必须与学习计划项目一致")
                project_id = plan.project_id
        return plan, project_id

    def _resolve_record_relations(
        self,
        project_id: int | None,
        course_id: int | None,
        task_id: int | None,
        user_id: int,
    ) -> tuple[int | None, int | None, int | None]:
        task = self._get_owned_task(task_id, user_id) if task_id else None
        if project_id is not None:
            self._get_owned_project(project_id, user_id)
        if course_id is not None:
            self._get_owned_course(course_id, user_id)
        if task:
            if task.project_id is not None:
                if project_id is not None and project_id != task.project_id:
                    raise ConflictError("记录项目必须与关联任务项目一致")
                project_id = task.project_id
            task_course_id = task.plan.course_id if task.plan else None
            if task_course_id is not None:
                if course_id is not None and course_id != task_course_id:
                    raise ConflictError("记录课程必须与关联任务计划课程一致")
                course_id = task_course_id
        return project_id, course_id, task.id if task else None

    @staticmethod
    def _validate_record_source(
        record_type: RecordType,
        project_id: int | None,
        course_id: int | None,
        task_id: int | None,
    ) -> None:
        if record_type == RecordType.PROJECT and project_id is None:
            raise ConflictError("项目实践记录必须关联项目")
        if record_type == RecordType.COURSE and course_id is None:
            raise ConflictError("课程学习记录必须关联课程")
        if record_type == RecordType.TASK and task_id is None:
            raise ConflictError("任务复盘记录必须关联任务")

    def _validate_plan_relations(
        self, project_id: int | None, course_id: int | None, user_id: int
    ) -> None:
        if project_id is not None:
            self._get_owned_project(project_id, user_id)
        if course_id is not None:
            self._get_owned_course(course_id, user_id)

    def _get_owned_plan(self, plan_id: int, user_id: int) -> LearningPlan:
        plan = self._repository.get_plan(plan_id)
        if plan is None:
            raise ResourceNotFoundError("学习计划不存在")
        if plan.user_id != user_id:
            raise PermissionDeniedError("无权访问该学习计划")
        return plan

    def _get_owned_task(self, task_id: int, user_id: int) -> DailyTask:
        task = self._repository.get_task(task_id)
        if task is None:
            raise ResourceNotFoundError("任务不存在")
        if task.user_id != user_id:
            raise PermissionDeniedError("无权访问该任务")
        return task

    def _get_owned_record(self, record_id: int, user_id: int) -> LearningRecord:
        record = self._repository.get_record(record_id)
        if record is None:
            raise ResourceNotFoundError("学习记录不存在")
        if record.user_id != user_id:
            raise PermissionDeniedError("无权访问该学习记录")
        return record

    def _get_owned_course(self, course_id: int, user_id: int) -> Course:
        course = self._repository.get_course(course_id)
        if course is None:
            raise ResourceNotFoundError("关联课程不存在")
        if course.owner_id != user_id:
            raise PermissionDeniedError("不能关联其他用户的课程")
        return course

    def _get_owned_project(self, project_id: int, user_id: int) -> Project:
        project = self._repository.get_project(project_id)
        if project is None:
            raise ResourceNotFoundError("关联项目不存在")
        if project.owner_id != user_id:
            raise PermissionDeniedError("不能关联其他用户的项目")
        return project

    @staticmethod
    def _validate_transition(current, target, transitions, resource: str) -> None:
        if target not in transitions[current]:
            raise ConflictError(f"{resource}不能从 {current.value} 变更为 {target.value}")

    def _save_plan(self, plan: LearningPlan) -> PlanData:
        try:
            return self._to_plan_data(self._repository.save_plan(plan))
        except LearningPersistenceConflictError as exc:
            raise ConflictError("学习计划数据冲突") from exc

    def _save_task(self, task: DailyTask, plan_ids: set[int]) -> TaskData:
        try:
            return self._to_task_data(
                self._repository.save_task(task, recalculate_plan_ids=plan_ids)
            )
        except LearningPersistenceConflictError as exc:
            raise ConflictError("任务数据冲突") from exc

    def _save_record(self, record: LearningRecord) -> RecordData:
        try:
            return self._to_record_data(self._repository.save_record(record))
        except LearningPersistenceConflictError as exc:
            raise ConflictError("学习记录数据冲突") from exc

    @staticmethod
    def _to_plan_data(plan: LearningPlan) -> PlanData:
        return PlanData(
            id=plan.id,
            title=plan.title,
            description=plan.description,
            status=plan.status,
            start_date=plan.start_date,
            end_date=plan.end_date,
            goal_data=plan.goal_data,
            progress=plan.progress,
            project=ResourceRefData(plan.project.id, plan.project.name) if plan.project else None,
            course=ResourceRefData(plan.course.id, plan.course.name) if plan.course else None,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    @staticmethod
    def _to_task_data(task: DailyTask) -> TaskData:
        return TaskData(
            id=task.id,
            title=task.title,
            description=task.description,
            priority=task.priority,
            status=task.status,
            scheduled_date=task.scheduled_date,
            start_time=task.start_time,
            end_time=task.end_time,
            estimated_minutes=task.estimated_minutes,
            completed_at=task.completed_at,
            plan=ResourceRefData(task.plan.id, task.plan.title) if task.plan else None,
            project=ResourceRefData(task.project.id, task.project.name) if task.project else None,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @staticmethod
    def _to_record_data(record: LearningRecord) -> RecordData:
        return RecordData(
            id=record.id,
            title=record.title,
            content=record.content,
            record_type=record.record_type,
            duration_minutes=record.duration_minutes,
            occurred_at=record.occurred_at,
            project=ResourceRefData(record.project.id, record.project.name) if record.project else None,
            course=ResourceRefData(record.course.id, record.course.name) if record.course else None,
            task=ResourceRefData(record.task.id, record.task.title) if record.task else None,
            record_metadata=record.record_metadata,
            created_at=record.created_at,
        )
