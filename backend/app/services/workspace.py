from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from math import ceil

from app.core.exceptions import ConflictError, PermissionDeniedError, ResourceNotFoundError
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
    WorkspacePersistenceConflictError,
    WorkspaceProjectRecord,
    WorkspaceRepository,
)


@dataclass(frozen=True, slots=True)
class WorkspaceProjectRefData:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class TaskCreateData:
    title: str
    description: str | None
    priority: TaskPriority
    scheduled_date: date
    start_time: time | None
    end_time: time | None
    estimated_minutes: int | None
    project_id: int | None


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
    project: WorkspaceProjectRefData | None
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
class LearningRecordCreateData:
    title: str
    content: str | None
    record_type: RecordType
    duration_minutes: int
    project_id: int | None
    occurred_at: datetime | None


@dataclass(frozen=True, slots=True)
class LearningRecordData:
    id: int
    title: str
    content: str | None
    record_type: RecordType
    duration_minutes: int
    occurred_at: datetime
    project: WorkspaceProjectRefData | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class LearningRecordPage:
    items: list[LearningRecordData]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class WorkspaceProjectData:
    id: int
    name: str
    description: str | None
    difficulty: ProjectDifficulty
    status: ProjectStatus
    language: str | None
    progress: int
    linked_task_count: int
    completed_task_count: int
    recorded_minutes: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceProjectPage:
    items: list[WorkspaceProjectData]
    total: int
    page: int
    page_size: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class WorkspaceProjectDetailData(WorkspaceProjectData):
    recent_tasks: list[TaskData]
    recent_records: list[LearningRecordData]


@dataclass(frozen=True, slots=True)
class WorkspaceStatsData:
    today_task_total: int
    today_task_completed: int
    today_estimated_minutes: int
    today_recorded_minutes: int
    learning_progress: int
    project_total: int
    active_project_total: int


@dataclass(frozen=True, slots=True)
class WorkspaceDashboardData:
    date: date
    stats: WorkspaceStatsData
    today_tasks: list[TaskData]
    recent_projects: list[WorkspaceProjectData]
    recent_records: list[LearningRecordData]


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository) -> None:
        self._repository = repository

    def get_dashboard(
        self, user_id: int, *, selected_date: date, utc_offset_minutes: int
    ) -> WorkspaceDashboardData:
        stats = self._repository.get_task_stats(user_id, selected_date)
        occurred_from, occurred_to = self._utc_day_bounds(
            selected_date, utc_offset_minutes
        )
        today_recorded_minutes = self._repository.sum_recorded_minutes(
            user_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
        projects = self._repository.list_projects(user_id, offset=0, limit=5)
        return WorkspaceDashboardData(
            date=selected_date,
            stats=WorkspaceStatsData(
                today_task_total=stats.total,
                today_task_completed=stats.completed,
                today_estimated_minutes=stats.estimated_minutes,
                today_recorded_minutes=today_recorded_minutes,
                learning_progress=round(stats.completed * 100 / stats.total)
                if stats.total
                else 0,
                project_total=self._repository.count_projects(user_id),
                active_project_total=self._repository.count_active_projects(user_id),
            ),
            today_tasks=[
                self._to_task_data(task)
                for task in self._repository.list_tasks(
                    user_id,
                    offset=0,
                    limit=6,
                    scheduled_date=selected_date,
                )
            ],
            recent_projects=[self._to_project_data(project) for project in projects],
            recent_records=[
                self._to_record_data(record)
                for record in self._repository.list_records(user_id, offset=0, limit=5)
            ],
        )

    def list_tasks(
        self,
        user_id: int,
        *,
        page: int,
        page_size: int,
        scheduled_date: date | None,
    ) -> TaskPage:
        total = self._repository.count_tasks(user_id, scheduled_date)
        tasks = self._repository.list_tasks(
            user_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            scheduled_date=scheduled_date,
        )
        return TaskPage(
            items=[self._to_task_data(task) for task in tasks],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def create_task(self, user_id: int, data: TaskCreateData) -> TaskData:
        self._validate_owned_project(data.project_id, user_id)
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
            project_id=data.project_id,
        )
        try:
            return self._to_task_data(self._repository.create_task(task))
        except WorkspacePersistenceConflictError as exc:
            raise ConflictError("任务数据与当前状态冲突") from exc

    def complete_task(self, task_id: int, user_id: int) -> TaskData:
        task = self._repository.get_task(task_id)
        if task is None:
            raise ResourceNotFoundError("任务不存在")
        if task.user_id != user_id:
            raise PermissionDeniedError("无权完成该任务")
        if task.status == TaskStatus.COMPLETED:
            return self._to_task_data(task)
        if task.status == TaskStatus.CANCELLED:
            raise ConflictError("已取消的任务不能完成")
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        try:
            return self._to_task_data(self._repository.update_task(task))
        except WorkspacePersistenceConflictError as exc:
            raise ConflictError("任务完成状态冲突") from exc

    def list_records(
        self, user_id: int, *, page: int, page_size: int
    ) -> LearningRecordPage:
        total = self._repository.count_records(user_id)
        records = self._repository.list_records(
            user_id, offset=(page - 1) * page_size, limit=page_size
        )
        return LearningRecordPage(
            items=[self._to_record_data(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def create_record(
        self, user_id: int, data: LearningRecordCreateData
    ) -> LearningRecordData:
        if data.record_type == RecordType.PROJECT and data.project_id is None:
            raise ConflictError("项目实践记录必须关联项目")
        if data.record_type in (RecordType.COURSE, RecordType.TASK):
            raise ConflictError("课程学习和任务复盘请在学习记录页面关联来源后创建")
        self._validate_owned_project(data.project_id, user_id)
        record = LearningRecord(
            user_id=user_id,
            title=data.title,
            content=data.content,
            record_type=data.record_type,
            duration_minutes=data.duration_minutes,
            project_id=data.project_id,
            occurred_at=data.occurred_at or datetime.now(UTC),
        )
        try:
            return self._to_record_data(self._repository.create_record(record))
        except WorkspacePersistenceConflictError as exc:
            raise ConflictError("学习记录与当前状态冲突") from exc

    def list_projects(
        self, user_id: int, *, page: int, page_size: int
    ) -> WorkspaceProjectPage:
        total = self._repository.count_projects(user_id)
        projects = self._repository.list_projects(
            user_id, offset=(page - 1) * page_size, limit=page_size
        )
        return WorkspaceProjectPage(
            items=[self._to_project_data(project) for project in projects],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_project(self, project_id: int, user_id: int) -> WorkspaceProjectDetailData:
        record = self._repository.get_project(project_id, user_id)
        if record is None:
            raise ResourceNotFoundError("项目不存在")
        if record.project.owner_id != user_id:
            raise PermissionDeniedError("无权访问该工作台项目")
        project = self._to_project_data(record)
        return WorkspaceProjectDetailData(
            id=project.id,
            name=project.name,
            description=project.description,
            difficulty=project.difficulty,
            status=project.status,
            language=project.language,
            progress=project.progress,
            linked_task_count=project.linked_task_count,
            completed_task_count=project.completed_task_count,
            recorded_minutes=project.recorded_minutes,
            updated_at=project.updated_at,
            recent_tasks=[
                self._to_task_data(task)
                for task in self._repository.list_project_tasks(
                    user_id, project_id, limit=8
                )
            ],
            recent_records=[
                self._to_record_data(item)
                for item in self._repository.list_project_records(
                    user_id, project_id, limit=8
                )
            ],
        )

    def _validate_owned_project(self, project_id: int | None, user_id: int) -> None:
        if project_id is None:
            return
        record = self._repository.get_project(project_id, user_id)
        if record is None:
            raise ResourceNotFoundError("关联项目不存在")
        if record.project.owner_id != user_id:
            raise PermissionDeniedError("不能关联其他用户的项目")

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
            project=WorkspaceProjectRefData(id=task.project.id, name=task.project.name)
            if task.project
            else None,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @staticmethod
    def _to_record_data(record: LearningRecord) -> LearningRecordData:
        if record.duration_minutes is None:
            raise RuntimeError("工作台学习记录缺少时长")
        return LearningRecordData(
            id=record.id,
            title=record.title,
            content=record.content,
            record_type=record.record_type,
            duration_minutes=record.duration_minutes,
            occurred_at=record.occurred_at,
            project=WorkspaceProjectRefData(
                id=record.project.id, name=record.project.name
            )
            if record.project
            else None,
            created_at=record.created_at,
        )

    @staticmethod
    def _to_project_data(record: WorkspaceProjectRecord) -> WorkspaceProjectData:
        project: Project = record.project
        progress = (
            round(record.completed_task_count * 100 / record.linked_task_count)
            if record.linked_task_count
            else project.progress
        )
        return WorkspaceProjectData(
            id=project.id,
            name=project.name,
            description=project.description,
            difficulty=project.difficulty,
            status=project.status,
            language=project.language,
            progress=progress,
            linked_task_count=record.linked_task_count,
            completed_task_count=record.completed_task_count,
            recorded_minutes=record.recorded_minutes,
            updated_at=project.updated_at,
        )

    @staticmethod
    def _utc_day_bounds(selected_date: date, utc_offset_minutes: int) -> tuple[datetime, datetime]:
        local_zone = timezone(timedelta(minutes=utc_offset_minutes))
        local_start = datetime.combine(selected_date, time.min, tzinfo=local_zone)
        return local_start.astimezone(UTC), (local_start + timedelta(days=1)).astimezone(UTC)
