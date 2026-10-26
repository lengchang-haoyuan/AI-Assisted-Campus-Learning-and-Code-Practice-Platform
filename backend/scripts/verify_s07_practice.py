"""S07专用隔离MySQL验收；默认仅预览，显式授权后保留本轮新增证据行。"""

import argparse
import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Any
from unittest.mock import patch
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Depends, HTTPException
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.database import create_database_engine
from app.ai.client import AIClient
from app.ai.provider import (
    AIClientError,
    AICompletionRequest,
    AIFailureCategory,
    AIProvider,
    AIProviderResult,
    AIUsage,
)
from app.core.exceptions import AppError
from app.practice.agent import PRACTICE_CONTEXT_FIELDS, PracticeGuidanceAgent
from app.repositories.practice import PracticeRepository
from app.services.practice import PracticeService

DATABASE_PATTERN = re.compile(r"scholarhub_l4_[a-z0-9_]+\Z")
ROW_LIMITS = {
    "practice_sessions": 20,
    "practice_attempts": 0,
    "practice_events": 120,
    "ai_requests": 16,
    "ai_results": 16,
}
PROTECTED_BATCHES = (
    "b96ea63e-419e-4293-b724-d1ce59bd85ba",
    "3217db64-1302-4722-a483-c3b1ad7b980f",
)
OWNER_ID = 3
OTHER_OWNER_ID = 4
PROJECT_ID = 1
CONTEXT_VERSION = 1
RUN_ID = "s07-20261021"
API_CREATE_KEY = str(uuid5(NAMESPACE_URL, RUN_ID + "-api-create"))
WRITE_PATTERN = re.compile(
    r"^\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+`?([a-zA-Z0-9_]+)`?\b",
    re.IGNORECASE,
)


class VerificationFailure(RuntimeError):
    """错误仅携带固定标识，不拼接SQL、Provider内容或配置。"""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise VerificationFailure(code)


def safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def validate_target_url(database: str):
    require(bool(DATABASE_PATTERN.fullmatch(database)), "invalid_database_name")
    configured = get_settings().database_url
    require(configured is not None, "database_unconfigured")
    url = make_url(configured)
    require(url.drivername == "mysql+pymysql", "unsupported_database_driver")
    require(url.host in {"127.0.0.1", "localhost"}, "nonlocal_database_rejected")
    require((url.port or 3306) == 3306, "unexpected_database_port")
    return url.set(database=database)


def existing_target_engine(database: str) -> Engine:
    """只检查既有库；不CREATE DATABASE，也不回退配置中的业务库。"""
    url = validate_target_url(database)
    inventory = create_engine(
        url.set(database="information_schema"),
        echo=False,
        connect_args={"connect_timeout": 5, "read_timeout": 10, "write_timeout": 10},
    )
    try:
        with inventory.connect() as connection:
            exists = connection.scalar(
                text("SELECT COUNT(*) FROM SCHEMATA WHERE SCHEMA_NAME = :database"),
                {"database": database},
            )
            require(exists == 1, "isolated_database_missing")
    finally:
        inventory.dispose()
    engine = create_database_engine(url.render_as_string(hide_password=False))
    with engine.connect() as connection:
        require(connection.scalar(text("SELECT DATABASE()")) == database, "target_mismatch")
    return engine


def table_names(connection) -> list[str]:
    return list(
        connection.scalars(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_NAME"
            )
        )
    )


def count_rows(connection, table: str) -> int:
    require(bool(re.fullmatch(r"[a-zA-Z0-9_]+", table)), "unsafe_table_identifier")
    return int(connection.scalar(text(f"SELECT COUNT(*) FROM `{table}`")) or 0)


def run_ledger(connection) -> dict[str, Any]:
    """固定tag跨次定位已有证据；出现已有记录时不盲目再次付诸写入。"""
    session_ids = list(
        connection.scalars(
            text("SELECT DISTINCT session_id FROM practice_events WHERE event_key LIKE :prefix OR event_key = :api_create ORDER BY session_id"),
            {"prefix": RUN_ID + "-%", "api_create": API_CREATE_KEY + ":create"},
        )
    )
    counts = dict.fromkeys(ROW_LIMITS, 0)
    requests = []
    sessions = []
    for session_id in session_ids:
        row = connection.execute(
            text("SELECT id, status, revision, current_step_key, context_version FROM practice_sessions WHERE id = :id"),
            {"id": session_id},
        ).mappings().one()
        sessions.append(dict(row))
        counts["practice_sessions"] += 1
        for table in ("practice_attempts", "practice_events"):
            counts[table] += int(connection.scalar(
                text(f"SELECT COUNT(*) FROM `{table}` WHERE session_id = :id"), {"id": session_id}
            ) or 0)
        request_rows = list(connection.execute(
            text("SELECT id, status, error_code FROM ai_requests WHERE JSON_UNQUOTE(JSON_EXTRACT(request_metadata, '$.session_id')) = :id ORDER BY id"),
            {"id": session_id},
        ).mappings())
        counts["ai_requests"] += len(request_rows)
        for request in request_rows:
            requests.append(dict(request))
            counts["ai_results"] += int(connection.scalar(
                text("SELECT COUNT(*) FROM ai_results WHERE request_id = :id"), {"id": request["id"]}
            ) or 0)
    return {"run_id": RUN_ID, "counts": counts, "sessions": sessions, "requests": requests}


def snapshot(engine: Engine) -> dict[str, Any]:
    """仅导出行数、版本与冻结批次数字，不读取正文或凭证。"""
    with engine.connect() as connection:
        tables = table_names(connection)
        require(set(ROW_LIMITS).issubset(tables), "practice_schema_not_migrated")
        counts = {table: count_rows(connection, table) for table in tables}
        projects = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT id, owner_id, (context_data IS NOT NULL) AS has_context, "
                    "JSON_UNQUOTE(JSON_EXTRACT(context_data, '$.version')) AS context_version "
                    "FROM projects WHERE id = :project_id"
                ),
                {"project_id": PROJECT_ID},
            ).mappings()
        ]
        require(len(projects) == 1, "verification_project_missing")
        project = projects[0]
        require(project["owner_id"] == OWNER_ID, "verification_project_owner_mismatch")
        require(bool(project["has_context"]), "verification_context_missing")
        require(str(project["context_version"]) == str(CONTEXT_VERSION), "verification_context_version_mismatch")
        user_ids = set(
            connection.scalars(
                text("SELECT id FROM users WHERE id IN (:owner, :other)"),
                {"owner": OWNER_ID, "other": OTHER_OWNER_ID},
            )
        )
        require(user_ids == {OWNER_ID, OTHER_OWNER_ID}, "verification_owners_missing")
        batch_parameters = {"main": PROTECTED_BATCHES[0], "boundary": PROTECTED_BATCHES[1]}
        batches = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT batch_id, owner_user_id, state, period_start, period_end, source_cutoff "
                    "FROM analytics_batches WHERE batch_id IN (:main, :boundary) ORDER BY batch_id"
                ),
                batch_parameters,
            ).mappings()
        ]
        require(len(batches) == 2, "protected_batch_missing")
        require(all(row["state"] == "completed" for row in batches), "protected_batch_not_completed")
        metrics = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT batch_id, metric_date, records, known_minutes, known_duration_count, "
                    "missing_duration_count, task_total, completed, overdue_unfinished, "
                    "cohort_count, confirmed_count FROM analytics_daily_metrics "
                    "WHERE batch_id IN (:main, :boundary) ORDER BY batch_id, metric_date"
                ),
                batch_parameters,
            ).mappings()
        ]
        ledger = run_ledger(connection)
    return {"tables": tables, "row_counts": counts, "project": project, "batches": batches, "metrics": metrics, "run_ledger": ledger}


def install_write_guard(engine: Engine, baseline: dict[str, Any]) -> Callable[[], None]:
    """防止脚本和被测服务越过本轮表范围与行数预算。"""
    def guard(connection, cursor, statement, parameters, context, executemany):
        del cursor, context
        normalized = statement.lstrip().upper()
        if normalized.startswith(("SELECT ", "SHOW ", "SET ")):
            return
        match = WRITE_PATTERN.match(statement)
        require(match is not None, "non_dml_statement_rejected")
        verb, table = match.group(1).upper(), match.group(2)
        require(not verb.startswith("DELETE"), "cleanup_or_delete_rejected")
        require(table in ROW_LIMITS and ROW_LIMITS[table] > 0, "write_outside_authorized_tables")
        if not verb.startswith("INSERT"):
            return
        # 独立DBAPI游标看见当前事务未提交行；不递归触发执行钩子。
        budget_cursor = connection.connection.cursor()
        try:
            budget_cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            current = int(budget_cursor.fetchone()[0])
        finally:
            budget_cursor.close()
        rows = len(parameters) if executemany else 1
        require(
            baseline["run_ledger"]["counts"][table] + current - baseline["row_counts"][table] + rows <= ROW_LIMITS[table],
            "write_budget_exhausted",
        )

    event.listen(engine, "before_cursor_execute", guard)
    return lambda: event.remove(engine, "before_cursor_execute", guard)


def verify_preserved(baseline: dict[str, Any], final: dict[str, Any]) -> dict[str, int]:
    require(baseline["tables"] == final["tables"], "table_set_changed")
    for field in ("project", "batches", "metrics"):
        require(baseline[field] == final[field], f"protected_{field}_changed")
    deltas = {}
    for table, previous in baseline["row_counts"].items():
        delta = final["row_counts"][table] - previous
        if table in ROW_LIMITS:
            require(0 <= delta <= ROW_LIMITS[table], "write_budget_or_deletion_violation")
            deltas[table] = delta
        else:
            require(delta == 0, "protected_table_count_changed")
    return deltas


class FakeGuidanceProvider(AIProvider):
    """经过真实AIClient/Agent校验；只返回固定内存响应，不含网络实现。"""

    def __init__(self) -> None:
        self.calls = 0
        self.failures_remaining = 0
        self.entered: asyncio.Event | None = None
        self.release: asyncio.Event | None = None
        self.check_no_transaction: Callable[[], bool] | None = None
        self._counter_lock = threading.Lock()

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request: AICompletionRequest) -> AIProviderResult:
        with self._counter_lock:
            self.calls += 1
            require(self.calls <= ROW_LIMITS["ai_requests"], "fake_call_budget_exhausted")
            should_fail = self.failures_remaining > 0
            if should_fail:
                self.failures_remaining -= 1
        if self.check_no_transaction is not None:
            require(self.check_no_transaction(), "database_transaction_during_provider_wait")
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            await self.release.wait()
        if should_fail:
            raise AIClientError("固定Fake上游失败", category=AIFailureCategory.UPSTREAM)
        return AIProviderResult(
            provider=self.name,
            model=request.model,
            content=json.dumps(
                {"summary": "先理解固定CSV规则，再自行实现。", "guidance": ["逐行区分有效值、未知时长和已知零。"], "checks": ["自行核对公开向量T01；这里没有执行学生代码。"]},
                ensure_ascii=False,
            ),
            finish_reason="stop",
            usage=AIUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )


def build_service(session: Session, provider: FakeGuidanceProvider) -> PracticeService:
    client = AIClient(
        provider,
        total_timeout_seconds=30,
        max_retries=0,
        retry_base_delay_seconds=0,
        max_retry_delay_seconds=0,
    )
    agent = PracticeGuidanceAgent(client, model="fake-model", max_tokens=1000, temperature=0)
    return PracticeService(
        PracticeRepository(session), agent, provider_name="fake", model="fake-model",
        operation_timeout_seconds=30,
    )


def create_case(service: PracticeService, key: str) -> dict[str, Any]:
    return service.create(OWNER_ID, PROJECT_ID, "python-learning-csv", "1.0", CONTEXT_VERSION, key)


def expect_sync_status(callback: Callable[[], object], status_code: int, code: str) -> None:
    try:
        callback()
    except (AppError, HTTPException) as exc:
        require(exc.status_code == status_code, code)
    else:
        raise VerificationFailure(code)


async def expect_status(callback, status_code: int, code: str) -> None:
    try:
        await callback()
    except (AppError, HTTPException) as exc:
        require(exc.status_code == status_code, code)
    else:
        raise VerificationFailure(code)


def state_brief(item: dict[str, Any]) -> dict[str, Any]:
    return {field: item[field] for field in ("id", "status", "revision", "current_step_key", "context_version")}


def count_case_events(factory: sessionmaker[Session], session_id: str) -> int:
    with factory() as session:
        return int(session.scalar(text("SELECT COUNT(*) FROM practice_events WHERE session_id = :id"), {"id": session_id}) or 0)


async def lifecycle_case(factory: sessionmaker[Session], key: str, provider: FakeGuidanceProvider) -> dict[str, Any]:
    calls_before = provider.calls
    with factory() as session:
        service = build_service(session, provider)
        item = create_case(service, key)
        session_id = item["id"]
        replay = create_case(service, key)
        require(replay["id"] == session_id and replay["replayed"], "duplicate_create_not_replayed")
        require(count_case_events(factory, session_id) == 1, "duplicate_create_amplified_event")
        provider.check_no_transaction = lambda: not session.in_transaction()
        item = await service.action(OWNER_ID, session_id, "start", item["revision"], key + "-start")
        provider.check_no_transaction = None
        require(item["status"] == "waiting_confirmation", "understand_not_waiting_confirmation")
        require(item["revision"] == 3, "start_revision_not_persisted")
        calls_after_start = provider.calls
        events_after_start = count_case_events(factory, session_id)
        replay = await service.action(OWNER_ID, session_id, "start", 1, key + "-start")
        require(replay["replayed"] and replay["revision"] == item["revision"], "start_replay_changed_revision")
        await expect_status(lambda: service.action(OWNER_ID, session_id, "hint", 1, key + "-stale"), 409, "wrong_revision_not_conflict")
        expect_sync_status(lambda: service.get(OTHER_OWNER_ID, session_id), 404, "cross_owner_get_not_hidden")
        await expect_status(lambda: service.action(OTHER_OWNER_ID, session_id, "cancel", item["revision"], key + "-other"), 404, "cross_owner_action_not_hidden")
        expect_sync_status(lambda: service.reject_attempt(OWNER_ID, session_id), 422, "s08_attempt_not_rejected")
        await expect_status(lambda: service.action(OWNER_ID, session_id, "review", item["revision"], key + "-review"), 422, "s08_review_not_rejected")
        require(provider.calls == calls_after_start, "query_or_replay_called_provider")
        require(count_case_events(factory, session_id) == events_after_start, "rejected_action_amplified_event")
        item = await service.action(OWNER_ID, session_id, "confirm", item["revision"], key + "-confirm")
        require(item["status"] == "waiting_submission" and item["current_step_key"] == "implement", "confirm_not_waiting_submission")
        item = await service.action(OWNER_ID, session_id, "resume", item["revision"], key + "-resume-waiting")
        item = await service.action(OWNER_ID, session_id, "cancel", item["revision"], key + "-cancel")
        cancelled_revision = item["revision"]
        replay = await service.action(OWNER_ID, session_id, "cancel", cancelled_revision - 1, key + "-cancel")
        require(replay["replayed"] and replay["revision"] == cancelled_revision, "cancel_replay_changed_state")
        item = await service.action(OWNER_ID, session_id, "resume", item["revision"], key + "-resume-cancelled")
        require(item["status"] == "waiting_submission", "cancel_resume_lost_safe_wait")
        require(provider.calls == calls_after_start, "local_action_called_provider")
        item = await service.action(OWNER_ID, session_id, "hint", item["revision"], key + "-hint")
        require(item["status"] == "waiting_submission", "implement_hint_not_waiting_submission")
        expected = state_brief(item)
    with factory() as restarted_session:
        rebuilt = build_service(restarted_session, provider)
        restored = rebuilt.get(OWNER_ID, session_id)
        require(state_brief(restored) == expected, "fresh_service_session_restore_mismatch")
        require(set(restored["outputs"]) == {"understand", "implement"}, "restored_outputs_missing")
        require(set(restored["context_snapshot"]["values"]).issubset(PRACTICE_CONTEXT_FIELDS), "snapshot_context_whitelist_broken")
    return {"state": expected, "fresh_service_and_sql_session": "passed", "fake_calls": provider.calls - calls_before}


async def cancelled_late_case(factory: sessionmaker[Session], key: str, provider: FakeGuidanceProvider) -> dict[str, Any]:
    provider.entered, provider.release = asyncio.Event(), asyncio.Event()
    with factory() as calling_session, factory() as control_session:
        caller = build_service(calling_session, provider)
        controller = build_service(control_session, provider)
        item = create_case(caller, key)
        session_id = item["id"]
        provider.check_no_transaction = lambda: not calling_session.in_transaction()
        task = asyncio.create_task(caller.action(OWNER_ID, session_id, "start", 1, key + "-start"))
        try:
            await asyncio.wait_for(provider.entered.wait(), timeout=10)
            running = controller.get(OWNER_ID, session_id)
            require(running["status"] == "running", "running_not_committed_before_provider")
            calls = provider.calls
            replay = await controller.action(OWNER_ID, session_id, "start", 1, key + "-start")
            require(replay["replayed"] and replay["status"] == "running", "inflight_duplicate_not_replayed")
            await expect_status(lambda: controller.action(OWNER_ID, session_id, "start", running["revision"], key + "-competing"), 409, "competing_start_not_conflict")
            cancelled = await controller.action(OWNER_ID, session_id, "cancel", running["revision"], key + "-cancel")
            require(provider.calls == calls, "cancel_called_provider")
        finally:
            provider.release.set()
            late = await task
            provider.entered, provider.release, provider.check_no_transaction = None, None, None
        require(late["detached"] and late["status"] == "cancelled", "late_result_overwrote_cancel")
        require(late["revision"] == cancelled["revision"] and not late["outputs"], "late_result_changed_cancelled_wait")
        return {"state": state_brief(late), "late_result_detached": True}


async def concurrent_start_case(factory: sessionmaker[Session], key: str, provider: FakeGuidanceProvider) -> dict[str, Any]:
    with factory() as session:
        item = create_case(build_service(session, provider), key)
    before_calls = provider.calls
    barrier = threading.Barrier(2, timeout=10)

    def start_in_thread() -> dict[str, Any]:
        with factory() as session:
            service = build_service(session, provider)
            barrier.wait()
            return asyncio.run(service.action(OWNER_ID, item["id"], "start", 1, key + "-start"))

    results = await asyncio.gather(asyncio.to_thread(start_in_thread), asyncio.to_thread(start_in_thread))
    require(provider.calls - before_calls == 1, "concurrent_start_repeated_provider")
    require(sum(bool(result["replayed"]) for result in results) == 1, "concurrent_start_not_one_replay")
    require(count_case_events(factory, item["id"]) == 2, "concurrent_start_amplified_event")
    with factory() as session:
        restored = build_service(session, provider).get(OWNER_ID, item["id"])
    require(restored["status"] == "waiting_confirmation", "concurrent_start_final_state_wrong")
    return {"state": state_brief(restored), "provider_calls": 1, "start_events": 1}


async def failed_continue_case(factory: sessionmaker[Session], key: str, provider: FakeGuidanceProvider) -> dict[str, Any]:
    with factory() as session:
        service = build_service(session, provider)
        item = create_case(service, key)
        provider.failures_remaining = 1
        await expect_status(lambda: service.action(OWNER_ID, item["id"], "start", 1, key + "-start"), 502, "fake_provider_failure_not_reported")
        failed = service.get(OWNER_ID, item["id"])
        require(failed["status"] == "failed" and failed["model_request"]["error_code"] == "upstream", "failure_not_persisted")
        calls = provider.calls
        replay = await service.action(OWNER_ID, item["id"], "start", 1, key + "-start")
        require(replay["replayed"] and replay["status"] == "failed", "failed_request_replay_not_stable")
        await expect_status(lambda: service.action(OWNER_ID, item["id"], "start", failed["revision"], key + "-wrong-retry"), 409, "failed_start_silently_retried")
        require(provider.calls == calls, "failed_query_or_replay_retried_provider")
        continued = await service.action(OWNER_ID, item["id"], "continue", failed["revision"], key + "-continue")
        require(continued["status"] == "waiting_confirmation", "explicit_continue_not_recovered")
        replay = await service.action(OWNER_ID, item["id"], "continue", failed["revision"], key + "-continue")
        require(replay["replayed"] and provider.calls == calls + 1, "continue_replay_repeated_provider")
        return {"state": state_brief(continued), "original_request_error": "upstream", "explicit_retry_calls": 1}


async def expired_running_case(factory: sessionmaker[Session], key: str, provider: FakeGuidanceProvider) -> dict[str, Any]:
    """推进时钟模拟预约租约已到期；不伪称执行了真实OS进程崩溃。"""
    provider.entered, provider.release = asyncio.Event(), asyncio.Event()
    with factory() as calling_session, factory() as restarted_session:
        caller = build_service(calling_session, provider)
        rebuilt = build_service(restarted_session, provider)
        item = create_case(caller, key)
        task = asyncio.create_task(caller.action(OWNER_ID, item["id"], "start", 1, key + "-start"))
        try:
            await asyncio.wait_for(provider.entered.wait(), timeout=10)
            running = rebuilt.get(OWNER_ID, item["id"])
            calls = provider.calls
            await expect_status(lambda: rebuilt.action(OWNER_ID, item["id"], "resume", running["revision"], key + "-early-resume"), 409, "active_lease_resumed_early")

            class ExpiredClock(datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime.now(tz) + timedelta(minutes=5)

            with patch("app.services.practice.datetime", ExpiredClock):
                failed = await rebuilt.action(OWNER_ID, item["id"], "resume", running["revision"], key + "-expired-resume")
            require(failed["status"] == "failed", "expired_running_not_failed")
            require(failed["model_request"]["error_code"] == "recovery_timeout", "recovery_error_not_persisted")
            require(provider.calls == calls, "resume_silently_called_provider")
        finally:
            provider.release.set()
            late = await task
            provider.entered, provider.release = None, None
        require(late["detached"] and late["status"] == "failed", "expired_operation_late_result_committed")
        require(late["model_request"]["error_code"] == "recovery_timeout", "late_result_overwrote_recovery_error")
        continued = await rebuilt.action(OWNER_ID, item["id"], "continue", failed["revision"], key + "-continue")
        require(continued["status"] == "waiting_confirmation", "expired_operation_continue_not_recovered")
    return {"state": state_brief(continued), "method": "fresh_service_session_and_simulated_expired_lease", "actual_os_process_restart": "not_run", "resume_provider_calls": 0}


def rollback_case(factory: sessionmaker[Session], key: str, provider: FakeGuidanceProvider) -> dict[str, Any]:
    engine = factory.kw["bind"]
    with engine.connect() as connection:
        before = {table: count_rows(connection, table) for table in ROW_LIMITS}

    def fail_event(connection, cursor, statement, parameters, context, executemany):
        del connection, cursor, parameters, context, executemany
        match = WRITE_PATTERN.match(statement)
        if match and match.group(1).upper().startswith("INSERT") and match.group(2) == "practice_events":
            raise VerificationFailure("injected_event_rollback")

    event.listen(engine, "before_cursor_execute", fail_event)
    try:
        with factory() as session:
            try:
                create_case(build_service(session, provider), key)
            except VerificationFailure as exc:
                require(str(exc) == "injected_event_rollback", "unexpected_rollback_failure")
            else:
                raise VerificationFailure("event_failure_not_injected")
    finally:
        event.remove(engine, "before_cursor_execute", fail_event)
    with engine.connect() as connection:
        after = {table: count_rows(connection, table) for table in ROW_LIMITS}
    require(before == after, "rolled_back_action_left_success_rows")
    with factory() as session:
        item = create_case(build_service(session, provider), key)
    require(count_case_events(factory, item["id"]) == 1, "rollback_recovery_event_count_wrong")
    return {"state": state_brief(item), "injected_failure": "event_insert", "rolled_back_row_deltas": {table: 0 for table in ROW_LIMITS}}


def verify_event_contract(factory: sessionmaker[Session], session_ids: list[str]) -> dict[str, Any]:
    from sqlalchemy import select
    from app.models.ai import AIRequest
    from app.models.practice import PracticeEvent

    allowed = {"request", "template_id", "template_version", "step_key", "context_version", "revision", "operation_id", "ai_request_id", "status"}
    allowed_request = {"template_id", "template_version", "expected_context_version", "action", "expected_revision", "attempt_id"}
    sample = None
    with factory() as session:
        events = list(session.scalars(select(PracticeEvent).where(PracticeEvent.session_id.in_(session_ids))))
        event_keys = set()
        for item in events:
            unique = (item.session_id, item.event_key)
            require(unique not in event_keys, "duplicate_event_key")
            event_keys.add(unique)
            payload = item.action_payload
            require(set(payload) <= allowed and set(payload["request"]) <= allowed_request, "event_payload_contains_unapproved_field")
            require(payload["template_id"] == "python-learning-csv" and payload["template_version"] == "1.0", "event_template_binding_wrong")
            require(payload["context_version"] == CONTEXT_VERSION and payload["revision"] >= 1, "event_version_binding_wrong")
            require(item.attempt_id is None, "s07_unexpected_attempt_event")
            if item.event_type == "session_started" and sample is None:
                sample = {"id": item.id, "session_id": item.session_id, "event_key": item.event_key, "event_type": item.event_type, "occurred_at": item.occurred_at, "action_payload": payload}
        requests = list(session.scalars(select(AIRequest).where(AIRequest.request_type == "practice_guidance")))
        requests = [item for item in requests if (item.request_metadata or {}).get("session_id") in session_ids]
        for item in requests:
            require(item.provider == "fake" and item.model == "fake-model", "unexpected_provider_or_model")
            require(item.user_id == OWNER_ID and item.project_id == PROJECT_ID and item.workflow_run_id is None, "request_identity_binding_wrong")
            require(item.request_metadata.get("max_retries") == 0, "request_retries_not_zero")
            require(item.status.value != "running", "verification_left_running_request")
    require(sample is not None, "start_event_sample_missing")
    return {"event_count": len(events), "request_count": len(requests), "start_event_sample": sample, "event_payload_contract": "passed"}


async def api_case(factory: sessionmaker[Session], provider: FakeGuidanceProvider) -> dict[str, Any]:
    """真实FastAPI/DTO/JWT/current_user/数据库，仅替换目标连接和模型Provider。"""
    import httpx
    from app.api.deps import get_db_session
    from app.api.practice_deps import get_practice_service
    from app.core.config import get_security_settings
    from app.core.security import SecurityService
    from app.main import create_app

    app = create_app()

    def database_override():
        with factory() as session:
            yield session

    async def service_override(session: Session = Depends(get_db_session)):
        yield build_service(session, provider)

    app.dependency_overrides[get_db_session] = database_override
    app.dependency_overrides[get_practice_service] = service_override
    security = SecurityService(get_security_settings())
    with factory() as session:
        versions = dict(session.execute(
            text("SELECT id, auth_version FROM users WHERE id IN (:owner, :other)"),
            {"owner": OWNER_ID, "other": OTHER_OWNER_ID},
        ).all())
    headers = {
        owner: {"Authorization": "Bearer " + security.create_access_token(owner, versions[owner] or 0).value}
        for owner in (OWNER_ID, OTHER_OWNER_ID)
    }
    codes = {}
    api_root = get_settings().api_v1_prefix

    async def checked(client, label: str, method: str, path: str, expected: int, **kwargs):
        response = await client.request(method, api_root + path, **kwargs)
        codes[label] = response.status_code
        require(response.status_code == expected, "api_" + label + "_status_mismatch")
        return response

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://s07.local") as client:
        create_path = f"/projects/{PROJECT_ID}/practice-sessions"
        await checked(client, "unauthenticated_list", "GET", create_path, 401)
        payload = {"template_id": "python-learning-csv", "template_version": "1.0", "expected_context_version": CONTEXT_VERSION, "request_key": API_CREATE_KEY}
        response = await checked(client, "create", "POST", create_path, 201, headers=headers[OWNER_ID], json=payload)
        item = response.json()
        session_path = "/practice-sessions/" + item["id"]
        await checked(client, "list", "GET", create_path, 200, headers=headers[OWNER_ID])
        await checked(client, "owner_get", "GET", session_path, 200, headers=headers[OWNER_ID])
        await checked(client, "cross_owner_get", "GET", session_path, 404, headers=headers[OTHER_OWNER_ID])
        action = {"action": "start", "expected_revision": item["revision"], "request_key": str(uuid5(NAMESPACE_URL, RUN_ID + "-api-start"))}
        response = await checked(client, "start", "POST", session_path + "/actions", 200, headers=headers[OWNER_ID], json=action)
        item = response.json()
        require(item["status"] == "waiting_confirmation", "api_start_not_waiting")
        before_calls = provider.calls
        await checked(client, "duplicate_start", "POST", session_path + "/actions", 200, headers=headers[OWNER_ID], json=action)
        invalid = {"action": "hint", "expected_revision": 1, "request_key": str(uuid5(NAMESPACE_URL, RUN_ID + "-api-stale"))}
        await checked(client, "wrong_revision", "POST", session_path + "/actions", 409, headers=headers[OWNER_ID], json=invalid)
        await checked(client, "unsupported_attempt", "POST", session_path + "/attempts", 422, headers=headers[OWNER_ID], json={})
        await checked(client, "invalid_action", "POST", session_path + "/actions", 422, headers=headers[OWNER_ID], json={**invalid, "action": "complete"})
        for action_name in ("confirm", "cancel", "resume"):
            action = {"action": action_name, "expected_revision": item["revision"], "request_key": str(uuid5(NAMESPACE_URL, RUN_ID + "-api-" + action_name))}
            response = await checked(client, action_name, "POST", session_path + "/actions", 200, headers=headers[OWNER_ID], json=action)
            item = response.json()
        await checked(client, "s06_main_list", "GET", "/offline-analytics/batches", 200, headers=headers[OWNER_ID])
        await checked(client, "s06_main_batch", "GET", "/offline-analytics/batches/" + PROTECTED_BATCHES[0], 200, headers=headers[OWNER_ID])
        await checked(client, "s06_boundary_batch", "GET", "/offline-analytics/batches/" + PROTECTED_BATCHES[1], 200, headers=headers[OTHER_OWNER_ID])
        await checked(client, "s06_cross_owner_batch", "GET", "/offline-analytics/batches/" + PROTECTED_BATCHES[0], 404, headers=headers[OTHER_OWNER_ID])
        require(provider.calls == before_calls, "api_get_local_action_or_replay_called_provider")
        require(item["status"] == "waiting_submission", "api_confirm_resume_state_wrong")
    app.dependency_overrides.clear()
    return {"state": state_brief(item), "status_codes": codes, "authentication": "real_JWT_and_current_user", "transport": "ASGI_in_process_no_TCP_or_browser"}


def independent_process_restore(database: str, expected: dict[str, Any]) -> dict[str, Any]:
    """新Python进程、新Engine、新Session查询安全等待点，参数中没有凭证。"""
    result = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-m", "scripts.verify_s07_practice", "--database", database, "--read-session", expected["id"]],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    require(result.returncode == 0, "independent_read_process_failed")
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise VerificationFailure("independent_read_process_invalid_json") from exc
    require(payload.get("status") == "passed", "independent_read_process_not_passed")
    require(payload.get("restored_state") == expected, "independent_read_process_state_mismatch")
    require(payload.get("fake_provider_calls") == 0, "independent_read_process_called_provider")
    return {"status": "passed", "restored_state": payload["restored_state"], "separate_python_process": True, "fake_provider_calls": 0, "http_server_process_restart": "not_run"}


def read_session_only(database: str, session_id: str) -> dict[str, Any]:
    require(str(UUID(session_id)) == session_id, "invalid_read_session_id")
    engine = existing_target_engine(database)

    def read_only(connection, cursor, statement, parameters, context, executemany):
        del connection, cursor, parameters, context, executemany
        require(statement.lstrip().upper().startswith(("SELECT ", "SHOW ", "SET ")), "read_only_child_write_rejected")

    event.listen(engine, "before_cursor_execute", read_only)
    provider = FakeGuidanceProvider()
    try:
        factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            item = build_service(session, provider).get(OWNER_ID, session_id)
        require(item["status"] in {"waiting_confirmation", "waiting_submission"}, "child_session_not_safe_wait")
        return {"status": "passed", "restored_state": state_brief(item), "fake_provider_calls": provider.calls}
    finally:
        event.remove(engine, "before_cursor_execute", read_only)
        engine.dispose()


async def run_cases(factory: sessionmaker[Session], run_id: str) -> dict[str, Any]:
    provider = FakeGuidanceProvider()
    cases = {}
    cases["lifecycle"] = await lifecycle_case(factory, run_id + "-lifecycle", provider)
    cases["cancelled_late"] = await cancelled_late_case(factory, run_id + "-cancel-late", provider)
    cases["concurrent_start"] = await concurrent_start_case(factory, run_id + "-concurrent", provider)
    cases["failed_continue"] = await failed_continue_case(factory, run_id + "-failure", provider)
    cases["expired_running"] = await expired_running_case(factory, run_id + "-expired", provider)
    cases["transaction_rollback"] = rollback_case(factory, run_id + "-rollback", provider)
    cases["api"] = await api_case(factory, provider)
    session_ids = [item["state"]["id"] for item in cases.values()]
    cases["events"] = verify_event_contract(factory, session_ids)
    cases["independent_process_restore"] = independent_process_restore(factory.kw["bind"].url.database, cases["lifecycle"]["state"])
    cases["created_session_ids"] = session_ids
    cases["fake_provider_calls"] = provider.calls
    require(provider.calls == 9, "unexpected_fake_provider_call_count")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--read-session")
    args = parser.parse_args()
    if not DATABASE_PATTERN.fullmatch(args.database):
        parser.error("仅允许scholarhub_l4_专用隔离库")
    if args.apply and args.confirm_database != args.database:
        parser.error("执行须通过--confirm-database重复确认同一目标")
    if args.read_session and args.apply:
        parser.error("--read-session仅支持只读子进程，不能与--apply合用")
    result: dict[str, Any] = {
        "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "database": args.database,
        "mode": "apply" if args.apply else "dry_run",
        "limits": ROW_LIMITS,
        "real_model_calls": 0,
        "cleanup": "retain_new_evidence_rows",
        "run_id": RUN_ID,
    }
    if args.read_session:
        result["mode"] = "read_only"
        try:
            result.update(read_session_only(args.database, args.read_session))
            print(safe_json(result))
            return 0
        except Exception as exc:
            result.update(status="failed", error_type=type(exc).__name__)
            if isinstance(exc, VerificationFailure):
                result["error_code"] = str(exc)
            print(safe_json(result))
            return 1
    if not args.apply:
        result["status"] = "not_run"
        result["detail"] = "no_connection_or_write"
        print(safe_json(result))
        return 0
    engine = None
    remove_guard = None
    baseline = None
    exit_code = 1
    try:
        engine = existing_target_engine(args.database)
        baseline = snapshot(engine)
        result["existing_run_ledger"] = baseline["run_ledger"]
        require(not any(baseline["run_ledger"]["counts"].values()), "previous_run_detected_read_only_resume_required")
        remove_guard = install_write_guard(engine, baseline)
        factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
        result["checks"] = asyncio.run(run_cases(factory, result["run_id"]))
        result["status"] = "passed"
        exit_code = 0
    except Exception as exc:
        result["status"] = "failed"
        result["error_type"] = type(exc).__name__
        if isinstance(exc, VerificationFailure):
            result["error_code"] = str(exc)
    finally:
        if engine is not None:
            if baseline is not None:
                try:
                    final = snapshot(engine)
                    result["cumulative_run_ledger"] = final["run_ledger"]
                    result["row_deltas"] = verify_preserved(baseline, final)
                    result["protected_baseline"] = {
                        "row_counts": baseline["row_counts"],
                        "batches": baseline["batches"],
                        "metrics": baseline["metrics"],
                    }
                    result["protected_baseline_unchanged"] = True
                except Exception as exc:
                    result["status"] = "failed"
                    result["preservation_error_type"] = type(exc).__name__
                    if isinstance(exc, VerificationFailure):
                        result["preservation_error_code"] = str(exc)
                    exit_code = 1
            if remove_guard is not None:
                remove_guard()
            engine.dispose()
    print(safe_json(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
