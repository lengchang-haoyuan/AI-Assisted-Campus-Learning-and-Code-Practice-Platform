from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.enums import ProjectStatus, TaskStatus
from app.models.learning import DailyTask, LearningPlan, LearningRecord
from app.models.project import Project


class WorkspacePersistenceConflictError(Exception):
    """工作台数据写入与当前数据库状态冲突。"""


@dataclass(frozen=True, slots=True)
class TaskStatsRecord:
    total: int
    completed: int
    estimated_minutes: int


@dataclass(frozen=True, slots=True)
class WorkspaceProjectRecord:
    project: Project
    linked_task_count: int
    completed_task_count: int
    recorded_minutes: int


class WorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_tasks(self, user_id: int, scheduled_date: date | None = None) -> int:
        statement = select(func.count(DailyTask.id)).where(DailyTask.user_id == user_id)
        if scheduled_date is not None:
            statement = statement.where(DailyTask.scheduled_date == scheduled_date)
        return self._session.scalar(statement) or 0

    def list_tasks(
        self,
        user_id: int,
        *,
        offset: int,
        limit: int,
        scheduled_date: date | None = None,
    ) -> list[DailyTask]:
        statement = select(DailyTask).options(joinedload(DailyTask.project)).where(
            DailyTask.user_id == user_id
        )
        if scheduled_date is not None:
            statement = statement.where(DailyTask.scheduled_date == scheduled_date)
        statement = statement.order_by(
            DailyTask.scheduled_date.desc(),
            DailyTask.start_time.asc(),
            DailyTask.created_at.desc(),
            DailyTask.id.desc(),
        ).offset(offset).limit(limit)
        return list(self._session.scalars(statement))

    def list_project_tasks(
        self, user_id: int, project_id: int, *, limit: int
    ) -> list[DailyTask]:
        statement = (
            select(DailyTask)
            .options(joinedload(DailyTask.project))
            .where(
                DailyTask.user_id == user_id,
                DailyTask.project_id == project_id,
            )
            .order_by(
                DailyTask.scheduled_date.desc(),
                DailyTask.created_at.desc(),
                DailyTask.id.desc(),
            )
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def get_task_stats(self, user_id: int, scheduled_date: date) -> TaskStatsRecord:
        statement = select(
            func.count(DailyTask.id),
            func.coalesce(
                func.sum(case((DailyTask.status == TaskStatus.COMPLETED, 1), else_=0)),
                0,
            ),
            func.coalesce(func.sum(DailyTask.estimated_minutes), 0),
        ).where(
            DailyTask.user_id == user_id,
            DailyTask.scheduled_date == scheduled_date,
        )
        row = self._session.execute(statement).one()
        return TaskStatsRecord(total=row[0], completed=row[1], estimated_minutes=row[2])

    def get_task(self, task_id: int) -> DailyTask | None:
        return self._session.scalar(
            select(DailyTask)
            .options(joinedload(DailyTask.project))
            .where(DailyTask.id == task_id)
            .execution_options(populate_existing=True)
        )

    def create_task(self, task: DailyTask) -> DailyTask:
        self._session.add(task)
        self._commit_or_raise_conflict()
        saved = self.get_task(task.id)
        if saved is None:
            raise RuntimeError("任务写入后无法重新加载")
        return saved

    def update_task(self, task: DailyTask) -> DailyTask:
        try:
            self._session.flush()
            if task.plan_id is not None:
                self._recalculate_plan_progress(task.plan_id, task.user_id)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkspacePersistenceConflictError from exc
        saved = self.get_task(task.id)
        if saved is None:
            raise RuntimeError("任务更新后无法重新加载")
        return saved

    def _recalculate_plan_progress(self, plan_id: int, user_id: int) -> None:
        total, completed = self._session.execute(
            select(
                func.count(DailyTask.id),
                func.coalesce(
                    func.sum(
                        case((DailyTask.status == TaskStatus.COMPLETED, 1), else_=0)
                    ),
                    0,
                ),
            ).where(DailyTask.plan_id == plan_id, DailyTask.user_id == user_id)
        ).one()
        plan = self._session.scalar(
            select(LearningPlan).where(
                LearningPlan.id == plan_id,
                LearningPlan.user_id == user_id,
            )
        )
        if plan is not None:
            plan.progress = round(completed * 100 / total) if total else 0

    def count_records(self, user_id: int) -> int:
        return self._session.scalar(
            select(func.count(LearningRecord.id)).where(LearningRecord.user_id == user_id)
        ) or 0

    def list_records(
        self, user_id: int, *, offset: int, limit: int
    ) -> list[LearningRecord]:
        statement = (
            select(LearningRecord)
            .options(joinedload(LearningRecord.project))
            .where(LearningRecord.user_id == user_id)
            .order_by(LearningRecord.occurred_at.desc(), LearningRecord.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def create_record(self, record: LearningRecord) -> LearningRecord:
        self._session.add(record)
        self._commit_or_raise_conflict()
        saved = self._session.scalar(
            select(LearningRecord)
            .options(joinedload(LearningRecord.project))
            .where(LearningRecord.id == record.id)
        )
        if saved is None:
            raise RuntimeError("学习记录写入后无法重新加载")
        return saved

    def list_project_records(
        self, user_id: int, project_id: int, *, limit: int
    ) -> list[LearningRecord]:
        statement = (
            select(LearningRecord)
            .options(joinedload(LearningRecord.project))
            .where(
                LearningRecord.user_id == user_id,
                LearningRecord.project_id == project_id,
            )
            .order_by(LearningRecord.occurred_at.desc(), LearningRecord.id.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def sum_recorded_minutes(
        self, user_id: int, *, occurred_from: datetime, occurred_to: datetime
    ) -> int:
        statement = select(func.coalesce(func.sum(LearningRecord.duration_minutes), 0)).where(
            LearningRecord.user_id == user_id,
            LearningRecord.occurred_at >= occurred_from,
            LearningRecord.occurred_at < occurred_to,
        )
        return self._session.scalar(statement) or 0

    def count_projects(self, user_id: int) -> int:
        return self._session.scalar(
            select(func.count(Project.id)).where(Project.owner_id == user_id)
        ) or 0

    def count_active_projects(self, user_id: int) -> int:
        return self._session.scalar(
            select(func.count(Project.id)).where(
                Project.owner_id == user_id,
                Project.status == ProjectStatus.IN_PROGRESS,
            )
        ) or 0

    def list_projects(
        self, user_id: int, *, offset: int, limit: int
    ) -> list[WorkspaceProjectRecord]:
        statement = self._project_statement(user_id).where(Project.owner_id == user_id)
        statement = statement.order_by(Project.updated_at.desc(), Project.id.desc()).offset(
            offset
        ).limit(limit)
        return [self._to_project_record(row) for row in self._session.execute(statement)]

    def get_project(
        self, project_id: int, user_id: int
    ) -> WorkspaceProjectRecord | None:
        row = self._session.execute(
            self._project_statement(user_id).where(Project.id == project_id)
        ).first()
        return self._to_project_record(row) if row else None

    def _project_statement(self, user_id: int):
        task_count = (
            select(func.count(DailyTask.id))
            .where(DailyTask.project_id == Project.id, DailyTask.user_id == user_id)
            .correlate(Project)
            .scalar_subquery()
        )
        completed_count = (
            select(func.count(DailyTask.id))
            .where(
                DailyTask.project_id == Project.id,
                DailyTask.user_id == user_id,
                DailyTask.status == TaskStatus.COMPLETED,
            )
            .correlate(Project)
            .scalar_subquery()
        )
        recorded_minutes = (
            select(func.coalesce(func.sum(LearningRecord.duration_minutes), 0))
            .where(
                LearningRecord.project_id == Project.id,
                LearningRecord.user_id == user_id,
            )
            .correlate(Project)
            .scalar_subquery()
        )
        return select(Project, task_count, completed_count, recorded_minutes)

    @staticmethod
    def _to_project_record(row) -> WorkspaceProjectRecord:
        return WorkspaceProjectRecord(
            project=row[0],
            linked_task_count=row[1],
            completed_task_count=row[2],
            recorded_minutes=row[3],
        )

    def _commit_or_raise_conflict(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise WorkspacePersistenceConflictError from exc
