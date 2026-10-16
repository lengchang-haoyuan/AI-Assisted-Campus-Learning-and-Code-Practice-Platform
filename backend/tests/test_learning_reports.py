import asyncio
from datetime import UTC, date, datetime
from hashlib import sha256
import json
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

from sqlalchemy.orm import Session

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
from app.services.learning_report import LearningReportData, LearningReportService
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


class LearningReportGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configure_repository()

    def configure_repository(self) -> None:
        self.session = Mock(spec=Session)
        self.rows: dict[tuple[type, int], AIRequest | AIResult | LearningReport] = {}

        def add_row(row: AIRequest | AIResult | LearningReport) -> None:
            model = type(row)
            first_id = {LearningReport: 7, AIRequest: 9, AIResult: 3}[model]
            row.id = first_id + sum(key[0] is model for key in self.rows)
            row.created_at = NOW
            if isinstance(row, LearningReport):
                row.updated_at = NOW
            self.rows[(model, row.id)] = row

        def reload_report(statement: object) -> LearningReport | None:
            report = self.rows.get((LearningReport, 7))
            if report is not None:
                report.ai_result = self.rows.get((AIResult, report.ai_result_id))
            return report

        # 执行生产 Repository 的赋值和状态路径；Session 为 Mock，不能证明数据库持久化。
        self.session.add.side_effect = add_row
        self.session.get.side_effect = lambda model, key: self.rows.get((model, key))
        self.session.scalar.side_effect = reload_report
        self.session.scalars.return_value = []
        self.repository = LearningReportRepository(self.session)
        self.repository.collect_source = Mock(return_value=source_payload())
        self.repository.complete_generation = Mock(wraps=self.repository.complete_generation)
        self.repository.fail_generation = Mock(wraps=self.repository.fail_generation)

    def generate(self, provider: AIProvider) -> LearningReportData:
        return asyncio.run(
            LearningReportService(self.repository, make_agent(provider)).generate(
                1,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                timezone_offset_minutes=480,
                now=NOW,
            )
        )

    def assert_facts(
        self, actual: dict[str, object], expected: tuple[int, int, float, float, float, int]
    ) -> None:
        fields = (
            "total_learning_minutes", "active_days", "task_completion_rate",
            "project_average_progress", "workflow_success_rate", "ai_request_count",
        )
        self.assertEqual(tuple(actual[field] for field in fields), expected)

    def test_valid_but_wrong_facts_are_corrected_in_both_result_assignments(self) -> None:
        payload = json.loads(report_json())
        payload["structured_data"].update(
            total_learning_minutes=999, active_days=7, task_completion_rate=12.5,
            project_average_progress=0.0, workflow_success_rate=100.0, ai_request_count=99,
        )
        result = self.generate(QueueProvider([json.dumps(payload, ensure_ascii=False)]))

        self.assertEqual(result.status, ReportStatus.COMPLETED)
        self.assert_facts(result.structured_data.model_dump(), (180, 3, 80.0, 65.0, 50.0, 3))
        report = self.rows[(LearningReport, 7)]
        ai_result = report.ai_result
        saved = self.repository.complete_generation.call_args.kwargs["result"]
        self.assertEqual(ai_result.structured_result, saved)
        self.assertEqual(report.structured_data, saved["structured_data"])
        self.assertEqual(result.structured_data.model_dump(), report.structured_data)
        for field in ("summary", "achievement", "problems", "suggestions"):
            self.assertEqual(saved[field], payload[field])
        for field in ("performance_level", "focus_areas", "recommended_weekly_minutes"):
            self.assertEqual(saved["structured_data"][field], payload["structured_data"][field])
        canonical = json.dumps(saved, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(ai_result.content_hash, sha256(canonical.encode("utf-8")).hexdigest())
        self.assertEqual(self.rows[(AIRequest, 9)].status, AIRequestStatus.COMPLETED)
        self.repository.fail_generation.assert_not_called()

    def test_correct_output_is_preserved(self) -> None:
        self.generate(QueueProvider([report_json()]))
        self.assertEqual(
            self.repository.complete_generation.call_args.kwargs["result"],
            json.loads(report_json()),
        )

    def test_zero_partial_zero_and_rate_boundaries_use_source_values(self) -> None:
        cases = (
            (0, 0, 0.0, 0.0, 0.0, 0),
            (0, 3, 0.0, 65.0, 100.0, 0),
            (180, 3, 100.0, 100.0, 0.0, 3),
            (180, 3, 66.7, 33.3, 66.7, 3),
        )
        for facts in cases:
            with self.subTest(facts=facts):
                self.configure_repository()
                source = source_payload()
                source["learning"].update(total_minutes=facts[0], active_days=facts[1])
                source["tasks"].update(
                    total=3, completed={0.0: 0, 100.0: 3, 66.7: 2}[facts[2]],
                    completion_rate=facts[2],
                )
                source["projects"]["average_progress"] = facts[3]
                completed_runs = {0.0: 0, 100.0: 3, 66.7: 2}[facts[4]]
                source["workflows"].update(
                    total_runs=3, completed_runs=completed_runs,
                    failed_runs=3 - completed_runs, success_rate=facts[4],
                )
                source["ai_usage"]["request_count"] = facts[5]
                if facts[5] == 0:
                    source["ai_usage"] = {field: 0 for field in source["ai_usage"]}
                if not any(facts):
                    for section in ("learning", "tasks", "projects", "workflows", "ai_usage", "community"):
                        for field, value in source[section].items():
                            source[section][field] = {} if isinstance(value, dict) else 0
                self.repository.collect_source.return_value = source

                result = self.generate(QueueProvider([report_json()]))

                self.assert_facts(result.structured_data.model_dump(), facts)
                self.assert_facts(self.rows[(LearningReport, 7)].ai_result.structured_result["structured_data"], facts)

    def test_generation_uses_original_source_snapshot_without_requery(self) -> None:
        source = source_payload()
        self.repository.collect_source.return_value = source

        class DriftingProvider(QueueProvider):
            async def complete(provider_self, request_data: AICompletionRequest) -> AIProviderResult:
                response = await super().complete(request_data)
                source["learning"].update(total_minutes=777, active_days=7)
                source["tasks"]["completion_rate"] = 0.0
                source["projects"]["average_progress"] = 100.0
                source["workflows"]["success_rate"] = 0.0
                source["ai_usage"]["request_count"] = 99
                return response

        provider = DriftingProvider([report_json()])
        result = self.generate(provider)

        self.repository.collect_source.assert_called_once()
        self.assert_facts(result.structured_data.model_dump(), (180, 3, 80.0, 65.0, 50.0, 3))
        user_message = provider.requests[0].messages[1].content
        sent = json.loads(user_message.split("<AGGREGATED_LEARNING_DATA>")[1].split("</")[0])
        self.assertEqual(sent["learning"]["total_minutes"], 180)
        self.assertEqual(sent["tasks"]["completion_rate"], 80.0)

    def test_invalid_or_sensitive_output_stays_failed_and_can_be_retried(self) -> None:
        out_of_range = json.loads(report_json())
        out_of_range["structured_data"]["task_completion_rate"] = 101
        invalid_enum = json.loads(report_json())
        invalid_enum["structured_data"]["performance_level"] = "unknown"
        outputs = (
            "not-json", json.dumps(out_of_range), json.dumps(invalid_enum),
            report_json(summary="api_key=sk-abcdefghijklmnop"),
        )
        for output in outputs:
            with self.subTest(output=output[:12]):
                self.configure_repository()
                result = self.generate(QueueProvider([output]))
                self.assertEqual(result.status, ReportStatus.FAILED)
                self.assertEqual(result.error.code, "agent_output_invalid")
                self.assertIsNone(result.structured_data)
                self.assertEqual(self.rows[(AIRequest, 9)].status, AIRequestStatus.FAILED)
                self.assertFalse(any(model is AIResult for model, key in self.rows))
                self.repository.complete_generation.assert_not_called()

                retried = self.generate(QueueProvider([report_json()]))
                self.assertEqual(retried.status, ReportStatus.COMPLETED)
                self.assertEqual(retried.id, result.id)
                self.assertEqual(self.rows[(AIRequest, 10)].status, AIRequestStatus.COMPLETED)
                self.assertEqual(self.rows[(AIRequest, 9)].status, AIRequestStatus.FAILED)

    def test_cancellation_preserves_failed_state_and_reraises(self) -> None:
        class CancelledProvider(QueueProvider):
            async def complete(self, request_data: AICompletionRequest) -> AIProviderResult:
                raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.generate(CancelledProvider([]))

        report = self.rows[(LearningReport, 7)]
        self.assertEqual(report.status, ReportStatus.FAILED)
        self.assertEqual(report.structured_data["error"]["code"], "cancelled")
        self.assertEqual(self.rows[(AIRequest, 9)].status, AIRequestStatus.FAILED)
        self.repository.complete_generation.assert_not_called()
        self.assertIsNone(report.ai_result)

    def test_generate_list_and_detail_api_return_the_same_saved_facts(self) -> None:
        payload = json.loads(report_json())
        payload["structured_data"].update(total_learning_minutes=999, task_completion_rate=12.5)
        provider = QueueProvider([json.dumps(payload, ensure_ascii=False)])
        service = LearningReportService(self.repository, make_agent(provider))
        self.repository.count_for_user = Mock(return_value=1)
        self.repository.list_for_user = Mock(side_effect=lambda user_id, **kwargs: [self.rows[(LearningReport, 7)]])
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=1, username="student", email="student@example.com", avatar_url=None,
            bio=None, is_active=True, created_at=NOW,
        )
        app.dependency_overrides[get_learning_report_service] = lambda: service
        try:
            generated = request(app, "POST", "/api/v1/learning-reports", body={
                "period_start": PERIOD_START.isoformat(), "period_end": PERIOD_END.isoformat(),
                "timezone_offset_minutes": 480,
            })
            listed = request(app, "GET", "/api/v1/learning-reports")
            detail = request(app, "GET", "/api/v1/learning-reports/7")
            self.assertEqual(generated.status_code, 201)
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(detail.status_code, 200)
            actual = generated.json()["structured_data"]
            self.assert_facts(actual, (180, 3, 80.0, 65.0, 50.0, 3))
            self.assertEqual(listed.json()["items"][0]["structured_data"], actual)
            self.assertEqual(detail.json()["structured_data"], actual)
            self.repository.collect_source.assert_called_once()
            self.repository.list_for_user.assert_called_once_with(1, offset=0, limit=10)
        finally:
            app.dependency_overrides.clear()


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

    def test_foreign_report_is_not_returned_when_owner_scoped_lookup_is_empty(self) -> None:
        repository = Mock(spec=LearningReportRepository)
        repository.get_for_user.return_value = None
        repository.count_for_user.return_value = 0
        repository.list_for_user.return_value = []
        self.service = LearningReportService(repository, make_agent(QueueProvider([])))
        self.app.dependency_overrides[get_current_user] = lambda: UserIdentity(
            id=2, username="other_student", email="other@example.com", avatar_url=None,
            bio=None, is_active=True, created_at=NOW,
        )

        detail = request(self.app, "GET", "/api/v1/learning-reports/7")
        listed = request(self.app, "GET", "/api/v1/learning-reports")

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(detail.json()["error"]["code"], "resource_not_found")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["items"], [])
        repository.get_for_user.assert_called_once_with(7, 2)
        repository.count_for_user.assert_called_once_with(2)
        repository.list_for_user.assert_called_once_with(2, offset=0, limit=10)


if __name__ == "__main__":
    unittest.main()
