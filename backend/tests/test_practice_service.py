import asyncio
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace
import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.ai.client import AIClient
from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.context.context_schema import CORE_PROJECT_FIELD_MAP
from app.core.exceptions import (
    AgentOutputError,
    AIUpstreamError,
    AIUpstreamTimeoutError,
    ConflictError,
    ResourceNotFoundError,
)
from app.models.ai import AIRequest, AIResult
from app.models.enums import AIRequestStatus
from app.models.practice import PracticeEvent, PracticeSession
from app.practice.agent import PRACTICE_CONTEXT_FIELDS, PracticeGuidanceAgent
from app.services.practice import PracticeService
from tests.test_practice_agent import guidance_output, make_context

NOW = datetime(2026, 10, 21, 8, tzinfo=UTC)


@dataclass
class MemoryPracticeState:
    """仅验证Service编排；不作为数据库约束、隔离或重启恢复证据。"""

    projects: dict[int, SimpleNamespace] = field(default_factory=dict)
    sessions: dict[str, PracticeSession] = field(default_factory=dict)
    events: dict[tuple[str, str], PracticeEvent] = field(default_factory=dict)
    requests: dict[int, AIRequest] = field(default_factory=dict)
    next_request_id: int = 1


class MemoryPracticeRepository:
    def __init__(self, state: MemoryPracticeState | None = None) -> None:
        self.state = state or MemoryPracticeState()
        self.in_transaction = False
        self.fail_next_flush = False
        self.commits = 0
        self.rollbacks = 0
        self.lock_history: list[tuple[str, object]] = []
        if not self.state.projects:
            context = make_context()
            self.state.projects[7] = SimpleNamespace(
                id=7,
                owner_id=1,
                context_data=context.to_storage(),
                **{
                    project_field: deepcopy(getattr(context.values, context_field))
                    for context_field, project_field in CORE_PROJECT_FIELD_MAP.items()
                },
            )

    @contextmanager
    def transaction(self):
        if self.in_transaction:
            raise AssertionError("测试发现嵌套实践事务")
        before = deepcopy(self.state)
        self.in_transaction = True
        try:
            yield
        except BaseException:
            self.state.__dict__.clear()
            self.state.__dict__.update(before.__dict__)
            self.rollbacks += 1
            raise
        else:
            self.commits += 1
        finally:
            self.in_transaction = False

    def get_project(self, project_id, owner_id, lock=False):
        if lock:
            self.lock_history.append(("project", project_id))
        project = self.state.projects.get(project_id)
        return project if project and project.owner_id == owner_id else None

    def get_session(self, session_id, owner_id, lock=False):
        if lock:
            self.lock_history.append(("session", session_id))
        item = self.state.sessions.get(session_id)
        return item if item and item.owner_user_id == owner_id else None

    def get_session_project_id(self, session_id, owner_id):
        item = self.get_session(session_id, owner_id)
        return item.project_id if item else None

    def list_sessions(self, project_id, owner_id, offset, limit):
        items = [
            item
            for item in self.state.sessions.values()
            if item.project_id == project_id and item.owner_user_id == owner_id
        ]
        items.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return items[offset : offset + limit]

    def get_event(self, session_id, event_key):
        return self.state.events.get((session_id, event_key))

    def get_creation_event(self, project_id, owner_id, event_key):
        for (session_id, key), event in self.state.events.items():
            item = self.state.sessions[session_id]
            if key == event_key and item.project_id == project_id and item.owner_user_id == owner_id:
                return event
        return None

    def get_request(self, request_id, lock=False):
        if lock:
            self.lock_history.append(("request", request_id))
        return self.state.requests.get(request_id)

    def list_attempts(self, session_id):
        return []

    def get_attempts_for_update(self, session_id):
        return []

    def add(self, value):
        if not self.in_transaction:
            raise AssertionError("业务写入必须处于显式事务")
        if isinstance(value, PracticeSession):
            value.created_at = value.updated_at = NOW
            self.state.sessions[value.id] = value
        elif isinstance(value, AIRequest):
            value.id = self.state.next_request_id
            self.state.next_request_id += 1
            self.state.requests[value.id] = value
        elif isinstance(value, AIResult):
            value.id = value.request_id
            value.created_at = NOW
            self.state.requests[value.request_id].result = value
        elif isinstance(value, PracticeEvent):
            key = (value.session_id, value.event_key)
            if key in self.state.events:
                raise ConflictError("重复事件键")
            self.state.events[key] = value
        else:
            raise AssertionError(f"意外写入类型: {type(value).__name__}")

    def flush(self):
        if not self.in_transaction:
            raise AssertionError("flush必须处于显式事务")
        if self.fail_next_flush:
            self.fail_next_flush = False
            raise RuntimeError("injected-local-flush-failure")


class QueuePracticeProvider(AIProvider):
    def __init__(self, repository: MemoryPracticeRepository, outcomes=None) -> None:
        self.repository = repository
        self.outcomes = list(outcomes) if outcomes is not None else []
        self.requests: list[AICompletionRequest] = []
        self.started: asyncio.Event | None = None
        self.release: asyncio.Event | None = None

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request: AICompletionRequest) -> AIProviderResult:
        if self.repository.in_transaction:
            raise AssertionError("等待Provider期间仍持有事务")
        self.requests.append(request)
        if self.started is not None:
            self.started.set()
        if self.release is not None:
            await self.release.wait()
        outcome = self.outcomes.pop(0) if self.outcomes else json.dumps(guidance_output(), ensure_ascii=False)
        if isinstance(outcome, Exception):
            raise outcome
        return AIProviderResult(
            provider="fake",
            model=request.model,
            content=outcome,
            finish_reason="stop",
            usage=AIUsage(prompt_tokens=10, completion_tokens=12, total_tokens=22),
        )


def build_service(repository=None, provider=None, *, operation_timeout_seconds=2):
    repository = repository or MemoryPracticeRepository()
    provider = provider or QueuePracticeProvider(repository)
    agent = PracticeGuidanceAgent(
        AIClient(
            provider,
            total_timeout_seconds=5,
            max_retries=0,
            retry_base_delay_seconds=0.1,
            max_retry_delay_seconds=1,
        ),
        model="fake-model",
        max_tokens=1000,
        temperature=0.1,
    )
    service = PracticeService(
        repository,
        agent,
        provider_name="fake",
        model="fake-model",
        operation_timeout_seconds=operation_timeout_seconds,
    )
    return service, repository, provider


def create_session(service, *, request_key=None):
    return service.create(
        owner_id=1,
        project_id=7,
        template_id="python-learning-csv",
        template_version="1.0",
        expected_context_version=1,
        request_key=request_key or str(uuid4()),
    )


def run_action(service, item, action, *, request_key=None, owner_id=1, **changes):
    return asyncio.run(
        service.action(
            owner_id=owner_id,
            session_id=item["id"],
            action=action,
            expected_revision=changes.pop("expected_revision", item["revision"]),
            request_key=request_key or str(uuid4()),
            **changes,
        )
    )


class PracticeServiceTests(unittest.TestCase):
    def setUp(self):
        self.service, self.repo, self.provider = build_service()

    def test_ready_guidance_confirm_implement_cancel_resume_and_requery(self):
        item = create_session(self.service)
        self.assertEqual((item["status"], item["current_step_key"], item["revision"]), ("ready", "understand", 1))
        self.assertEqual(self.provider.requests, [])

        item = run_action(self.service, item, "start")
        self.assertEqual((item["status"], item["revision"]), ("waiting_confirmation", 3))
        self.assertEqual(item["outputs"]["understand"], guidance_output())
        item = run_action(self.service, item, "confirm")
        self.assertEqual((item["status"], item["current_step_key"]), ("waiting_submission", "implement"))
        self.assertEqual(len(self.provider.requests), 1)
        item = run_action(self.service, item, "hint")
        self.assertEqual(item["status"], "waiting_submission")
        self.assertEqual(set(item["outputs"]), {"understand", "implement"})
        item = run_action(self.service, item, "cancel")
        self.assertEqual(item["status"], "cancelled")
        item = run_action(self.service, item, "resume")
        self.assertEqual((item["status"], item["current_step_key"]), ("waiting_submission", "implement"))

        # 新Service对象复用同一持久对象集合，证明状态不依赖Service实例缓存。
        fresh, _, _ = build_service(MemoryPracticeRepository(self.repo.state), self.provider)
        loaded = fresh.get(1, item["id"])
        self.assertEqual((loaded["revision"], loaded["outputs"]), (item["revision"], item["outputs"]))
        self.assertEqual(len(fresh.list(1, 7)), 1)
        self.assertEqual(len(self.provider.requests), 2)
        self.assertFalse(self.repo.in_transaction)

    def test_replays_are_stable_and_different_payload_or_version_conflicts(self):
        creation_key = str(uuid4())
        item = create_session(self.service, request_key=creation_key)
        replayed = create_session(self.service, request_key=creation_key)
        self.assertEqual(replayed["id"], item["id"])
        self.assertTrue(replayed["replayed"])
        with self.assertRaises(ConflictError):
            self.service.create(1, 7, "python-learning-csv", "1.0", 2, creation_key)
        self.assertEqual(len(self.repo.state.sessions), 1)

        action_key = str(uuid4())
        before = deepcopy(item)
        item = run_action(self.service, item, "start", request_key=action_key)
        replayed = run_action(self.service, before, "start", request_key=action_key)
        self.assertTrue(replayed["replayed"])
        self.assertEqual(replayed["active_ai_request_id"], item["active_ai_request_id"])
        self.assertEqual(replayed["action_result"]["event_key"], action_key + ":action")
        with self.assertRaises(ConflictError):
            run_action(self.service, item, "hint", request_key=action_key)
        with self.assertRaises(ConflictError):
            run_action(self.service, before, "cancel")
        self.assertEqual(len(self.provider.requests), 1)
        self.assertEqual(len(self.repo.state.events), 2)
        self.assertEqual(self.service.get(1, item["id"])["revision"], item["revision"])

    def test_ownership_and_missing_material_never_call_model(self):
        item = create_session(self.service)
        def submit(owner):
            return self.service.submit_attempt(owner, item["id"], 1, "implement", str(uuid4()),
                "def summarize_records(csv_text):\n    pass\n", {}, None)
        for operation in (
            lambda: self.service.get(2, item["id"]),
            lambda: self.service.list(2, 7),
            lambda: submit(2),
            lambda: run_action(self.service, item, "start", owner_id=2),
        ):
            with self.assertRaises(ResourceNotFoundError):
                operation()
        with self.assertRaises(ConflictError):
            submit(1)
        with self.assertRaises(HTTPException) as raised:
            run_action(self.service, item, "review")
        self.assertEqual(raised.exception.status_code, 422)
        with self.assertRaises(ResourceNotFoundError):
            run_action(self.service, item, "start", attempt_id=str(uuid4()))
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(len(self.repo.state.events), 1)
        self.assertEqual(self.service.get(1, item["id"])["status"], "ready")

    def test_provider_wait_has_no_transaction_concurrent_start_conflicts_and_cancel_detaches_result(self):
        item = create_session(self.service)

        async def scenario():
            self.provider.started = asyncio.Event()
            self.provider.release = asyncio.Event()
            key = str(uuid4())
            pending = asyncio.create_task(self.service.action(1, item["id"], "start", 1, key))
            await asyncio.wait_for(self.provider.started.wait(), 1)
            self.assertFalse(self.repo.in_transaction)
            running = self.service.get(1, item["id"])
            self.assertEqual((running["status"], running["revision"]), ("running", 2))
            replay = await self.service.action(1, item["id"], "start", 1, key)
            self.assertTrue(replay["replayed"])
            self.assertEqual(replay["active_operation_id"], running["active_operation_id"])
            with self.assertRaises(ConflictError):
                await self.service.action(1, item["id"], "start", running["revision"], str(uuid4()))
            cancelled = await self.service.action(1, item["id"], "cancel", running["revision"], str(uuid4()))
            self.assertEqual(cancelled["status"], "cancelled")
            self.provider.release.set()
            returned = await asyncio.wait_for(pending, 1)
            self.assertTrue(returned["detached"])
            self.assertEqual(returned["status"], "cancelled")
            self.assertEqual(returned["outputs"], {})
            self.assertEqual(returned["model_request"]["status"], "failed")
            self.assertEqual(returned["model_request"]["error_code"], "cancelled")
            saved = self.repo.state.requests[returned["active_ai_request_id"]]
            self.assertTrue(saved.request_metadata["late_response"])
            self.assertEqual(saved.prompt_tokens, 10)
            self.assertEqual(returned["revision"], cancelled["revision"])
            resumed = await self.service.action(1, item["id"], "resume", returned["revision"], str(uuid4()))
            self.assertEqual(resumed["status"], "ready")

        asyncio.run(scenario())
        self.assertEqual(len(self.provider.requests), 1)
        self.assertEqual(len(self.repo.state.requests), 1)
        self.assertEqual(len(self.repo.state.events), 4)

    def test_provider_failure_is_saved_and_only_explicit_continue_retries(self):
        self.provider.outcomes = [AIClientError("private upstream failure", category=AIFailureCategory.UPSTREAM, retryable=True)]
        item = create_session(self.service)
        with self.assertRaises(AIUpstreamError):
            run_action(self.service, item, "start")
        failed = self.service.get(1, item["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["model_request"]["error_code"], "upstream")
        self.assertNotIn("private upstream failure", json.dumps(failed, default=str))
        self.assertEqual(len(self.provider.requests), 1)
        self.service.list(1, 7)
        resumed = run_action(self.service, failed, "resume")
        self.assertEqual(resumed["status"], "failed")
        self.assertEqual(len(self.provider.requests), 1)
        with self.assertRaises(ConflictError):
            run_action(self.service, resumed, "hint")
        result = run_action(self.service, resumed, "continue")
        self.assertEqual(result["status"], "waiting_confirmation")
        self.assertEqual(len(self.provider.requests), 2)
        self.assertEqual(len(self.repo.state.requests), 2)
        first = self.repo.state.requests[failed["active_ai_request_id"]]
        self.assertEqual(first.status, AIRequestStatus.FAILED)
        self.assertEqual(first.request_metadata["max_retries"], 0)

    def test_residual_running_recovery_waits_for_deadline_and_late_result_cannot_overwrite(self):
        item = create_session(self.service)

        async def scenario():
            self.provider.started = asyncio.Event()
            self.provider.release = asyncio.Event()
            pending = asyncio.create_task(self.service.action(1, item["id"], "start", 1, str(uuid4())))
            await asyncio.wait_for(self.provider.started.wait(), 1)
            running = self.service.get(1, item["id"])
            fresh, _, _ = build_service(MemoryPracticeRepository(self.repo.state), self.provider)
            with self.assertRaises(ConflictError):
                await fresh.action(1, item["id"], "resume", running["revision"], str(uuid4()))
            saved_request = self.repo.state.requests[running["active_ai_request_id"]]
            saved_request.request_metadata = {
                **saved_request.request_metadata,
                "recover_after": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            }
            recovered = await fresh.action(1, item["id"], "resume", running["revision"], str(uuid4()))
            self.assertEqual(recovered["status"], "failed")
            self.assertEqual(recovered["model_request"]["error_code"], "recovery_timeout")
            self.assertEqual(len(self.provider.requests), 1)
            self.provider.release.set()
            late = await asyncio.wait_for(pending, 1)
            self.assertTrue(late["detached"])
            self.assertEqual(late["status"], "failed")
            self.assertEqual(late["model_request"]["status"], "failed")
            self.assertEqual(late["outputs"], {})

        asyncio.run(scenario())
        self.assertEqual(len(self.provider.requests), 1)

    def test_task_interruption_saves_failed_operation_without_repeating_provider(self):
        item = create_session(self.service)

        async def scenario():
            self.provider.started = asyncio.Event()
            self.provider.release = asyncio.Event()
            pending = asyncio.create_task(self.service.action(1, item["id"], "start", 1, str(uuid4())))
            await asyncio.wait_for(self.provider.started.wait(), 1)
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending

        asyncio.run(scenario())
        failed = self.service.get(1, item["id"])
        self.assertEqual((failed["status"], failed["model_request"]["error_code"]), ("failed", "interrupted"))
        self.assertEqual(len(self.provider.requests), 1)

    def test_snapshot_remains_bound_after_source_context_changes(self):
        item = create_session(self.service)
        saved_snapshot = deepcopy(item["context_snapshot"])
        self.assertEqual(set(saved_snapshot["values"]), PRACTICE_CONTEXT_FIELDS)
        project = self.repo.state.projects[7]
        changed = deepcopy(project.context_data)
        changed["version"] = 2
        changed["values"]["project_name"] = "later-project-name"
        for metadata in changed["field_metadata"].values():
            metadata["version"] = 2
        project.context_data = changed
        project.name = "later-project-name"

        result = run_action(self.service, item, "start")
        self.assertEqual(result["context_version"], 1)
        self.assertEqual(result["context_snapshot"], saved_snapshot)
        sent = self.provider.requests[0].messages[1].content
        self.assertIn("CSV 学习项目", sent)
        self.assertNotIn("later-project-name", sent)
        self.assertNotIn("excluded-", sent)

    def test_events_are_whitelisted_and_rollback_does_not_leave_success_event(self):
        item = create_session(self.service)
        item = run_action(self.service, item, "start")
        item = run_action(self.service, item, "confirm")
        self.assertEqual(self.repo.lock_history[0], ("project", 7))
        confirmed = [event for event in self.repo.state.events.values() if event.event_type == "step_confirmed"]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0].confirmation_kind, "understanding")
        self.assertEqual(confirmed[0].action_payload["step_key"], "understand")
        allowed = {"request", "template_id", "template_version", "step_key", "context_version", "revision", "operation_id", "ai_request_id", "status"}
        for event in self.repo.state.events.values():
            self.assertEqual(set(event.action_payload), allowed)
            self.assertIsNone(event.attempt_id)
            for forbidden in ("code", "feedback", "prompt", "student_code", "private upstream"):
                self.assertNotIn(forbidden, json.dumps(event.action_payload))
        before_events = set(self.repo.state.events)
        self.repo.fail_next_flush = True
        with self.assertRaisesRegex(RuntimeError, "injected-local-flush-failure"):
            run_action(self.service, item, "cancel")
        after = self.service.get(1, item["id"])
        self.assertEqual((after["status"], after["revision"]), (item["status"], item["revision"]))
        self.assertEqual(set(self.repo.state.events), before_events)
        self.assertGreaterEqual(self.repo.rollbacks, 1)
        self.assertEqual(len(self.provider.requests), 1)

    def test_reservation_rollback_prevents_provider_call_and_request_event(self):
        item = create_session(self.service)
        self.repo.fail_next_flush = True
        with self.assertRaises(RuntimeError):
            run_action(self.service, item, "start")
        after = self.service.get(1, item["id"])
        self.assertEqual((after["status"], after["revision"]), ("ready", 1))
        self.assertEqual(self.repo.state.requests, {})
        self.assertEqual(len(self.repo.state.events), 1)
        self.assertEqual(self.provider.requests, [])

    def test_invalid_output_is_saved_as_failure_without_raw_reply(self):
        self.provider.outcomes = ["invalid-model-reply"]
        item = create_session(self.service)
        with self.assertRaises(AgentOutputError):
            run_action(self.service, item, "start")
        failed = self.service.get(1, item["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["model_request"]["error_code"], "agent_output_invalid")
        self.assertNotIn("invalid-model-reply", json.dumps(failed, default=str))
        self.assertEqual(len(self.provider.requests), 1)

    def test_outer_timeout_is_bounded_and_persisted_without_retry(self):
        service, _, provider = build_service(operation_timeout_seconds=0.01)
        item = create_session(service)

        async def scenario():
            provider.release = asyncio.Event()
            with self.assertRaises(AIUpstreamTimeoutError):
                await service.action(1, item["id"], "start", 1, str(uuid4()))

        asyncio.run(scenario())
        failed = service.get(1, item["id"])
        self.assertEqual((failed["status"], failed["model_request"]["error_code"]), ("failed", "total_timeout"))
        self.assertEqual(len(provider.requests), 1)


if __name__ == "__main__":
    unittest.main()
