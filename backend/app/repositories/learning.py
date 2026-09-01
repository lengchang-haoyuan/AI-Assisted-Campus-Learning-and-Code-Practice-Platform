from datetime import date

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

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

    def get_plan(self, plan_id: int) -> LearningPlan | None:
        return self._session.scalar(self._plan_query().where(LearningPlan.id == plan_id))

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
        row = self._session.execute(
            select(
                func.count(DailyTask.id),
                func.coalesce(
                    func.sum(case((DailyTask.status == TaskStatus.COMPLETED, 1), else_=0)),
                    0,
                ),
            ).where(DailyTask.plan_id == plan_id, DailyTask.user_id == user_id)
        ).one()
        progress = round(row[1] * 100 / row[0]) if row[0] else 0
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
        ).execution_options(populate_existing=True)

    def _commit_or_raise(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise LearningPersistenceConflictError from exc
