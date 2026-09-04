from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, distinct, func, select
from sqlalchemy.orm import Session

from app.models.community import Comment, Favorite, Like, ProjectView
from app.models.enums import ProjectStatus, TaskStatus
from app.models.learning import DailyTask
from app.models.project import Project
from app.repositories.project_progress import project_progress_rows


@dataclass(frozen=True, slots=True)
class TodayStatisticsRecord:
    visitors: int
    completed_task_users: int
    project_total: int
    published_project_total: int
    projects_created: int
    projects_published: int
    comments: int
    likes: int
    favorites: int
    views: int


@dataclass(frozen=True, slots=True)
class TrendStatisticsRecord:
    visitors: dict[date, int]
    completed_task_users: dict[date, int]
    completed_tasks: dict[date, int]
    projects_created: dict[date, int]
    projects_completed: dict[date, int]
    projects_published: dict[date, int]
    comments: dict[date, int]
    likes: dict[date, int]
    favorites: dict[date, int]
    views: dict[date, int]


@dataclass(frozen=True, slots=True)
class ProjectStatisticsRecord:
    total: int
    published: int
    completed: int
    average_progress: float
    status_counts: dict[str, int]
    completion_trend: dict[date, int]


@dataclass(frozen=True, slots=True)
class TechnologyItemRecord:
    name: str
    count: int


class StatisticsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_today(
        self, *, start_at: datetime, end_at: datetime
    ) -> TodayStatisticsRecord:
        return TodayStatisticsRecord(
            visitors=self._count_distinct_between(
                ProjectView.user_id, ProjectView.viewed_at, start_at, end_at
            ),
            completed_task_users=self._count_distinct_between(
                DailyTask.user_id,
                DailyTask.completed_at,
                start_at,
                end_at,
                DailyTask.status == TaskStatus.COMPLETED,
            ),
            project_total=self._scalar_count(Project.id),
            published_project_total=self._scalar_count(
                Project.id, Project.is_published.is_(True)
            ),
            projects_created=self._count_between(
                Project.id, Project.created_at, start_at, end_at
            ),
            projects_published=self._count_between(
                Project.id, Project.published_at, start_at, end_at
            ),
            comments=self._count_between(
                Comment.id,
                Comment.created_at,
                start_at,
                end_at,
                Comment.is_deleted.is_(False),
            ),
            likes=self._count_between(Like.id, Like.created_at, start_at, end_at),
            favorites=self._count_between(
                Favorite.id, Favorite.created_at, start_at, end_at
            ),
            views=self._count_between(
                ProjectView.id, ProjectView.viewed_at, start_at, end_at
            ),
        )

    def count_projects(self) -> int:
        return self._scalar_count(Project.id)

    def get_trend(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        timezone_offset: str,
    ) -> TrendStatisticsRecord:
        return TrendStatisticsRecord(
            visitors=self._grouped_count(
                ProjectView.viewed_at,
                ProjectView.id,
                start_at,
                end_at,
                timezone_offset,
                distinct_column=ProjectView.user_id,
            ),
            completed_task_users=self._grouped_count(
                DailyTask.completed_at,
                DailyTask.id,
                start_at,
                end_at,
                timezone_offset,
                DailyTask.status == TaskStatus.COMPLETED,
                distinct_column=DailyTask.user_id,
            ),
            completed_tasks=self._grouped_count(
                DailyTask.completed_at,
                DailyTask.id,
                start_at,
                end_at,
                timezone_offset,
                DailyTask.status == TaskStatus.COMPLETED,
            ),
            projects_created=self._grouped_count(
                Project.created_at,
                Project.id,
                start_at,
                end_at,
                timezone_offset,
            ),
            projects_completed=self._grouped_count(
                Project.completed_at,
                Project.id,
                start_at,
                end_at,
                timezone_offset,
                Project.status == ProjectStatus.COMPLETED,
            ),
            projects_published=self._grouped_count(
                Project.published_at,
                Project.id,
                start_at,
                end_at,
                timezone_offset,
                Project.is_published.is_(True),
            ),
            comments=self._grouped_count(
                Comment.created_at,
                Comment.id,
                start_at,
                end_at,
                timezone_offset,
                Comment.is_deleted.is_(False),
            ),
            likes=self._grouped_count(
                Like.created_at, Like.id, start_at, end_at, timezone_offset
            ),
            favorites=self._grouped_count(
                Favorite.created_at,
                Favorite.id,
                start_at,
                end_at,
                timezone_offset,
            ),
            views=self._grouped_count(
                ProjectView.viewed_at,
                ProjectView.id,
                start_at,
                end_at,
                timezone_offset,
            ),
        )

    def get_projects(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        timezone_offset: str,
    ) -> ProjectStatisticsRecord:
        status_rows = self._session.execute(
            select(Project.status, func.count(Project.id)).group_by(Project.status)
        )
        status_counts = {
            getattr(status, "value", str(status)): int(count)
            for status, count in status_rows
        }
        progress_rows = project_progress_rows()
        average_progress = self._session.scalar(select(func.avg(progress_rows.c.progress)))
        return ProjectStatisticsRecord(
            total=self._scalar_count(Project.id),
            published=self._scalar_count(Project.id, Project.is_published.is_(True)),
            completed=self._scalar_count(
                Project.id, Project.status == ProjectStatus.COMPLETED
            ),
            average_progress=float(average_progress or 0),
            status_counts=status_counts,
            completion_trend=self._grouped_count(
                Project.completed_at,
                Project.id,
                start_at,
                end_at,
                timezone_offset,
                Project.status == ProjectStatus.COMPLETED,
            ),
        )

    def get_technology_stacks(
        self, *, limit: int
    ) -> dict[str, list[TechnologyItemRecord]]:
        columns = {
            "language": Project.language,
            "framework": Project.framework,
            "frontend": Project.frontend,
            "backend": Project.backend,
            "database": Project.database,
        }
        result: dict[str, list[TechnologyItemRecord]] = {}
        for key, column in columns.items():
            rows = self._session.execute(
                select(column, func.count(Project.id))
                .where(column.is_not(None), func.trim(column) != "")
                .group_by(column)
                .order_by(func.count(Project.id).desc(), column.asc())
                .limit(limit)
            )
            result[key] = [
                TechnologyItemRecord(name=str(name), count=int(count))
                for name, count in rows
            ]
        return result

    def _scalar_count(self, column: Any, *conditions: ColumnElement[bool]) -> int:
        statement = select(func.count(column))
        if conditions:
            statement = statement.where(*conditions)
        return int(self._session.scalar(statement) or 0)

    def _count_between(
        self,
        count_column: Any,
        time_column: Any,
        start_at: datetime,
        end_at: datetime,
        *conditions: ColumnElement[bool],
    ) -> int:
        return self._scalar_count(
            count_column,
            time_column >= start_at,
            time_column < end_at,
            *conditions,
        )

    def _count_distinct_between(
        self,
        distinct_column: Any,
        time_column: Any,
        start_at: datetime,
        end_at: datetime,
        *conditions: ColumnElement[bool],
    ) -> int:
        statement = select(func.count(distinct(distinct_column))).where(
            time_column >= start_at,
            time_column < end_at,
            *conditions,
        )
        return int(self._session.scalar(statement) or 0)

    def _grouped_count(
        self,
        time_column: Any,
        count_column: Any,
        start_at: datetime,
        end_at: datetime,
        timezone_offset: str,
        *conditions: ColumnElement[bool],
        distinct_column: Any | None = None,
    ) -> dict[date, int]:
        local_date = func.date(func.convert_tz(time_column, "+00:00", timezone_offset))
        aggregate = (
            func.count(distinct(distinct_column))
            if distinct_column is not None
            else func.count(count_column)
        )
        rows = self._session.execute(
            select(local_date.label("local_date"), aggregate)
            .where(time_column >= start_at, time_column < end_at, *conditions)
            .group_by(local_date)
            .order_by(local_date)
        )
        return {self._as_date(day): int(count) for day, count in rows}

    @staticmethod
    def _as_date(value: date | datetime | str | Decimal) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
