"""S10新版专题、提醒语义与一次应用的业务边界。"""

from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import get_current_user
from app.api.v1.analytics import get_recommendation_service
from app.core.exceptions import ConflictError
from app.main import create_app
from app.schemas.analytics import PublicationPayload, PracticeTopicSummary
from app.schemas.practice_analytics import PracticeSummary, RecommendationApplicationCreate
from app.services.analytics import validate_payload
from app.services.analytics_artifacts import load_publication
from app.services.learning import LearningService
from app.services.practice_recommendations import build_recommendations, validate_practice_summary


def practice_summary():
    ids = [str(uuid4()) for _ in range(10)]
    advice = [dict(attempt_id=ids[i], attempt_no=i+1, operation_id=ids[i+2],
                   ai_request_id=i+1, review_event_id=ids[i+4], issue_event_id=ids[i+6],
                   criterion_id="C05", issue_type="empty_result_contract", prompt_version=None,
                   source="ai_report") for i in range(2)]
    return PracticeSummary.model_validate(dict(
        semantics="advisory_process", cohort_rule="sessions_created_in_window;state_at_snapshot;events_in_window_before_cutoff",
        observed_event_coverage_start="2026-10-21T14:55:19Z", coverage_basis="first_retained_owner_event",
        session_count=1, attempt_count=2, no_submission_count=0, submission_event_count=2, personal_end_count=0,
        request_count=3, cancel_count=0, resume_count=0, teacher_confirmation_count=None,
        sessions=[dict(session_id=ids[8], project_id=3, template_id="python-learning-csv", template_version="1.0",
            context_version=1, revision=9, current_step_key="implement", status="waiting_confirmation",
            created_at="2026-10-26T00:00:00Z", attempt_count=2,
            event_counts={"session_started": 1, "review_started": 2, "attempt_submitted": 2},
            latest_attempt_id=ids[1], latest_attempt_no=2, latest_operation_id=ids[3], latest_ai_request_id=2,
            personal_reviewed=False, self_statement=None, output_comparison="unknown", teacher_confirmation=None,
            advice=advice)]))


class PracticeAnalyticsTests(unittest.TestCase):
    def test_repeated_model_report_is_optional_and_traceable(self):
        summary = practice_summary()
        validate_practice_summary(summary)
        candidate, = build_recommendations(summary)
        self.assertEqual(candidate.source, "ai_report")
        self.assertEqual(len(candidate.references), 2)
        self.assertIn("AI重复报告", candidate.explanation)
        self.assertIn("可自行选择", candidate.explanation)

    def test_one_attempt_or_other_category_does_not_trigger(self):
        for change in (lambda s: s.advice.pop(0), lambda s: setattr(s.advice[0], "issue_type", "counting")):
            summary = practice_summary()
            change(summary.sessions[0])
            self.assertEqual(build_recommendations(summary), [])

    def test_duplicate_same_attempt_never_counts_twice(self):
        summary = practice_summary()
        summary.sessions[0].advice = [summary.sessions[0].advice[1]] * 2
        self.assertEqual(build_recommendations(summary), [])
        with self.assertRaises(ValueError):
            validate_practice_summary(summary)

    def test_no_current_advice_or_finished_is_not_a_current_candidate(self):
        for field, value in (("personal_reviewed", True), ("status", "completed"),
                             ("status", "cancelled"), ("status", "failed"),
                             ("status", "running"), ("latest_operation_id", uuid4()),
                             ("latest_attempt_id", uuid4())):
            summary = practice_summary()
            setattr(summary.sessions[0], field, value)
            self.assertEqual(build_recommendations(summary), [], field)

    def test_counts_and_unknown_teacher_are_not_inferred(self):
        summary = practice_summary()
        self.assertIsNone(summary.teacher_confirmation_count)
        self.assertIsNone(summary.sessions[0].teacher_confirmation)
        summary.attempt_count += 1
        with self.assertRaises(ValueError):
            validate_practice_summary(summary)

    def test_explicit_version_and_topic_pairs(self):
        old = load_publication("v2-controlled")
        new = old.model_dump(mode="json")
        new.update(schema_version="scholarhub-source-2.0", metric_version="learning-process-2.0", rule_version="quality-2.0")
        new["topic_summary"] = dict(teaching=new["topic_summary"], practice=practice_summary().model_dump(mode="json"))
        validate_payload(PublicationPayload.model_validate(new))
        new["rule_version"] = "quality-1.0"
        with self.assertRaises(ValidationError):
            PublicationPayload.model_validate(new)
        new = old.model_dump(mode="json")
        new["topic_summary"] = dict(teaching=new["topic_summary"], practice=practice_summary().model_dump(mode="json"))
        with self.assertRaises(ValidationError):
            PublicationPayload.model_validate(new)


class MemoryRecommendationRepository:
    def __init__(self, batch, summary):
        self.batch, self.summary, self.applications = batch, summary, []

    @contextmanager
    def transaction(self):
        yield

    def lock_batch(self, owner, batch_id):
        return self.batch if owner == 3 and batch_id == self.batch.batch_id else None

    def by_request(self, owner, key):
        return next((item for item in self.applications if item.request_key == key), None)

    def by_candidate(self, owner, batch_id, key):
        return next((item for item in self.applications if item.candidate_key == key), None)

    def current_source(self, owner, session_id):
        item = self.summary.sessions[0]
        return dict(id=session_id, project_id=item.project_id, template_id=item.template_id,
                    template_version=item.template_version, context_version=item.context_version,
                    revision=item.revision, status=item.status, current_step_key=item.current_step_key), dict(
                    id=str(item.latest_attempt_id), operation_id=str(item.latest_operation_id), ai_request_id=item.latest_ai_request_id)

    def source_events(self, session_id, ids):
        return [dict(id=str(identity), attempt_id=str(item.attempt_id), event_type=kind,
                     criterion_id=item.criterion_id, issue_type=item.issue_type,
                     occurred_at=datetime(2026, 10, 26, tzinfo=UTC), operation_id=str(item.operation_id),
                     ai_request_id=item.ai_request_id)
                for item in self.summary.sessions[0].advice
                for identity, kind in ((item.review_event_id, "review_finished"), (item.issue_event_id, "criterion_issue"))]

    def save_application(self, application):
        self.applications.append(application)


class RecommendationApplicationTests(unittest.TestCase):
    def setUp(self):
        self.summary = practice_summary()
        old = load_publication("v2-controlled")
        self.batch = SimpleNamespace(batch_id=str(uuid4()), schema_version="scholarhub-source-2.0",
            metric_version="learning-process-2.0", rule_version="quality-2.0",
            topic_summary=PracticeTopicSummary(teaching=old.topic_summary, practice=self.summary).model_dump(mode="json"),
            source_cutoff=datetime(2026, 10, 27, tzinfo=UTC))
        self.repo = MemoryRecommendationRepository(self.batch, self.summary)
        self.learning = Mock()
        self.learning.add_recommendation_task.side_effect = lambda task: setattr(task, "id", 901)
        self.service = LearningService(self.learning, self.repo)
        self.service._resolve_task_relations = Mock(return_value=(None, 3))
        self.payload = RecommendationApplicationCreate(request_key="s10-unit-request", candidate_key=build_recommendations(self.summary)[0].candidate_key,
            expected_metric_version="learning-process-2.0", expected_rule_version="B-R1-advisory-1.0",
            expected_session_revision=9, title="本人审阅后的自测", scheduled_date="2026-10-27", project_id=3)

    def test_replay_compares_original_payload_not_editable_task(self):
        first = self.service.create_task_from_recommendation(3, self.payload, self.batch.batch_id)
        task = self.learning.add_recommendation_task.call_args.args[0]
        task.title = "后来修改的标题"
        second = self.service.create_task_from_recommendation(3, self.payload, self.batch.batch_id)
        self.assertEqual(first.task_id, second.task_id)
        self.assertTrue(second.replayed)
        self.learning.add_recommendation_task.assert_called_once()
        self.assertIsNone(task.plan_id)
        self.assertIn("/offline-analytics?batch_id=", task.description)

    def test_same_key_changed_payload_and_same_candidate_new_key_reject(self):
        self.service.create_task_from_recommendation(3, self.payload, self.batch.batch_id)
        for changes in ({"title": "不同载荷"}, {"request_key": "another-key"}):
            with self.assertRaises(ConflictError):
                self.service.create_task_from_recommendation(3, self.payload.model_copy(update=changes), self.batch.batch_id)
        self.learning.add_recommendation_task.assert_called_once()

    def test_changed_source_revision_rejects_before_task_creation(self):
        self.summary.sessions[0].revision += 1
        with self.assertRaises(ConflictError):
            self.service.create_task_from_recommendation(3, self.payload, self.batch.batch_id)
        self.learning.add_recommendation_task.assert_not_called()

    def test_missing_event_reference_rejects(self):
        self.repo.source_events = lambda *args: []
        with self.assertRaises(ConflictError):
            self.service.create_task_from_recommendation(3, self.payload, self.batch.batch_id)
        self.learning.add_recommendation_task.assert_not_called()

    def test_api_uses_narrow_application_and_rejects_extra_plan(self):
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=3)
        app.dependency_overrides[get_recommendation_service] = lambda: self.service
        with TestClient(app) as client:
            url = f"/api/v1/offline-analytics/batches/{self.batch.batch_id}/recommendation-applications"
            body = self.payload.model_dump(mode="json")
            self.assertEqual(client.post(url, json={**body, "plan_id": 3}).status_code, 422)
            result = client.post(url, json=body)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["task_id"], 901)


if __name__ == "__main__":
    unittest.main()
