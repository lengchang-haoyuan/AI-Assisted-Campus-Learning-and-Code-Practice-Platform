from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone

from app.models.enums import ProjectStatus
from app.repositories.statistics import StatisticsRepository


@dataclass(frozen=True, slots=True)
class TodayStatisticsData:
    date: date
    timezone_offset_minutes: int
    visitors: int
    completed_task_users: int
    project_total: int
    published_project_total: int
    projects_created: int
    projects_published: int
    community_interactions: int


@dataclass(frozen=True, slots=True)
class TrendPointData:
    date: date
    visitors: int
    completed_task_users: int
    completed_tasks: int
    projects_created: int
    projects_completed: int
    projects_published: int
    community_interactions: int


@dataclass(frozen=True, slots=True)
class TrendStatisticsData:
    days: int
    start_date: date
    end_date: date
    timezone_offset_minutes: int
    items: list[TrendPointData]


@dataclass(frozen=True, slots=True)
class ProjectStatusCountData:
    status: ProjectStatus
    count: int


@dataclass(frozen=True, slots=True)
class DailyCountData:
    date: date
    count: int


@dataclass(frozen=True, slots=True)
class ProjectStatisticsData:
    days: int
    total: int
    published: int
    completed: int
    average_progress: float
    statuses: list[ProjectStatusCountData]
    completion_trend: list[DailyCountData]


@dataclass(frozen=True, slots=True)
class TechnologyItemData:
    name: str
    count: int
    percentage: float


@dataclass(frozen=True, slots=True)
class TechnologyDimensionData:
    key: str
    label: str
    items: list[TechnologyItemData]


@dataclass(frozen=True, slots=True)
class TechnologyStatisticsData:
    total_projects: int
    dimensions: list[TechnologyDimensionData]


class StatisticsService:
    _TECHNOLOGY_LABELS = {
        "language": "语言",
        "framework": "框架",
        "frontend": "前端",
        "backend": "后端",
        "database": "数据库",
    }

    def __init__(self, repository: StatisticsRepository) -> None:
        self._repository = repository

    def get_today(
        self, timezone_offset_minutes: int, *, now: datetime | None = None
    ) -> TodayStatisticsData:
        local_today, start_at, end_at = self._period_bounds(
            1, timezone_offset_minutes, now=now
        )
        record = self._repository.get_today(start_at=start_at, end_at=end_at)
        return TodayStatisticsData(
            date=local_today,
            timezone_offset_minutes=timezone_offset_minutes,
            visitors=record.visitors,
            completed_task_users=record.completed_task_users,
            project_total=record.project_total,
            published_project_total=record.published_project_total,
            projects_created=record.projects_created,
            projects_published=record.projects_published,
            community_interactions=(
                record.comments + record.likes + record.favorites + record.views
            ),
        )

    def get_trend(
        self,
        days: int,
        timezone_offset_minutes: int,
        *,
        now: datetime | None = None,
    ) -> TrendStatisticsData:
        end_date, start_at, end_at = self._period_bounds(
            days, timezone_offset_minutes, now=now
        )
        start_date = end_date - timedelta(days=days - 1)
        record = self._repository.get_trend(
            start_at=start_at,
            end_at=end_at,
            timezone_offset=self._mysql_timezone_offset(timezone_offset_minutes),
        )
        items = []
        for offset in range(days):
            day = start_date + timedelta(days=offset)
            items.append(
                TrendPointData(
                    date=day,
                    visitors=record.visitors.get(day, 0),
                    completed_task_users=record.completed_task_users.get(day, 0),
                    completed_tasks=record.completed_tasks.get(day, 0),
                    projects_created=record.projects_created.get(day, 0),
                    projects_completed=record.projects_completed.get(day, 0),
                    projects_published=record.projects_published.get(day, 0),
                    community_interactions=(
                        record.comments.get(day, 0)
                        + record.likes.get(day, 0)
                        + record.favorites.get(day, 0)
                        + record.views.get(day, 0)
                    ),
                )
            )
        return TrendStatisticsData(
            days=days,
            start_date=start_date,
            end_date=end_date,
            timezone_offset_minutes=timezone_offset_minutes,
            items=items,
        )

    def get_projects(
        self,
        days: int,
        timezone_offset_minutes: int,
        *,
        now: datetime | None = None,
    ) -> ProjectStatisticsData:
        end_date, start_at, end_at = self._period_bounds(
            days, timezone_offset_minutes, now=now
        )
        start_date = end_date - timedelta(days=days - 1)
        record = self._repository.get_projects(
            start_at=start_at,
            end_at=end_at,
            timezone_offset=self._mysql_timezone_offset(timezone_offset_minutes),
        )
        return ProjectStatisticsData(
            days=days,
            total=record.total,
            published=record.published,
            completed=record.completed,
            average_progress=round(record.average_progress, 1),
            statuses=[
                ProjectStatusCountData(
                    status=status,
                    count=record.status_counts.get(status.value, 0),
                )
                for status in ProjectStatus
            ],
            completion_trend=[
                DailyCountData(
                    date=day,
                    count=record.completion_trend.get(day, 0),
                )
                for day in (
                    start_date + timedelta(days=offset) for offset in range(days)
                )
            ],
        )

    def get_technology_stacks(self, limit: int) -> TechnologyStatisticsData:
        record = self._repository.get_technology_stacks(limit=limit)
        total_projects = self._repository.count_projects()
        dimensions = []
        for key, label in self._TECHNOLOGY_LABELS.items():
            items = record[key]
            assigned_total = sum(item.count for item in items)
            dimensions.append(
                TechnologyDimensionData(
                    key=key,
                    label=label,
                    items=[
                        TechnologyItemData(
                            name=item.name,
                            count=item.count,
                            percentage=(
                                round(item.count * 100 / assigned_total, 1)
                                if assigned_total
                                else 0.0
                            ),
                        )
                        for item in items
                    ],
                )
            )
        return TechnologyStatisticsData(
            total_projects=total_projects,
            dimensions=dimensions,
        )

    @staticmethod
    def _period_bounds(
        days: int,
        timezone_offset_minutes: int,
        *,
        now: datetime | None,
    ) -> tuple[date, datetime, datetime]:
        offset_timezone = timezone(timedelta(minutes=timezone_offset_minutes))
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            raise ValueError("统计当前时间必须包含时区")
        local_today = current.astimezone(offset_timezone).date()
        start_date = local_today - timedelta(days=days - 1)
        local_start = datetime.combine(start_date, time.min, offset_timezone)
        local_end = datetime.combine(local_today + timedelta(days=1), time.min, offset_timezone)
        return local_today, local_start.astimezone(UTC), local_end.astimezone(UTC)

    @staticmethod
    def _mysql_timezone_offset(timezone_offset_minutes: int) -> str:
        sign = "+" if timezone_offset_minutes >= 0 else "-"
        absolute = abs(timezone_offset_minutes)
        return f"{sign}{absolute // 60:02d}:{absolute % 60:02d}"
