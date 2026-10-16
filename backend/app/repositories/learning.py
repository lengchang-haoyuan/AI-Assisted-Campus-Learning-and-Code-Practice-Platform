from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import set_committed_value

from app.models.course import Course
from app.models.enums import TaskStatus
from app.models.learning import DailyTask, LearningPlan, LearningRecord
from app.models.project import Project


class LearningPersistenceConflictError(Exception):
    """学习数据写入与当前数据库状态冲突。"""


class LearningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_plans(self, user_id: int) -> int:
        return self._session.scalar(
            select(func.count(LearningPlan.id)).where(LearningPlan.user_id == user_id)
        ) or 0

    def list_plans(self, user_id: int, *, offset: int, limit: int) -> list[LearningPlan]:
        return list(self._session.scalars(self._plan_query().where(
            LearningPlan.user_id == user_id
        ).order_by(LearningPlan.updated_at.desc(), LearningPlan.id.desc()).offset(offset).limit(limit)))

    def get_plan(self, plan_id: int, *, for_update: bool = False) -> LearningPlan | None:
        if for_update:
            return self._session.scalar(select(LearningPlan).where(LearningPlan.id == plan_id)
                .with_for_update().execution_options(populate_existing=True))
        return self._session.scalar(self._plan_query().where(LearningPlan.id == plan_id))

    def get_plan_task_counts(self, plan_id: int, user_id: int) -> tuple[int, int]:
        statuses = list(self._session.scalars(select(DailyTask.status).where(
            DailyTask.plan_id == plan_id, DailyTask.user_id == user_id,
        ).order_by(DailyTask.id).with_for_update()))
        return len(statuses), sum(status == TaskStatus.COMPLETED for status in statuses)

    def lock_task_plans(self, task: DailyTask, new_plan_id: int | None = None) -> None:
        with self._session.no_autoflush:
            original_plan_id = task.plan_id
            plans = {}
            for plan_id in sorted({value for value in (original_plan_id, new_plan_id) if value is not None}):
                plans[plan_id] = self.get_plan(plan_id, for_update=True)
            current = self._session.scalar(select(DailyTask).where(DailyTask.id == task.id)
                .with_for_update().execution_options(populate_existing=True))
            if current is None or current.plan_id != original_plan_id:
                self._session.rollback()
                raise LearningPersistenceConflictError("任务关联已被更新，请刷新后重试")
            set_committed_value(task, 'plan', plans.get(task.plan_id))

    def save_plan(self, plan: LearningPlan) -> LearningPlan:
        self._session.add(plan)
        self._commit_or_raise()
        saved = self.get_plan(plan.id)
        if saved is None:
            raise RuntimeError("学习计划写入后无法重新加载")
        return saved

    def delete_plan(self, plan: LearningPlan) -> None:
        self._session.delete(plan)
        self._commit_or_raise()

    def list_plan_task_project_ids(self, plan_id: int, user_id: int) -> set[int | None]:
        return set(self._session.scalars(
            select(DailyTask.project_id)
            .where(DailyTask.plan_id == plan_id, DailyTask.user_id == user_id)
            .distinct()
        ))

    def get_plan_task_date_bounds(
        self, plan_id: int, user_id: int
    ) -> tuple[date | None, date | None]:
        row = self._session.execute(
            select(func.min(DailyTask.scheduled_date), func.max(DailyTask.scheduled_date))
            .where(DailyTask.plan_id == plan_id, DailyTask.user_id == user_id)
        ).one()
        return row[0], row[1]

    def count_tasks(
        self,
        user_id: int,
        *,
        scheduled_date: date | None = None,
        plan_id: int | None = None,
    ) -> int:
        statement = select(func.count(DailyTask.id)).where(DailyTask.user_id == user_id)
        if scheduled_date is not None:
            statement = statement.where(DailyTask.scheduled_date == scheduled_date)
        if plan_id is not None:
            statement = statement.where(DailyTask.plan_id == plan_id)
        return self._session.scalar(statement) or 0

    def list_tasks(
        self,
        user_id: int,
        *,
        offset: int,
        limit: int,
        scheduled_date: date | None = None,
        plan_id: int | None = None,
    ) -> list[DailyTask]:
        statement = self._task_query().where(DailyTask.user_id == user_id)
        if scheduled_date is not None:
            statement = statement.where(DailyTask.scheduled_date == scheduled_date)
        if plan_id is not None:
            statement = statement.where(DailyTask.plan_id == plan_id)
        return list(self._session.scalars(statement.order_by(
            DailyTask.scheduled_date.desc(),
            DailyTask.start_time.asc(),
            DailyTask.id.desc(),
        ).offset(offset).limit(limit)))

    def get_task(self, task_id: int) -> DailyTask | None:
        return self._session.scalar(self._task_query().where(DailyTask.id == task_id))

    def save_task(
        self, task: DailyTask, *, recalculate_plan_ids: set[int]
    ) -> DailyTask:
        self._session.add(task)
        try:
            self._session.flush()
            for plan_id in recalculate_plan_ids:
                self._set_plan_progress(plan_id, task.user_id)
        except IntegrityError as exc:
            self._session.rollback()
            raise LearningPersistenceConflictError from exc
        self._commit_or_raise()
        saved = self.get_task(task.id)
        if saved is None:
            raise RuntimeError("任务写入后无法重新加载")
        return saved

    def delete_task(self, task: DailyTask) -> None:
        plan_id = task.plan_id
        self._session.delete(task)
        try:
            self._session.flush()
            if plan_id is not None:
                self._set_plan_progress(plan_id, task.user_id)
        except IntegrityError as exc:
            self._session.rollback()
            raise LearningPersistenceConflictError from exc
        self._commit_or_raise()

    def recalculate_plan_progress(self, plan_id: int, user_id: int) -> None:
        self._set_plan_progress(plan_id, user_id)
        self._commit_or_raise()

    def _set_plan_progress(self, plan_id: int, user_id: int) -> None:
        self.get_plan(plan_id, for_update=True)
        total, completed = self.get_plan_task_counts(plan_id, user_id)
        progress = round(completed * 100 / total) if total else 0
        self._session.execute(
            update(LearningPlan)
            .where(LearningPlan.id == plan_id, LearningPlan.user_id == user_id)
            .values(progress=progress)
        )

    def count_records(self, user_id: int) -> int:
        return self._session.scalar(
            select(func.count(LearningRecord.id)).where(LearningRecord.user_id == user_id)
        ) or 0

    def list_records(
        self, user_id: int, *, offset: int, limit: int
    ) -> list[LearningRecord]:
        return list(self._session.scalars(self._record_query().where(
            LearningRecord.user_id == user_id
        ).order_by(LearningRecord.occurred_at.desc(), LearningRecord.id.desc()).offset(offset).limit(limit)))

    def get_record(self, record_id: int) -> LearningRecord | None:
        return self._session.scalar(
            self._record_query().where(LearningRecord.id == record_id)
        )

    def save_record(self, record: LearningRecord) -> LearningRecord:
        self._session.add(record)
        self._commit_or_raise()
        saved = self.get_record(record.id)
        if saved is None:
            raise RuntimeError("学习记录写入后无法重新加载")
        return saved

    def delete_record(self, record: LearningRecord) -> None:
        self._session.delete(record)
        self._commit_or_raise()

    def get_course(self, course_id: int) -> Course | None:
        return self._session.get(Course, course_id)

    def get_project(self, project_id: int) -> Project | None:
        return self._session.get(Project, project_id)

    @staticmethod
    def _plan_query():
        return select(LearningPlan).options(
            joinedload(LearningPlan.project), joinedload(LearningPlan.course)
        ).execution_options(populate_existing=True)

    @staticmethod
    def _task_query():
        return select(DailyTask).options(
            joinedload(DailyTask.plan).joinedload(LearningPlan.course),
            joinedload(DailyTask.project),
        ).execution_options(populate_existing=True)

    @staticmethod
    def _record_query():
        return select(LearningRecord).options(
            joinedload(LearningRecord.project),
            joinedload(LearningRecord.course),
            joinedload(LearningRecord.task),
            joinedload(LearningRecord.teaching_feedback),
        ).execution_options(populate_existing=True)

    def _commit_or_raise(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise LearningPersistenceConflictError from exc
