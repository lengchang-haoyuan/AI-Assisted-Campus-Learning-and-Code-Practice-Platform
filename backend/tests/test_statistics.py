from datetime import UTC, date, datetime
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_current_user, get_statistics_service
from app.main import create_app
from app.models.enums import ProjectStatus
from app.repositories.statistics import (
    ProjectStatisticsRecord,
    StatisticsRepository,
    TechnologyItemRecord,
    TodayStatisticsRecord,
    TrendStatisticsRecord,
)
from app.services.auth import UserIdentity
from app.services.statistics import StatisticsService
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
TODAY = date(2026, 9, 2)


def empty_trend(**overrides: dict[date, int]) -> TrendStatisticsRecord:
    values = {
        "visitors": {},
        "completed_task_users": {},
        "completed_tasks": {},
        "projects_created": {},
        "projects_completed": {},
        "projects_published": {},
        "comments": {},
        "likes": {},
        "favorites": {},
        "views": {},
    }
    values.update(overrides)
    return TrendStatisticsRecord(**values)


class StatisticsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=StatisticsRepository)
        self.service = StatisticsService(self.repository)

    def test_today_uses_local_day_bounds_and_sums_interactions(self) -> None:
        self.repository.get_today.return_value = TodayStatisticsRecord(
            visitors=3,
            completed_task_users=2,
            project_total=8,
            published_project_total=4,
            projects_created=1,
            projects_published=1,
            comments=2,
            likes=3,
            favorites=4,
            views=5,
        )

        result = self.service.get_today(480, now=NOW)

        self.assertEqual(result.community_interactions, 14)
        self.assertEqual(result.date, TODAY)
        self.repository.get_today.assert_called_once_with(
            start_at=datetime(2026, 9, 1, 16, 0, tzinfo=UTC),
            end_at=datetime(2026, 9, 2, 16, 0, tzinfo=UTC),
        )

    def test_trend_fills_missing_days_and_uses_distinct_daily_counts(self) -> None:
        self.repository.get_trend.return_value = empty_trend(
            visitors={TODAY: 3},
            completed_task_users={TODAY: 2},
            completed_tasks={TODAY: 4},
            comments={TODAY: 1},
            views={TODAY: 2},
        )

        result = self.service.get_trend(7, 480, now=NOW)

        self.assertEqual(len(result.items), 7)
        self.assertEqual(result.items[0].date, date(2026, 8, 27))
        self.assertEqual(result.items[0].visitors, 0)
        self.assertEqual(result.items[-1].community_interactions, 3)
        self.repository.get_trend.assert_called_once_with(
            start_at=datetime(2026, 8, 26, 16, 0, tzinfo=UTC),
            end_at=datetime(2026, 9, 2, 16, 0, tzinfo=UTC),
            timezone_offset="+08:00",
        )

    def test_projects_and_technology_stacks_have_stable_empty_semantics(self) -> None:
        self.repository.get_projects.return_value = ProjectStatisticsRecord(
            total=2,
            published=1,
            completed=0,
            average_progress=25.25,
            status_counts={ProjectStatus.IN_PROGRESS.value: 2},
            completion_trend={},
        )
        project_result = self.service.get_projects(30, 480, now=NOW)
        self.assertEqual(project_result.average_progress, 25.2)
        self.assertEqual(len(project_result.statuses), len(ProjectStatus))
        self.assertEqual(len(project_result.completion_trend), 30)

        self.repository.get_technology_stacks.return_value = {
            "language": [TechnologyItemRecord("Python", 2)],
            "framework": [],
            "frontend": [],
            "backend": [],
            "database": [],
        }
        self.repository.count_projects.return_value = 2
        technology_result = self.service.get_technology_stacks(10)
        self.assertEqual(technology_result.dimensions[0].items[0].percentage, 100.0)
        self.assertEqual(technology_result.dimensions[1].items, [])


class StatisticsAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=StatisticsService)
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="student",
            email="student@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_statistics_service] = lambda: self.service

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_statistics_routes_require_authentication(self) -> None:
        app = create_app()
        app.dependency_overrides[get_statistics_service] = lambda: self.service
        for path in (
            "/api/v1/statistics/today",
            "/api/v1/statistics/trend",
            "/api/v1/statistics/projects",
            "/api/v1/statistics/tech-stacks",
        ):
            with self.subTest(path=path):
                self.assertEqual(request(app, "GET", path).status_code, 401)

    def test_query_bounds_are_validated_before_service_call(self) -> None:
        response = request(
            self.app,
            "GET",
            "/api/v1/statistics/trend?days=365&timezone_offset_minutes=900",
        )
        self.assertEqual(response.status_code, 422)
        self.service.get_trend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
