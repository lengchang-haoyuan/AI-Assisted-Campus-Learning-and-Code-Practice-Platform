import asyncio
from datetime import UTC, date, datetime
import json
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.agents.base import AgentOutputValidationError
from app.agents.learning_report import LearningReportAgent
from app.agents.learning_report_schemas import LearningReportSource
from app.ai.client import AIClient
from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.api.deps import get_current_user, get_learning_report_service
from app.main import create_app
from app.models.ai import AIRequest, AIResult
from app.models.enums import AIRequestStatus, ReportStatus
from app.models.learning import LearningReport
from app.repositories.learning_report import LearningReportRepository
from app.services.auth import UserIdentity
from app.services.learning_report import LearningReportService
from tests.test_api_foundation import request

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
PERIOD_START = date(2026, 8, 27)
PERIOD_END = date(2026, 9, 2)


def source_payload() -> dict[str, object]:
    return {
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "timezone_offset_minutes": 480,
        "learning": {
            "record_count": 4,
            "total_minutes": 180,
            "active_days": 3,
            "by_type": {"study": 2, "project": 2},
        },
        "tasks": {"total": 5, "completed": 4, "completion_rate": 80.0},
        "projects": {
            "total": 2,
            "published": 1,
            "completed": 1,
            "average_progress": 65.0,
            "by_status": {"in_progress": 1, "completed": 1},
        },
        "workflows": {
            "total_runs": 2,
            "completed_runs": 1,
            "failed_runs": 1,
            "success_rate": 50.0,
        },
        "ai_usage": {
            "request_count": 3,
            "completed_count": 2,
            "failed_count": 1,
            "prompt_tokens": 800,
            "completion_tokens": 300,
        },
        "community": {
            "comments": 2,
            "likes": 3,
            "favorites": 1,
            "project_views": 5,
        },
    }


def report_json(*, summary: str = "本周学习节奏稳定。") -> str:
    return json.dumps(
        {
            "result_type": "learning_report",
            "summary": summary,
            "achievement": ["完成 4 项任务", "累计学习 180 分钟"],
            "problems": ["Workflow 成功率仍有提升空间"],
            "suggestions": ["下周优先复盘失败 Workflow"],
            "structured_data": {
                "performance_level": "steady",
                "total_learning_minutes": 180,
                "active_days": 3,
                "task_completion_rate": 80.0,
                "project_average_progress": 65.0,
                "workflow_success_rate": 50.0,
                "ai_request_count": 3,
                "focus_areas": ["Workflow", "项目实践"],
                "recommended_weekly_minutes": 240,
            },
        },
        ensure_ascii=False,
    )


class QueueProvider(AIProvider):
    def __init__(self, outcomes: list[str | AIClientError]) -> None:
        self._outcomes = outcomes.copy()
        self.requests: list[AICompletionRequest] = []

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request_data: AICompletionRequest) -> AIProviderResult:
        self.requests.append(request_data)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, AIClientError):
            raise outcome
        return AIProviderResult(
            provider="fake",
            model=request_data.model,
            content=outcome,
            finish_reason="stop",
            usage=AIUsage(
                prompt_tokens=80,
                completion_tokens=40,
                total_tokens=120,
            ),
        )


def make_agent(provider: AIProvider) -> LearningReportAgent:
    client = AIClient(
        provider,
        total_timeout_seconds=1,
        max_retries=0,
        retry_base_delay_seconds=0.1,
        max_retry_delay_seconds=1,
    )
    return LearningReportAgent(
        client,
        model="fake-model",
        max_tokens=1200,
        temperature=0.1,
    )


def make_report(status: ReportStatus, *, report_id: int = 7) -> LearningReport:
    report = LearningReport(
        id=report_id,
        user_id=1,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )
    if status == ReportStatus.COMPLETED:
        payload = json.loads(report_json())
        report.summary = payload["summary"]
        report.achievements = payload["achievement"]
        report.problems = payload["problems"]
        report.suggestions = payload["suggestions"]
        report.structured_data = payload["structured_data"]
        report.generated_at = NOW
        report.ai_result = AIResult(
            id=3,
            request_id=5,
            result_type="learning_report",
            structured_result=payload,
            created_at=NOW,
        )
    elif status == ReportStatus.FAILED:
        report.summary = "学习报告生成失败，可在服务恢复后重试。"
        report.structured_data = {
            "error": {"code": "network", "message": "AI 服务调用失败，请稍后重试"}
        }
    return report


class LearningReportAgentTests(unittest.TestCase):
    def test_fake_provider_returns_schema_validated_report(self) -> None:
        provider = QueueProvider([report_json()])
        execution = asyncio.run(
            make_agent(provider).run(LearningReportSource.model_validate(source_payload()))
        )

        self.assertEqual(execution.result.structured_data.total_learning_minutes, 180)
        self.assertEqual(execution.result.achievement[0], "完成 4 项任务")
        self.assertNotIn("学习记录正文", provider.requests[0].messages[1].content)
        self.assertIn("total_minutes", provider.requests[0].messages[1].content)

    def test_invalid_or_sensitive_model_output_is_rejected(self) -> None:
        for output in ("not-json", report_json(summary="api_key=sk-abcdefghijklmnop")):
            with self.subTest(output=output[:12]):
                with self.assertRaises(AgentOutputValidationError):
                    asyncio.run(
                        make_agent(QueueProvider([output])).run(
                            LearningReportSource.model_validate(source_payload())
                        )
                    )


class LearningReportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=LearningReportRepository)

    def test_provider_failure_is_persisted_and_returned_as_retryable_state(self) -> None:
        error = AIClientError(
            "network detail",
            category=AIFailureCategory.NETWORK,
        )
        self.repository.collect_source.return_value = {
            key: value for key, value in source_payload().items() if key != "timezone_offset_minutes"
        }
        pending = make_report(ReportStatus.PENDING)
        ai_request = AIRequest(
            id=9,
            user_id=1,
            provider="fake",
            model="fake-model",
            request_type="learning_report",
            status=AIRequestStatus.RUNNING,
            input_hash="a" * 64,
            requested_at=NOW,
        )
        self.repository.prepare_generation.return_value = (pending, ai_request)
        self.repository.fail_generation.return_value = make_report(ReportStatus.FAILED)
        service = LearningReportService(
            self.repository, make_agent(QueueProvider([error]))
        )

        result = asyncio.run(
            service.generate(
                1,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                timezone_offset_minutes=480,
                now=NOW,
            )
        )

        self.assertEqual(result.status, ReportStatus.FAILED)
        self.assertEqual(result.error.code, "network")
        self.repository.fail_generation.assert_called_once_with(
            7,
            9,
            error_code="network",
            error_message="AI 服务调用失败，请稍后重试",
        )

    def test_report_lookup_is_current_user_scoped(self) -> None:
        self.repository.get_for_user.return_value = make_report(ReportStatus.COMPLETED)
        service = LearningReportService(
            self.repository, make_agent(QueueProvider([report_json()]))
        )

        result = service.get_report(7, 2)

        self.assertEqual(result.status, ReportStatus.COMPLETED)
        self.repository.get_for_user.assert_called_once_with(7, 2)


class LearningReportAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = Mock(spec=LearningReportService)
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1,
            username="student",
            email="student@example.com",
            avatar_url=None,
            bio=None,
            is_active=True,
            created_at=NOW,
        )
        self.app.dependency_overrides[get_learning_report_service] = lambda: self.service

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_routes_require_authentication_and_validate_period(self) -> None:
        app = create_app()
        app.dependency_overrides[get_learning_report_service] = lambda: self.service
        self.assertEqual(
            request(app, "GET", "/api/v1/learning-reports").status_code, 401
        )

        response = request(
            self.app,
            "POST",
            "/api/v1/learning-reports",
            body={
                "period_start": "2026-01-01",
                "period_end": "2026-09-02",
                "timezone_offset_minutes": 480,
            },
        )
        self.assertEqual(response.status_code, 422)
        self.service.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
