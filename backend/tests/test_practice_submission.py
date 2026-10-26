"""S08工程编排测试；Fake结果不用于模型质量或真实MySQL锁的验收。"""

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import unittest
from uuid import uuid4

from app.ai.client import AIClient
from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.core.exceptions import AgentOutputError, AIUpstreamError, ConflictError, ResourceNotFoundError
from app.models.practice import PracticeAttempt
from app.practice.agent import PracticeGuidanceAgent
from app.practice.review import PracticeCodeGuidanceAgent, PracticeReviewAgent
from app.practice.templates import get_template
from app.services.practice import PracticeService
from tests.test_practice_agent import guidance_output
from tests.test_practice_review import review_draft
from tests.test_practice_service import (
    MemoryPracticeRepository,
    MemoryPracticeState,
    NOW,
    create_session,
    run_action,
)

_CONTRACT = json.loads((Path(__file__).resolve().parents[2] /
    "开发相关文档/阶段报告/AI大数据改造/V2/S01-AI固定模板与评价案例.json").read_text(encoding="utf-8-sig"))
_CASES = {item["case_id"]: item for item in _CONTRACT["cases"]}
GOOD_CODE = _CASES["Q01"]["student_code"]
BAD_CODE = _CASES["Q05"]["student_code"]
INCOMPLETE_CODE = _CASES["Q14"]["student_code"]


def declared_correct():
    return {item["test_id"]: deepcopy(item["expected"]) for item in get_template()["public_output_vectors"]}


@dataclass
class SubmissionMemoryState(MemoryPracticeState):
    attempts: dict[str, PracticeAttempt] = field(default_factory=dict)


class SubmissionMemoryRepository(MemoryPracticeRepository):
    def __init__(self, state=None):
        super().__init__(state or SubmissionMemoryState())

    def add(self, value):
        if isinstance(value, PracticeAttempt):
            if not self.in_transaction:
                raise AssertionError("尝试写入必须在事务内")
            for existing in self.state.attempts.values():
                if existing.session_id == value.session_id and (
                    existing.request_key == value.request_key or
                    (existing.step_key, existing.attempt_no) == (value.step_key, value.attempt_no)
                ):
                    raise ConflictError("测试仓储拒绝重复提交")
            value.created_at = value.updated_at = NOW
            self.state.attempts[value.id] = value
            return
        super().add(value)

    def get_attempt(self, session_id, attempt_id, lock=False):
        if lock:
            self.lock_history.append(("attempt", attempt_id))
        item = self.state.attempts.get(attempt_id)
        return item if item and item.session_id == session_id else None

    def list_attempts(self, session_id):
        return sorted((item for item in self.state.attempts.values() if item.session_id == session_id),
                      key=lambda item: (item.attempt_no, item.id))

    def get_attempts_for_update(self, session_id):
        items = sorted(self.list_attempts(session_id), key=lambda item: item.id)
        self.lock_history.extend(("attempt", item.id) for item in items)
        return items

    def latest_attempt(self, session_id, step_key="implement", lock=False):
        items = self.get_attempts_for_update(session_id) if lock else self.list_attempts(session_id)
        return max((item for item in items if item.step_key == step_key),
                   key=lambda item: (item.attempt_no, item.id), default=None)

    def get_attempt_by_request_key(self, session_id, request_key, lock=False):
        return next((item for item in self.list_attempts(session_id) if item.request_key == request_key), None)

    def latest_event(self, session_id, event_type):
        return next((item for item in reversed(list(self.state.events.values()))
                     if item.session_id == session_id and item.event_type == event_type), None)


class SubmissionProvider(AIProvider):
    def __init__(self, repository):
        self.repository = repository
        self.requests: list[AICompletionRequest] = []
        self.review_requests: list[AICompletionRequest] = []
        self.review_outcomes: list[dict | Exception] = []
        self.review_started = None
        self.review_release = None

    @property
    def name(self):
        return "fake"

    async def complete(self, request):
        if self.repository.in_transaction:
            raise AssertionError("Provider等待期间不能持事务")
        self.requests.append(request)
        if "PracticeReviewDraft" in request.messages[0].content:
            self.review_requests.append(request)
            if self.review_started is not None:
                self.review_started.set()
            if self.review_release is not None:
                await self.review_release.wait()
            outcome = self.review_outcomes.pop(0) if self.review_outcomes else review_draft(overall="pass")
        else:
            outcome = guidance_output()
        if isinstance(outcome, Exception):
            raise outcome
        return AIProviderResult(provider="fake", model=request.model,
            content=json.dumps(outcome, ensure_ascii=False), finish_reason="stop",
            usage=AIUsage(prompt_tokens=20, completion_tokens=30, total_tokens=50))


def build_submission_service():
    repository = SubmissionMemoryRepository()
    provider = SubmissionProvider(repository)
    client = AIClient(provider, total_timeout_seconds=5, max_retries=0,
                      retry_base_delay_seconds=0.1, max_retry_delay_seconds=1)
    options = {"model": "fake-model", "max_tokens": 1500, "temperature": 0.1}
    service = PracticeService(repository, PracticeGuidanceAgent(client, **options),
        provider_name="fake", model="fake-model", operation_timeout_seconds=2,
        review_agent=PracticeReviewAgent(client, **options),
        code_guidance_agent=PracticeCodeGuidanceAgent(client, **options))
    return service, repository, provider


def implement_session(service):
    item = create_session(service)
    item = run_action(service, item, "start")
    return run_action(service, item, "confirm")


def submit(service, item, *, code=GOOD_CODE, declared_output=None, request_key=None,
           self_statement=True, owner_id=1, expected_revision=None):
    return service.submit_attempt(owner_id=owner_id, session_id=item["id"],
        expected_revision=item["revision"] if expected_revision is None else expected_revision,
        step_key="implement", request_key=request_key or str(uuid4()), code=code,
        declared_output=declared_correct() if declared_output is None else declared_output,
        self_statement=self_statement)


class PracticeSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.service, self.repo, self.provider = build_submission_service()

    def latest(self, item):
        return self.repo.latest_attempt(item["id"])

    def review(self, item, *, outcome="pass", **changes):
        self.provider.review_outcomes.append(review_draft(overall=outcome))
        return run_action(self.service, item, "review", attempt_id=self.latest(item).id, **changes)

    def test_submission_can_end_without_suggestions_or_output_match_for_any_self_statement(self):
        for statement in (True, False, None):
            with self.subTest(statement=statement):
                item = submit(self.service, implement_session(self.service), code=BAD_CODE,
                              declared_output={}, self_statement=statement)
                before_calls = len(self.provider.requests)
                self.assertEqual(item["status"], "waiting_confirmation")
                self.assertTrue(item["current_attempt"]["can_confirm"])
                self.assertIsNone(item["current_attempt"]["feedback"]["ai_static_review"])
                key = str(uuid4())
                completed = run_action(self.service, item, "confirm", request_key=key,
                                       attempt_id=self.latest(item).id)
                replayed = run_action(self.service, item, "confirm", request_key=key,
                                      attempt_id=self.latest(item).id)
                self.assertEqual(completed["status"], "completed")
                self.assertTrue(replayed["replayed"])
                self.assertFalse(completed["current_attempt"]["can_confirm"])
                feedback = completed["current_attempt"]["feedback"]
                self.assertIs(feedback["self_statement"]["value"], statement)
                self.assertFalse(feedback["submitted_output_match"]["matched"])
                self.assertIsNone(feedback["teacher_confirmation"])
                self.assertIsNone(feedback["personal_confirmation"]["ai_request_id"])
                self.assertEqual(feedback["personal_confirmation"]["criteria"], [])
                self.assertEqual(feedback["personal_confirmation"]["actor_user_id"], 1)
                self.service.get(1, item["id"])
                self.service.list(1, 7)
                self.assertEqual(len(self.provider.requests), before_calls)
        self.assertEqual(self.provider.review_requests, [])

    def test_needs_changes_is_optional_advice_and_does_not_require_second_submission(self):
        item = submit(self.service, implement_session(self.service), code=BAD_CODE)
        item = self.review(item, outcome="needs_changes")
        before = deepcopy(self.latest(item).feedback["ai_static_review"])
        completed = run_action(self.service, item, "confirm", attempt_id=self.latest(item).id)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(len(completed["attempts"]), 1)
        self.assertEqual(self.latest(item).feedback["ai_static_review"], before)
        self.assertEqual(self.latest(item).feedback["personal_confirmation"]["ai_request_id"], before["ai_request_id"])
        self.assertFalse(any(event.event_type == "revision_requested" for event in self.repo.state.events.values()))

    def test_failed_and_invalid_suggestions_preserve_errors_usage_and_allow_local_completion(self):
        invalid = review_draft(overall="needs_changes")
        invalid["criteria"][0]["evidence_span"] = "fabricated code quote"
        cases = (
            (AIClientError("private failure without usage", category=AIFailureCategory.UPSTREAM),
             AIUpstreamError, "upstream", None, None),
            (AIClientError("private failure", category=AIFailureCategory.UPSTREAM,
                           observed_usage=AIUsage(prompt_tokens=7, completion_tokens=9, total_tokens=16)),
             AIUpstreamError, "upstream", 7, 9),
            ({"not": "a valid suggestion"}, AgentOutputError, "agent_output_invalid", 20, 30),
            (invalid, AgentOutputError, "agent_output_invalid", 20, 30),
        )
        for outcome, error, category, prompt_tokens, completion_tokens in cases:
            for resume_first in (False, True):
                with self.subTest(category=category, outcome=type(outcome).__name__, resume=resume_first):
                    item = submit(self.service, implement_session(self.service), code=BAD_CODE)
                    attempt_id = self.latest(item).id
                    self.provider.review_outcomes.append(outcome)
                    with self.assertRaises(error):
                        run_action(self.service, item, "review", attempt_id=attempt_id)
                    failed = self.service.get(1, item["id"])
                    request_id = failed["active_ai_request_id"]
                    self.assertEqual(failed["status"], "failed")
                    self.assertTrue(failed["current_attempt"]["can_confirm"])
                    self.assertIsNone(self.latest(item).feedback["ai_static_review"])
                    self.assertEqual(failed["model_request"]["error_code"], category)
                    self.assertEqual(failed["model_request"]["prompt_tokens"], prompt_tokens)
                    self.assertEqual(failed["model_request"]["completion_tokens"], completion_tokens)
                    before_calls = len(self.provider.requests)
                    if resume_first:
                        failed = run_action(self.service, failed, "resume")
                        self.assertEqual(failed["status"], "waiting_confirmation")
                    completed = run_action(self.service, failed, "confirm", attempt_id=attempt_id)
                    self.assertEqual(completed["status"], "completed")
                    self.assertIsNone(self.latest(item).feedback["ai_static_review"])
                    self.assertIsNone(self.latest(item).feedback["teacher_confirmation"])
                    self.assertEqual(self.latest(item).feedback["review_error"]["code"], category)
                    saved = self.repo.state.requests[request_id]
                    self.assertEqual(saved.error_code, category)
                    self.assertIsNone(saved.result)
                    self.assertEqual(len(self.provider.requests), before_calls)

    def test_confirmation_requires_owner_revision_binding_and_safe_session_state(self):
        item = submit(self.service, implement_session(self.service), declared_output={})
        attempt_id = self.latest(item).id
        for changes, error in (({"owner_id": 2}, ResourceNotFoundError),
                               ({"expected_revision": item["revision"] - 1}, ConflictError),
                               ({"attempt_id": str(uuid4())}, ResourceNotFoundError)):
            with self.subTest(changes=changes):
                with self.assertRaises(error):
                    run_action(self.service, item, "confirm", **{"attempt_id": attempt_id, **changes})
        original_feedback = deepcopy(self.latest(item).feedback)
        for field, value in (("attempt_id", str(uuid4())), ("attempt_no", 99),
                             ("template_version", "2.0"), ("context_version", 99)):
            self.latest(item).feedback = deepcopy(original_feedback)
            self.latest(item).feedback["binding"][field] = value
            with self.subTest(field=field), self.assertRaises(ConflictError):
                run_action(self.service, item, "confirm", attempt_id=attempt_id)
        self.latest(item).feedback = original_feedback
        cancelled = run_action(self.service, item, "cancel")
        self.assertFalse(cancelled["current_attempt"]["can_confirm"])
        with self.assertRaises(ConflictError):
            run_action(self.service, cancelled, "confirm", attempt_id=attempt_id)
        resumed = run_action(self.service, cancelled, "resume")
        self.assertEqual(resumed["status"], "waiting_confirmation")
        self.assertTrue(resumed["current_attempt"]["can_confirm"])
        self.assertEqual(len(self.provider.requests), 1)

    def test_legacy_revision_wait_can_be_reviewed_without_rewriting_history(self):
        item = submit(self.service, implement_session(self.service), code=BAD_CODE)
        item = self.review(item, outcome="needs_changes")
        self.repo.state.sessions[item["id"]].status = type(self.repo.state.sessions[item["id"]].status).WAITING_REVISION
        item = self.service.get(1, item["id"])
        before = deepcopy(self.latest(item).feedback["ai_static_review"])
        self.assertTrue(item["current_attempt"]["can_confirm"])
        completed = run_action(self.service, item, "confirm", attempt_id=self.latest(item).id)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.latest(item).feedback["ai_static_review"], before)
        self.assertEqual(len(self.provider.review_requests), 1)

    def test_expired_review_recovers_to_personal_wait_and_late_advice_cannot_change_completion(self):
        item = submit(self.service, implement_session(self.service))
        attempt_id = self.latest(item).id

        async def scenario():
            self.provider.review_started = asyncio.Event()
            self.provider.review_release = asyncio.Event()
            pending = asyncio.create_task(self.service.action(1, item["id"], "review", item["revision"], str(uuid4()), attempt_id))
            await asyncio.wait_for(self.provider.review_started.wait(), 1)
            running = self.service.get(1, item["id"])
            self.assertFalse(running["current_attempt"]["can_confirm"])
            with self.assertRaises(ConflictError):
                await self.service.action(1, item["id"], "confirm", running["revision"], str(uuid4()), attempt_id)
            with self.assertRaises(ConflictError):
                await self.service.action(1, item["id"], "resume", running["revision"], str(uuid4()))
            request = self.repo.state.requests[running["active_ai_request_id"]]
            request.request_metadata = {**request.request_metadata,
                "recover_after": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
            resumed = await self.service.action(1, item["id"], "resume", running["revision"], str(uuid4()))
            self.assertEqual(resumed["status"], "waiting_confirmation")
            self.assertEqual(resumed["model_request"]["error_code"], "recovery_timeout")
            completed = await self.service.action(1, item["id"], "confirm", resumed["revision"], str(uuid4()), attempt_id)
            before = deepcopy(self.latest(item).feedback)
            self.provider.review_release.set()
            late = await asyncio.wait_for(pending, 1)
            self.assertTrue(late["detached"])
            self.assertEqual(late["status"], "completed")
            self.assertEqual(late["revision"], completed["revision"])
            self.assertEqual(self.latest(item).feedback, before)
            self.assertEqual(late["model_request"]["error_code"], "recovery_timeout")
            self.assertEqual(late["model_request"]["prompt_tokens"], 20)

        asyncio.run(scenario())
        self.assertEqual(len(self.provider.review_requests), 1)

    def test_fresh_service_reads_same_current_attempt_without_model_or_state_changes(self):
        item = submit(self.service, implement_session(self.service), declared_output={})
        fresh = PracticeService(SubmissionMemoryRepository(self.repo.state), self.service.agent,
                                provider_name="fake", model="fake-model")
        before_events = set(self.repo.state.events)
        loaded = fresh.get(1, item["id"])
        self.assertEqual(loaded["current_attempt"], item["current_attempt"])
        self.assertTrue(loaded["current_attempt"]["can_confirm"])
        self.assertEqual(loaded["revision"], item["revision"])
        self.assertEqual(set(self.repo.state.events), before_events)
        self.assertEqual(len(self.provider.requests), 1)

    def test_first_correct_submission_requires_personal_confirmation_then_completes(self):
        item = implement_session(self.service)
        item = submit(self.service, item)
        attempt_id = item["submission"]["attempt_id"]
        self.assertEqual(item["submission"]["attempt_no"], 1)
        self.assertEqual(item["status"], "waiting_confirmation")
        self.assertEqual(len(self.provider.requests), 1)
        item = self.review(item)
        self.assertEqual(item["status"], "waiting_confirmation")
        evidence = self.repo.state.attempts[attempt_id].feedback
        self.assertIsNone(evidence["teacher_confirmation"])
        self.assertIsNone(evidence["personal_confirmation"])
        self.assertTrue(evidence["submitted_output_match"]["matched"])
        self.assertFalse(evidence["submitted_output_match"]["code_executed"])
        self.assertEqual(evidence["ai_static_review"]["review"]["overall"], "pass")
        with self.assertRaises(ConflictError):
            run_action(self.service, item, "review", attempt_id=attempt_id)
        completed = run_action(self.service, item, "confirm", attempt_id=attempt_id)
        self.assertEqual(completed["status"], "completed")
        evidence = self.repo.state.attempts[attempt_id].feedback
        self.assertIsNotNone(evidence["personal_confirmation"])
        self.assertIsNone(evidence["teacher_confirmation"])
        self.assertEqual(len(self.provider.requests), 2)
        self.assertEqual(len(completed["attempts"]), 1)

    def test_optional_revisions_preserve_history_and_understanding(self):
        item = implement_session(self.service)
        understanding = deepcopy(item["step_outputs"]["understand"])
        records = []
        for index in (1, 2):
            item = submit(self.service, item, code=BAD_CODE + f"\n# revision-{index}\n")
            item = self.review(item, outcome="needs_changes")
            self.assertEqual(item["status"], "waiting_confirmation")
            self.assertTrue(item["current_attempt"]["can_confirm"])
            current = self.latest(item)
            records.append((current.id, deepcopy(current.code_text), deepcopy(current.feedback)))
        item = submit(self.service, item, code=GOOD_CODE)
        self.assertEqual(item["step_outputs"]["understand"], understanding)
        self.assertNotIn("implement", item["step_outputs"])
        self.assertEqual([entry.attempt_no for entry in self.repo.list_attempts(item["id"])], [1, 2, 3])
        for attempt_id, code, feedback in records:
            self.assertEqual(self.repo.state.attempts[attempt_id].code_text, code)
            self.assertEqual(self.repo.state.attempts[attempt_id].feedback, feedback)
        item = self.review(item)
        item = run_action(self.service, item, "confirm", attempt_id=self.latest(item).id)
        self.assertEqual(item["status"], "completed")
        self.assertEqual(len(item["attempts"]), 3)

    def test_review_explain_and_confirm_without_required_attempt_are_conflicts(self):
        item = implement_session(self.service)
        for action in ("review", "explain", "confirm"):
            with self.subTest(action=action):
                with self.assertRaises(ConflictError):
                    run_action(self.service, item, action)
        item = submit(self.service, item)
        with self.assertRaises(ConflictError):
            run_action(self.service, item, "confirm")
        self.assertEqual(len(self.provider.requests), 1)

    def test_hint_and_explain_read_only_selected_current_attempt_code(self):
        item = implement_session(self.service)
        item = submit(self.service, item, code=BAD_CODE)
        first_id = self.latest(item).id
        with self.assertRaises(ConflictError):
            run_action(self.service, item, "hint")
        item = run_action(self.service, item, "hint", attempt_id=first_id)
        self.assertIn(BAD_CODE, self.provider.requests[-1].messages[-1].content)
        item = submit(self.service, item, code=GOOD_CODE + "\n# current-attempt-marker\n")
        current_id = self.latest(item).id
        with self.assertRaises(ConflictError):
            run_action(self.service, item, "explain", attempt_id=first_id)
        item = run_action(self.service, item, "explain", attempt_id=current_id)
        self.assertIn("current-attempt-marker", self.provider.requests[-1].messages[-1].content)
        self.assertEqual(item["status"], "waiting_confirmation")
        self.assertIsNone(self.repo.state.attempts[current_id].feedback["ai_static_review"])
        self.assertEqual(len(self.provider.review_requests), 0)

    def test_output_mismatch_does_not_block_personal_review_completion(self):
        item = submit(self.service, implement_session(self.service), declared_output={})
        item = self.review(item)
        attempt = self.latest(item)
        self.assertFalse(attempt.feedback["submitted_output_match"]["matched"])
        self.assertEqual(attempt.feedback["ai_static_review"]["review"]["overall"], "pass")
        completed = run_action(self.service, item, "confirm", attempt_id=attempt.id)
        self.assertEqual(completed["status"], "completed")
        self.assertFalse(completed["current_attempt"]["feedback"]["submitted_output_match"]["matched"])
        self.assertIsNone(completed["current_attempt"]["feedback"]["teacher_confirmation"])

    def test_insufficient_suggestions_retain_unknown_and_allow_personal_completion(self):
        item = submit(self.service, implement_session(self.service), code=INCOMPLETE_CODE)
        item = self.review(item, outcome="insufficient")
        self.assertEqual(item["status"], "waiting_confirmation")
        attempt = self.latest(item)
        review = attempt.feedback["ai_static_review"]["review"]
        self.assertEqual(review["overall"], "insufficient")
        self.assertTrue(all(entry["verdict"] == "unknown" for entry in review["criteria"]))
        completed = run_action(self.service, item, "confirm", attempt_id=attempt.id)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.latest(item).feedback["ai_static_review"]["review"], review)

    def test_failed_review_continue_retries_same_attempt_and_replay_has_zero_extra_calls(self):
        item = submit(self.service, implement_session(self.service))
        attempt_id = self.latest(item).id
        self.provider.review_outcomes.append(AIClientError("private failure body", category=AIFailureCategory.UPSTREAM, retryable=True))
        with self.assertRaises(AIUpstreamError):
            run_action(self.service, item, "review", attempt_id=attempt_id)
        failed = self.service.get(1, item["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(len(self.provider.review_requests), 1)
        retry_key = str(uuid4())
        reviewed = run_action(self.service, failed, "continue", attempt_id=attempt_id, request_key=retry_key)
        self.assertEqual(reviewed["status"], "waiting_confirmation")
        replay = run_action(self.service, failed, "continue", attempt_id=attempt_id, request_key=retry_key)
        self.assertTrue(replay["replayed"])
        self.assertEqual(len(self.provider.review_requests), 2)
        self.assertEqual(self.latest(item).attempt_no, 1)
        request_data = self.repo.state.requests[reviewed["active_ai_request_id"]]
        self.assertEqual(request_data.request_metadata["attempt_id"], attempt_id)
        self.assertEqual(request_data.request_metadata["retry_of"]["ai_request_id"], failed["active_ai_request_id"])
        self.assertNotIn("private failure body", json.dumps(reviewed, default=str))

    def test_cancelled_late_review_cannot_bind_to_new_attempt_after_resume(self):
        item = submit(self.service, implement_session(self.service))
        old_id = self.latest(item).id

        async def scenario():
            self.provider.review_started = asyncio.Event()
            self.provider.review_release = asyncio.Event()
            pending = asyncio.create_task(self.service.action(1, item["id"], "review", item["revision"], str(uuid4()), old_id))
            await asyncio.wait_for(self.provider.review_started.wait(), 1)
            self.assertFalse(self.repo.in_transaction)
            running = self.service.get(1, item["id"])
            with self.assertRaises(ConflictError):
                submit(self.service, running)
            cancelled = await self.service.action(1, item["id"], "cancel", running["revision"], str(uuid4()))
            self.assertEqual(cancelled["status"], "cancelled")
            resumed = await self.service.action(1, item["id"], "resume", cancelled["revision"], str(uuid4()))
            new_item = submit(self.service, resumed, code=GOOD_CODE + "\n# replacement-attempt\n")
            new_id = self.latest(new_item).id
            self.provider.review_release.set()
            late = await asyncio.wait_for(pending, 1)
            self.assertTrue(late["detached"])
            self.assertEqual(late["revision"], new_item["revision"])
            self.assertIsNone(self.repo.state.attempts[old_id].feedback["ai_static_review"])
            self.assertIsNone(self.repo.state.attempts[new_id].feedback["ai_static_review"])
            self.assertEqual(self.repo.state.attempts[old_id].code_text, GOOD_CODE)
            self.assertEqual(self.repo.state.attempts[new_id].attempt_no, 2)

        asyncio.run(scenario())
        self.assertEqual(len(self.provider.review_requests), 1)

    def test_submission_owner_version_and_replay_payload_are_enforced(self):
        item = implement_session(self.service)
        with self.assertRaises(ResourceNotFoundError):
            submit(self.service, item, owner_id=2)
        with self.assertRaises(ConflictError):
            submit(self.service, item, expected_revision=item["revision"] - 1)
        key = str(uuid4())
        original = deepcopy(item)
        item = submit(self.service, item, request_key=key.upper())
        replay = submit(self.service, original, request_key=key)
        self.assertTrue(replay["submission"]["replayed"])
        self.assertEqual(replay["submission"]["attempt_id"], item["submission"]["attempt_id"])
        typed_output = declared_correct()
        typed_output["T04"]["record_count"] = True
        for changes in ({"code": BAD_CODE}, {"declared_output": {}}, {"declared_output": typed_output}, {"self_statement": False},
                        {"expected_revision": original["revision"] + 1}):
            with self.subTest(changes=changes):
                with self.assertRaises(ConflictError):
                    submit(self.service, original, request_key=key, **changes)
        self.assertEqual(len(self.repo.state.attempts), 1)
        self.assertEqual(len(self.provider.requests), 1)

    def test_interleaved_same_revision_submission_and_confirmation_commit_once(self):
        item = implement_session(self.service)

        async def submissions():
            async def one():
                return submit(self.service, item)
            return await asyncio.gather(one(), one(), return_exceptions=True)

        outcomes = asyncio.run(submissions())
        self.assertEqual(sum(isinstance(outcome, ConflictError) for outcome in outcomes), 1)
        submitted = next(outcome for outcome in outcomes if isinstance(outcome, dict))
        self.assertEqual(len(self.repo.state.attempts), 1)
        reviewed = submitted
        attempt_id = self.latest(reviewed).id

        async def confirmations():
            return await asyncio.gather(
                self.service.action(1, reviewed["id"], "confirm", reviewed["revision"], str(uuid4()), attempt_id),
                self.service.action(1, reviewed["id"], "confirm", reviewed["revision"], str(uuid4()), attempt_id),
                return_exceptions=True,
            )

        outcomes = asyncio.run(confirmations())
        self.assertEqual(sum(isinstance(outcome, ConflictError) for outcome in outcomes), 1)
        self.assertEqual(self.service.get(1, item["id"])["status"], "completed")
        self.assertEqual(sum(event.event_type == "session_completed" for event in self.repo.state.events.values()), 1)

    def test_submission_and_confirmation_rollbacks_leave_no_success_event_or_evidence(self):
        item = implement_session(self.service)
        before = set(self.repo.state.events)
        self.repo.fail_next_flush = True
        with self.assertRaises(RuntimeError):
            submit(self.service, item)
        self.assertEqual(self.repo.state.attempts, {})
        self.assertEqual(set(self.repo.state.events), before)
        self.assertEqual(self.service.get(1, item["id"])["revision"], item["revision"])
        item = self.review(submit(self.service, item))
        attempt_id = self.latest(item).id
        evidence = deepcopy(self.repo.state.attempts[attempt_id].feedback)
        before = set(self.repo.state.events)
        self.repo.fail_next_flush = True
        with self.assertRaises(RuntimeError):
            run_action(self.service, item, "confirm", attempt_id=attempt_id)
        self.assertEqual(self.service.get(1, item["id"])["status"], "waiting_confirmation")
        self.assertEqual(self.repo.state.attempts[attempt_id].feedback, evidence)
        self.assertEqual(set(self.repo.state.events), before)

    def test_review_events_reference_criteria_without_code_or_private_body_and_get_is_read_only(self):
        item = submit(self.service, implement_session(self.service), code=BAD_CODE)
        item = self.review(item, outcome="needs_changes")
        count = len(self.provider.requests)
        before_events = set(self.repo.state.events)
        self.service.get(1, item["id"])
        self.service.list(1, 7)
        self.assertEqual(len(self.provider.requests), count)
        self.assertEqual(set(self.repo.state.events), before_events)
        events = list(self.repo.state.events.values())
        for expected in ("attempt_submitted", "review_started", "review_finished", "criterion_issue"):
            self.assertIn(expected, [event.event_type for event in events])
        issues = [event for event in events if event.event_type == "criterion_issue"]
        self.assertEqual([(event.criterion_id, event.issue_type) for event in issues], [("C01", "missing_header_validation")])
        for event in events:
            payload = json.dumps(event.action_payload)
            for forbidden in ("code_text", "declared_output", "student_code", "suggested_self_test", "def summarize_records", "return {}"):
                self.assertNotIn(forbidden, payload)
        feedback = self.latest(item).feedback
        self.assertEqual(feedback["self_statement"]["source"], "student_declaration")
        self.assertEqual(feedback["ai_static_review"]["source"], "ai_static_review")
        self.assertEqual(feedback["submitted_output_match"]["source"], "server_fixed_value_comparison")
        self.assertIsNone(feedback["teacher_confirmation"])


class PracticeSubmissionAPITests(unittest.TestCase):
    def setUp(self):
        from app.api.deps import get_current_user, get_db_session
        from app.api.practice_deps import get_practice_service
        from app.main import create_app
        from tests.test_practice_api import current_user, forbid_database
        self.app = create_app()
        self.service, self.repo, self.provider = build_submission_service()
        self.user = current_user()
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_db_session] = forbid_database
        self.app.dependency_overrides[get_practice_service] = lambda: self.service

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def post(self, item, path, body):
        from tests.test_api_foundation import request
        return request(self.app, "POST", f"/api/v1/practice-sessions/{item['id']}/{path}", body=body)

    def body(self, item, **changes):
        return {"expected_revision": item["revision"], "step_key": "implement", "request_key": str(uuid4()),
                "code": GOOD_CODE, "declared_output": declared_correct(), "self_statement": True, **changes}

    def test_routes_allow_completion_without_advice_and_guard_owner_version_and_cancel(self):
        from tests.test_practice_api import current_user
        item = implement_session(self.service)
        response = self.post(item, "attempts", self.body(item, code=BAD_CODE, declared_output={}, self_statement=False))
        self.assertEqual(response.status_code, 201, response.body)
        item = response.json()
        body = {"action": "confirm", "expected_revision": item["revision"],
                "attempt_id": item["current_attempt"]["id"], "request_key": str(uuid4())}
        self.assertEqual(self.post(item, "actions", {**body, "expected_revision": item["revision"] - 1}).status_code, 409)
        self.user = current_user(2)
        self.assertEqual(self.post(item, "actions", body).status_code, 404)
        self.user = current_user()
        cancelled = self.post(item, "actions", {**body, "action": "cancel", "request_key": str(uuid4())}).json()
        self.assertEqual(self.post(cancelled, "actions", {**body, "expected_revision": cancelled["revision"]}).status_code, 409)
        resumed = self.post(cancelled, "actions", {"action": "resume", "expected_revision": cancelled["revision"],
                                                   "request_key": str(uuid4())}).json()
        self.assertEqual(resumed["status"], "waiting_confirmation")
        response = self.post(resumed, "actions", {**body, "expected_revision": resumed["revision"]})
        self.assertEqual(response.status_code, 200, response.body)
        completed = response.json()
        self.assertEqual(completed["status"], "completed")
        self.assertIsNone(completed["current_attempt"]["feedback"]["ai_static_review"])
        self.assertIsNone(completed["current_attempt"]["feedback"]["teacher_confirmation"])
        self.assertEqual(len(self.provider.requests), 1)

    def test_routes_recover_failed_suggestion_without_new_provider_request(self):
        from tests.test_api_foundation import request
        item = submit(self.service, implement_session(self.service))
        attempt_id = item["current_attempt"]["id"]
        self.provider.review_outcomes.append({"invalid": "synthetic"})
        response = self.post(item, "actions", {"action": "review", "expected_revision": item["revision"],
                                               "attempt_id": attempt_id, "request_key": str(uuid4())})
        self.assertEqual(response.status_code, 502, response.body)
        item = request(self.app, "GET", f"/api/v1/practice-sessions/{item['id']}").json()
        self.assertEqual(item["model_request"]["error_code"], "agent_output_invalid")
        response = self.post(item, "actions", {"action": "resume", "expected_revision": item["revision"],
                                               "request_key": str(uuid4())})
        self.assertEqual(response.status_code, 200, response.body)
        item = response.json()
        response = self.post(item, "actions", {"action": "confirm", "expected_revision": item["revision"],
                                               "attempt_id": attempt_id, "request_key": str(uuid4())})
        self.assertEqual(response.status_code, 200, response.body)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["model_request"]["completion_tokens"], 30)
        self.assertIsNone(response.json()["current_attempt"]["feedback"]["ai_static_review"])
        self.assertEqual(len(self.provider.requests), 2)

    def test_real_submission_review_and_confirmation_routes_bind_evidence(self):
        item = implement_session(self.service)
        response = self.post(item, "attempts", self.body(item))
        self.assertEqual(response.status_code, 201, response.body)
        item = response.json()
        attempt_id = item["submission"]["attempt_id"]
        response = self.post(item, "actions", {"action": "review", "expected_revision": item["revision"],
            "attempt_id": attempt_id, "request_key": str(uuid4())})
        self.assertEqual(response.status_code, 200, response.body)
        item = response.json()
        self.assertEqual(item["status"], "waiting_confirmation")
        response = self.post(item, "actions", {"action": "confirm", "expected_revision": item["revision"],
            "attempt_id": attempt_id, "request_key": str(uuid4())})
        self.assertEqual(response.status_code, 200, response.body)
        self.assertEqual(response.json()["status"], "completed")
        self.assertIsNone(response.json()["attempts"][0]["feedback"]["teacher_confirmation"])

    def test_submission_schema_owner_conflict_and_missing_current_attempt_errors(self):
        from tests.test_practice_api import current_user
        item = implement_session(self.service)
        for changes in ({"code": " "}, {"code": "x" * 12001}, {"declared_output": {"x": "y" * 8192}},
                        {"self_statement": "true"}, {"teacher_confirmation": True}):
            with self.subTest(changes=changes):
                response = self.post(item, "attempts", self.body(item, **changes))
                self.assertEqual(response.status_code, 422, response.body)
        response = self.post(item, "actions", {"action": "review", "expected_revision": item["revision"], "request_key": str(uuid4())})
        self.assertEqual(response.status_code, 409, response.body)
        self.user = current_user(2)
        response = self.post(item, "attempts", self.body(item))
        self.assertEqual(response.status_code, 404, response.body)
        self.user = current_user()
        response = self.post(item, "attempts", self.body(item, expected_revision=item["revision"] - 1))
        self.assertEqual(response.status_code, 409, response.body)
        self.assertEqual(self.repo.state.attempts, {})
        self.assertEqual(len(self.provider.requests), 1)


if __name__ == "__main__":
    unittest.main()
