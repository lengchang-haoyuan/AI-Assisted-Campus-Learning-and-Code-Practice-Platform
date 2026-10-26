"""S08隔离MySQL/Fake验收；默认dryrun，不调用收费模型、不执行学生代码。"""

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
from unittest.mock import patch
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Depends, HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.ai.client import AIClient
from app.ai.provider import AIClientError, AIFailureCategory, AIProvider, AIProviderResult, AIUsage
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.practice.agent import PracticeGuidanceAgent
from app.practice.review import PracticeCodeGuidanceAgent, PracticeReviewAgent
from app.repositories.practice import PracticeRepository
from app.services.practice import PracticeService

DATABASE = "scholarhub_l4_s02_20261020"
RUN_ID = "s08-advisory-db-20261026"
OWNER_ID, OTHER_OWNER_ID, PROJECT_ID, CONTEXT_VERSION = 3, 4, 1, 1
ROW_LIMITS = {"practice_sessions": 14, "practice_attempts": 20, "practice_events": 180, "ai_requests": 28, "ai_results": 28}
INITIAL_COUNTS = {"practice_sessions": 15, "practice_attempts": 9, "practice_events": 88, "ai_requests": 27, "ai_results": 25}
LABELS = ("first", "revision", "late", "empty", "failure", "rollback", "api", "insufficient",
          "invalid", "advice-only", "concurrent", "timeout")
BATCHES = ("b96ea63e-419e-4293-b724-d1ce59bd85ba", "3217db64-1302-4722-a483-c3b1ad7b980f")
BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND.parent / "开发相关文档/阶段报告/AI大数据改造/V2/S01-AI固定模板与评价案例.json"
WRITE_PATTERN = re.compile(r"^\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+\x60?([a-zA-Z0-9_]+)\x60?\b", re.I)


class VerificationFailure(RuntimeError):
    """固定错误码，不输出SQL参数、凭证或正文。"""


def require(condition, code):
    if not condition:
        raise VerificationFailure(code)


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def key(label, action):
    return str(uuid5(NAMESPACE_URL, f"{RUN_ID}:{label}:{action}"))


def existing_target_engine(database):
    require(database == DATABASE, "unexpected_database")
    value = get_settings().database_url
    require(value is not None, "database_unconfigured")
    url = make_url(value)
    require(url.drivername == "mysql+pymysql", "unsupported_driver")
    require(url.host in {"127.0.0.1", "localhost"} and (url.port or 3306) == 3306, "nonlocal_target_rejected")
    options = {"echo": False, "connect_args": {"connect_timeout": 5, "read_timeout": 15, "write_timeout": 15}}
    inventory = create_engine(url.set(database="information_schema"), **options)
    try:
        with inventory.connect() as connection:
            require(connection.scalar(text("SELECT COUNT(*) FROM SCHEMATA WHERE SCHEMA_NAME=:database"), {"database": database}) == 1, "isolated_database_missing")
    finally:
        inventory.dispose()
    engine = create_engine(url.set(database=database), **options)
    @event.listens_for(engine, "connect")
    def utc_connection(dbapi_connection, connection_record):
        del connection_record
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")
    with engine.connect() as connection:
        require(connection.scalar(text("SELECT DATABASE()")) == database, "target_mismatch")
    return engine


def run_ledger(connection):
    keys = [key(label, "create") + ":create" for label in LABELS]
    placeholders = ",".join(f":k{i}" for i in range(len(keys)))
    sessions = [dict(row) for row in connection.execute(text(
        "SELECT s.id,s.status,s.revision,s.current_step_key,s.context_version FROM practice_sessions s "
        "JOIN practice_events e ON e.session_id=s.id WHERE e.event_type='session_created' "
        f"AND e.event_key IN ({placeholders}) ORDER BY s.id"
    ), {f"k{i}": value for i, value in enumerate(keys)}).mappings()]
    counts = dict.fromkeys(ROW_LIMITS, 0)
    counts["practice_sessions"] = len(sessions)
    for item in sessions:
        for table in ("practice_attempts", "practice_events"):
            counts[table] += int(connection.scalar(text(f"SELECT COUNT(*) FROM {table} WHERE session_id=:id"), {"id": item["id"]}) or 0)
        requests = list(connection.scalars(text("SELECT id FROM ai_requests WHERE JSON_UNQUOTE(JSON_EXTRACT(request_metadata,'$.session_id'))=:id"), {"id": item["id"]}))
        counts["ai_requests"] += len(requests)
        for request_id in requests:
            counts["ai_results"] += int(connection.scalar(text("SELECT COUNT(*) FROM ai_results WHERE request_id=:id"), {"id": request_id}) or 0)
    return {"run_id": RUN_ID, "counts": counts, "sessions": sessions}


def snapshot(engine):
    """全部旧行原值只留内存比较，报告不落旧正文。"""
    with engine.connect() as connection:
        names = list(connection.scalars(text("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")))
        rows = {}
        for name in names:
            require(bool(re.fullmatch(r"[a-z_]+", name)), "unsafe_table_name")
            columns = list(connection.scalars(text("SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION"), {"table": name}))
            require(bool(columns), "table_without_primary_key")
            rows[name] = {tuple(row[column] for column in columns): dict(row) for row in connection.execute(text(f"SELECT * FROM {name}")).mappings()}
        project = connection.execute(text("SELECT id,owner_id,JSON_UNQUOTE(JSON_EXTRACT(context_data,'$.version')) AS context_version FROM projects WHERE id=:project"), {"project": PROJECT_ID}).mappings().one()
        require(project["owner_id"] == OWNER_ID and str(project["context_version"]) == str(CONTEXT_VERSION), "fixture_context_changed")
        params = {"main": BATCHES[0], "boundary": BATCHES[1]}
        batches = [dict(row) for row in connection.execute(text("SELECT batch_id,owner_user_id,state,source_cutoff FROM analytics_batches WHERE batch_id IN (:main,:boundary) ORDER BY batch_id"), params).mappings()]
        metrics = [dict(row) for row in connection.execute(text("SELECT batch_id,metric_date,records,known_minutes,missing_duration_count,task_total,completed,overdue_unfinished,cohort_count,confirmed_count FROM analytics_daily_metrics WHERE batch_id IN (:main,:boundary) ORDER BY batch_id,metric_date"), params).mappings()]
        ledger = run_ledger(connection)
    return {"tables": names, "rows": rows, "row_counts": {name: len(value) for name, value in rows.items()}, "project": dict(project), "batches": batches, "metrics": metrics, "run_ledger": ledger}


def verify_initial(baseline):
    require(len(baseline["tables"]) == 39, "initial_table_count_changed")
    require({table: baseline["row_counts"][table] for table in ROW_LIMITS} == INITIAL_COUNTS, "initial_row_counts_changed")
    require(not baseline["run_ledger"]["sessions"], "existing_s08_tag_requires_inspection")
    require(len(baseline["batches"]) == 2 and all(row["state"] == "completed" for row in baseline["batches"]), "s06_batch_invalid")


def verify_preserved(baseline, final):
    require(baseline["tables"] == final["tables"], "table_set_changed")
    deltas = {}
    for table, before in baseline["rows"].items():
        after = final["rows"][table]
        require(all(identity in after and after[identity] == value for identity, value in before.items()), "old_row_changed_" + table)
        delta = len(after) - len(before)
        if table in ROW_LIMITS:
            require(0 <= delta <= ROW_LIMITS[table], "row_budget_exceeded")
            deltas[table] = delta
        else:
            require(delta == 0, "protected_table_changed_" + table)
    require(baseline["batches"] == final["batches"] and baseline["metrics"] == final["metrics"], "s06_batch_changed")
    require(deltas == final["run_ledger"]["counts"], "new_rows_outside_run_tag")
    return deltas


class WriteGuard:
    def __init__(self, engine, baseline):
        self.engine, self.baseline = engine, baseline
        self.new_ids = {table: set() for table in ROW_LIMITS}
        self.writes = []

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self.before)
        event.listen(self.engine, "after_cursor_execute", self.after)
        return self

    def __exit__(self, *args):
        event.remove(self.engine, "before_cursor_execute", self.before)
        event.remove(self.engine, "after_cursor_execute", self.after)

    def before(self, connection, cursor, statement, parameters, context, executemany):
        del cursor, parameters, executemany
        if statement.lstrip().upper().startswith(("SELECT ", "SHOW ", "SET ")):
            return
        match = WRITE_PATTERN.match(statement)
        require(match is not None, "ddl_or_unknown_write_rejected")
        verb, table = match.group(1).upper(), match.group(2)
        require(not verb.startswith("DELETE"), "delete_rejected")
        require(table in ROW_LIMITS, "write_table_rejected")
        self.writes.append({"verb": verb, "table": table})
        records = context.compiled_parameters or []
        require(bool(records), "unbound_write_rejected")
        if verb.startswith("INSERT"):
            budget = connection.connection.cursor()
            try:
                budget.execute(f"SELECT COUNT(*) FROM {table}")
                current = int(budget.fetchone()[0])
            finally:
                budget.close()
            require(current - self.baseline["row_counts"][table] + len(records) <= ROW_LIMITS[table], "insert_budget_exhausted")
            for row in records:
                if table == "practice_sessions":
                    require(row.get("owner_user_id") == OWNER_ID and row.get("project_id") == PROJECT_ID, "session_fixture_mismatch")
                elif table in {"practice_attempts", "practice_events"}:
                    require(row.get("session_id") in self.new_ids["practice_sessions"], "insert_into_old_session")
                elif table == "ai_requests":
                    metadata = row.get("request_metadata") or {}
                    metadata = json.loads(metadata) if isinstance(metadata, str) else metadata
                    require(metadata.get("session_id") in self.new_ids["practice_sessions"], "request_outside_run")
                    require(row.get("user_id") == OWNER_ID and row.get("project_id") == PROJECT_ID, "request_fixture_mismatch")
                else:
                    require(row.get("request_id") in self.new_ids["ai_requests"], "result_outside_run")
            return
        require(table in {"practice_sessions", "practice_attempts", "ai_requests"}, "immutable_row_update")
        where = re.search(r"\bWHERE\s+\x60?" + re.escape(table) + r"\x60?\.\x60?id\x60?\s*=\s*%\((\w+)\)s\s*$", statement, re.I)
        require(where is not None, "update_requires_single_pk")
        require(all(row.get(where.group(1)) in self.new_ids[table] for row in records), "old_row_update")
        setters = statement.split("WHERE", 1)[0].lower()
        if table == "practice_attempts":
            require(not any(re.search(r"\b" + column + r"\s*=", setters) for column in ("code_text", "declared_output", "self_statement", "request_key", "session_id", "attempt_no", "step_key")), "attempt_payload_update")

    def after(self, connection, cursor, statement, parameters, context, executemany):
        del connection, parameters, executemany
        match = WRITE_PATTERN.match(statement)
        if match is None or not match.group(1).upper().startswith("INSERT"):
            return
        table, records = match.group(2), context.compiled_parameters or []
        if table in {"practice_sessions", "practice_attempts", "practice_events"}:
            self.new_ids[table].update(row["id"] for row in records)
        elif table == "ai_requests":
            require(len(records) == 1, "request_batch_not_supported")
            self.new_ids[table].add(cursor.lastrowid)


def fixtures():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {"cases": {item["case_id"]: item for item in data["cases"]}, "declared": {item["test_id"]: deepcopy(item["expected"]) for item in data["fixed_output_vectors"] if item["test_id"] in {"T01", "T04"}}}


class FakePracticeProvider(AIProvider):
    """冻结标签仅用于工程Fake，不计入模型质量成绩。"""
    def __init__(self):
        self.calls = 0
        self.fail_next_review = self.block_next_review = self.invalid_next_review = False
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.sessions, self.fixture = [], fixtures()

    @property
    def name(self):
        return "fake"

    async def complete(self, request):
        self.calls += 1
        require(self.calls <= ROW_LIMITS["ai_requests"], "fake_call_budget_exhausted")
        require(all(not session.in_transaction() for session in self.sessions), "transaction_during_provider")
        review = request.response_schema_name == "practice_review_v1"
        if review and self.block_next_review:
            self.block_next_review = False
            self.entered.set()
            await self.release.wait()
        if review and self.fail_next_review:
            self.fail_next_review = False
            raise AIClientError("固定工程Fake失败", category=AIFailureCategory.UPSTREAM,
                                observed_usage=AIUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20))
        if review and self.invalid_next_review:
            self.invalid_next_review = False
            content = {"invalid_synthetic_advice": True}
        elif review:
            code = "".join(message.content.split("<STUDENT_CODE_PART>\n", 1)[1].rsplit("\n</STUDENT_CODE_PART>", 1)[0] for message in request.messages if "<STUDENT_CODE_PART>\n" in message.content)
            case = next((item for item in self.fixture["cases"].values() if (item.get("student_code") or "").strip() == code.strip()), None)
            require(case is not None, "fake_fixture_code_not_found")
            issues = {item["criterion_id"]: item["issue_type"] for item in case["reference_issues"]}
            quote = next((line for line in code.splitlines() if line.strip()), None)
            criteria = [{"criterion_id": cid, "verdict": verdict, "issue_type": issues.get(cid),
                "evidence_span": quote if verdict != "unknown" else None,
                "reason": "固定工程Fake按冻结标签返回，不代表模型质量。",
                "suggested_self_test": "本人核对公开边界；服务器未执行代码。" if verdict == "fail" else None,
                "next_action": "自行补齐材料或修改当前验收项。" if verdict != "pass" else None}
                for cid, verdict in case["reference_criteria"].items()]
            content = {"summary": "固定Fake反馈，仅验证状态编排。", "overall": case["reference_label"], "criteria": criteria}
        else:
            content = {"summary": "理解CSV规则后由本人实现。", "guidance": ["逐行区分未知时长与零。"], "checks": ["本人核对T01/T04；服务器未执行代码。"]}
        return AIProviderResult(provider="fake", model=request.model, content=json.dumps(content, ensure_ascii=False), finish_reason="stop", usage=AIUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20))


def build_service(session, provider):
    provider.sessions.append(session)
    client = AIClient(provider, total_timeout_seconds=30, max_retries=0, retry_base_delay_seconds=0, max_retry_delay_seconds=0)
    options = {"model": "fake-model", "max_tokens": 1500, "temperature": 0}
    return PracticeService(PracticeRepository(session), PracticeGuidanceAgent(client, **options),
        review_agent=PracticeReviewAgent(client, **options), code_guidance_agent=PracticeCodeGuidanceAgent(client, **options),
        provider_name="fake", model="fake-model", operation_timeout_seconds=30)


def brief(item):
    attempt = item.get("current_attempt")
    return {"id": item["id"], "status": item["status"], "revision": item["revision"],
        "current_step_key": item["current_step_key"], "context_version": item["context_version"],
        "current_attempt": None if not attempt else {"id": attempt["id"], "attempt_no": attempt["attempt_no"],
            "status": attempt["status"], "can_confirm": attempt["can_confirm"]},
        "attempt_count": len(item.get("attempts", []))}


async def expect_async(callback, status, code):
    try:
        await callback()
    except (AppError, HTTPException) as exc:
        require(exc.status_code == status, code)
    else:
        raise VerificationFailure(code)


async def act(service, item, label, action, *, attempt_id=None, suffix=None):
    return await service.action(OWNER_ID, item["id"], action, item["revision"], key(label, suffix or action), attempt_id=attempt_id)


async def create_ready(service, label):
    item = service.create(OWNER_ID, PROJECT_ID, "python-learning-csv", "1.0", CONTEXT_VERSION, key(label, "create"))
    item = await act(service, item, label, "start")
    require(item["status"] == "waiting_confirmation", "guidance_not_waiting")
    return await act(service, item, label, "confirm", suffix="understand-confirm")


def submit(service, item, label, number, case_id="Q01", *, declared_output=None, self_statement=True):
    data = fixtures()
    return service.submit_attempt(OWNER_ID, item["id"], item["revision"], "implement", key(label, f"submit-{number}"),
        data["cases"][case_id]["student_code"],
        deepcopy(data["declared"] if declared_output is None else declared_output), self_statement)


def attempt_id(item):
    return item["submission"]["attempt_id"] if item.get("submission") else item["current_attempt"]["id"]


def check_evidence(item, expected):
    evidence = item["current_attempt"]["feedback"]
    require(evidence["teacher_confirmation"] is None, "teacher_confirmation_fabricated")
    require(evidence["self_statement"]["value"] is True, "self_statement_not_separate")
    review = evidence["ai_static_review"]["review"]
    require(review["overall"] == expected and len(review["criteria"]) == 6, "review_result_wrong")
    require(evidence["submitted_output_match"]["matched"] and not evidence["submitted_output_match"]["code_executed"], "output_evidence_wrong")


async def first_case(factory, provider):
    with factory() as session:
        service = build_service(session, provider)
        item = await create_ready(service, "first")
        before = provider.calls
        item = submit(service, item, "first", 1, "Q05", declared_output={}, self_statement=False)
        require(provider.calls == before, "submission_called_provider")
        identity = attempt_id(item)
        require(item["status"] == "waiting_confirmation" and item["current_attempt"]["can_confirm"], "submission_not_waiting_person")
        before = provider.calls
        item = await act(service, item, "first", "confirm", attempt_id=identity, suffix="implement-confirm")
        require(item["status"] == "completed" and len(item["attempts"]) == 1, "direct_review_not_completed_once")
        require(provider.calls == before, "confirmation_called_provider")
        evidence = item["current_attempt"]["feedback"]
        require(evidence["ai_static_review"] is None and evidence["teacher_confirmation"] is None, "direct_review_fabricated_advice_or_teacher")
        require(evidence["self_statement"]["value"] is False and not evidence["submitted_output_match"]["matched"], "declaration_or_output_overwritten")
        require(evidence["personal_confirmation"]["ai_request_id"] is None and evidence["personal_confirmation"]["criteria"] == [], "direct_review_fabricated_advice_reference")
        require(not item["current_attempt"]["can_confirm"], "completed_still_confirmable")
        return {"state": brief(item), "attempts": 1, "advice_not_requested": True,
                "output_mismatch_retained": True, "personal_review_only": True}


async def revision_case(factory, provider):
    with factory() as session:
        service = build_service(session, provider)
        item = await create_ready(service, "revision")
        frozen = []
        immutable = ("id", "attempt_no", "code", "declared_output", "self_statement", "feedback", "review_schema_version", "ai_request_id", "operation_id", "created_at", "reviewed_at")
        for number, case_id in enumerate(("Q05", "Q09", "Q01"), 1):
            item = submit(service, item, "revision", number, case_id)
            identity = attempt_id(item)
            item = await act(service, item, "revision", "review", attempt_id=identity, suffix=f"review-{number}")
            check_evidence(item, "pass" if number == 3 else "needs_changes")
            require(item["status"] == "waiting_confirmation" and item["current_attempt"]["can_confirm"], "advice_forced_revision")
            for old, current in zip(frozen, item["attempts"]):
                require(all(old[field] == current[field] for field in immutable), "old_attempt_history_changed")
            frozen = deepcopy(item["attempts"])
        item = await act(service, item, "revision", "confirm", attempt_id=identity, suffix="implement-confirm")
        require(item["status"] == "completed" and len(item["attempts"]) == 3, "revision_history_or_completion_wrong")
        return {"state": brief(item), "append_only_attempt_history": "passed"}


async def late_case(factory, provider):
    with factory() as session:
        service = build_service(session, provider)
        item = await create_ready(service, "late")
        item = submit(service, item, "late", 1, "Q05")
        old_id = attempt_id(item)
        provider.entered.clear()
        provider.release.clear()
        provider.block_next_review = True
        pending = asyncio.create_task(act(service, item, "late", "review", attempt_id=old_id, suffix="blocked-review"))
        try:
            await asyncio.wait_for(provider.entered.wait(), timeout=10)
            with factory() as other:
                second = build_service(other, provider)
                current = second.get(OWNER_ID, item["id"])
                current = await act(second, current, "late", "cancel")
                current = await act(second, current, "late", "resume")
                current = submit(second, current, "late", 2, "Q01")
                newest_id = attempt_id(current)
                require(newest_id != old_id, "attempt_identity_reused")
            provider.release.set()
            detached = await asyncio.wait_for(pending, timeout=15)
            require(detached["detached"], "cancelled_review_not_detached")
            item = service.get(OWNER_ID, item["id"])
            require(item["current_attempt"]["id"] == newest_id, "late_review_changed_current_attempt")
            require(not item["current_attempt"]["feedback"].get("ai_static_review"), "late_review_bound_to_new_attempt")
            return {"state": brief(item), "old_attempt_id": old_id, "new_attempt_id": newest_id, "late_result_detached": True}
        finally:
            provider.release.set()
            if not pending.done():
                await asyncio.wait_for(pending, timeout=15)


async def empty_case(factory, provider):
    with factory() as session:
        service = build_service(session, provider)
        item = await create_ready(service, "empty")
        before = provider.calls
        for action in ("review", "explain", "confirm"):
            await expect_async(lambda action=action: act(service, item, "empty", action, suffix="missing-" + action), 409, "no_submission_" + action + "_not_rejected")
        require(provider.calls == before, "no_submission_called_provider")
        item = await act(service, item, "empty", "cancel")
        item = await act(service, item, "empty", "resume")
        require(item["status"] == "waiting_submission" and item["current_attempt"] is None, "empty_resume_invented_attempt")
        require(provider.calls == before, "empty_resume_called_provider")
        return {"state": brief(item), "rejections": {"review": 409, "explain": 409, "confirm": 409}, "provider_calls": 0}


async def failed_case(factory, provider, label="failure"):
    with factory() as session:
        service = build_service(session, provider)
        item = await create_ready(service, label)
        item = submit(service, item, label, 1)
        identity = attempt_id(item)
        provider.fail_next_review = label == "failure"
        provider.invalid_next_review = label == "invalid"
        try:
            await act(service, item, label, "review", attempt_id=identity)
        except (AppError, HTTPException):
            pass
        else:
            raise VerificationFailure("fake_failure_not_reported")
        item = service.get(OWNER_ID, item["id"])
        require(item["status"] == "failed", "review_failure_not_persisted")
        code = "upstream" if label == "failure" else "agent_output_invalid"
        require(item["model_request"]["error_code"] == code and item["model_request"]["prompt_tokens"] == 10
                and item["model_request"]["completion_tokens"] == 10, "failed_usage_or_error_lost")
        require(item["current_attempt"]["feedback"]["ai_static_review"] is None, "failed_advice_fabricated")
        before = provider.calls
        item = await act(service, item, label, "resume")
        require(item["status"] == "waiting_confirmation", "failed_resume_not_personal_wait")
        item = await act(service, item, label, "confirm", attempt_id=identity, suffix="implement-confirm")
        require(item["status"] == "completed" and provider.calls == before, "failed_advice_blocked_personal_end")
        require(item["model_request"]["error_code"] == code, "confirmation_overwrote_error")
        return {"state": brief(item), "error_code": code, "known_fake_usage": {"prompt_tokens": 10, "completion_tokens": 10},
                "recovery_and_confirmation_provider_calls": 0, "advice_fabricated": False}


async def rollback_case(factory, provider, engine):
    with factory() as session:
        service = build_service(session, provider)
        item = await create_ready(service, "rollback")
        before = brief(item)
        counts = snapshot(engine)["row_counts"]
        def fail_event(connection, cursor, statement, parameters, context, executemany):
            del connection, cursor, parameters, executemany
            if statement.lstrip().upper().startswith("INSERT INTO PRACTICE_EVENTS") and any(row.get("event_type") == "attempt_submitted" for row in context.compiled_parameters or []):
                raise VerificationFailure("injected_attempt_event_failure")
        event.listen(engine, "before_cursor_execute", fail_event)
        try:
            try:
                submit(service, item, "rollback", 1)
            except VerificationFailure as exc:
                require(str(exc) == "injected_attempt_event_failure", "unexpected_rollback_failure")
            else:
                raise VerificationFailure("event_failure_not_injected")
        finally:
            event.remove(engine, "before_cursor_execute", fail_event)
        require(brief(service.get(OWNER_ID, item["id"])) == before, "event_failure_changed_session")
        require(snapshot(engine)["row_counts"] == counts, "event_failure_left_partial_rows")
        item = submit(service, item, "rollback", 1)
        before_confirm = deepcopy(item["current_attempt"]["feedback"])
        counts = snapshot(engine)["row_counts"]
        def fail_confirm(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("INSERT INTO PRACTICE_EVENTS") and any(
                row.get("event_type") == "step_confirmed" and row.get("confirmation_kind") == "practice_owner"
                for row in context.compiled_parameters or []):
                raise VerificationFailure("injected_confirmation_event_failure")
        event.listen(engine, "before_cursor_execute", fail_confirm)
        try:
            try:
                await act(service, item, "rollback", "confirm", attempt_id=attempt_id(item), suffix="implement-confirm")
            except VerificationFailure as exc:
                require(str(exc) == "injected_confirmation_event_failure", "unexpected_confirmation_failure")
            else:
                raise VerificationFailure("confirmation_failure_not_injected")
        finally:
            event.remove(engine, "before_cursor_execute", fail_confirm)
        reloaded = service.get(OWNER_ID, item["id"])
        require(brief(reloaded) == brief(item) and reloaded["current_attempt"]["feedback"] == before_confirm,
                "confirmation_failure_left_evidence_or_state")
        require(snapshot(engine)["row_counts"] == counts, "confirmation_failure_left_events")
        item = await act(service, reloaded, "rollback", "confirm", attempt_id=attempt_id(reloaded), suffix="implement-confirm")
        require(item["status"] == "completed", "rollback_replay_cannot_complete")
        return {"state": brief(item), "injected_failures": ["attempt_submitted_event", "personal_confirmation_event"], "partial_rows": 0}


async def advice_only_case(factory, provider):
    with factory() as session:
        service = build_service(session, provider)
        item = submit(service, await create_ready(service, "advice-only"), "advice-only", 1, "Q05")
        item = await act(service, item, "advice-only", "review", attempt_id=attempt_id(item))
        check_evidence(item, "needs_changes")
        advice = deepcopy(item["current_attempt"]["feedback"]["ai_static_review"])
        before = provider.calls
        item = await act(service, item, "advice-only", "confirm", attempt_id=attempt_id(item), suffix="implement-confirm")
        require(item["status"] == "completed" and len(item["attempts"]) == 1, "needs_changes_forced_second_submission")
        require(item["current_attempt"]["feedback"]["ai_static_review"] == advice, "advice_relabelled_for_completion")
        require(provider.calls == before, "advice_confirmation_called_model")
        return {"state": brief(item), "needs_changes_retained": True, "second_attempt_required": False}


async def concurrent_case(factory, provider):
    with factory() as session:
        original = await create_ready(build_service(session, provider), "concurrent")
    def pair(action, item):
        barrier = threading.Barrier(2)
        def one(number):
            with factory() as session:
                connection_id = int(session.scalar(text("SELECT CONNECTION_ID()")))
                service = build_service(session, provider)
                barrier.wait(timeout=10)
                try:
                    result = (submit(service, item, "concurrent", number) if action == "submit" else
                        asyncio.run(act(service, item, "concurrent", "confirm", attempt_id=attempt_id(item), suffix=f"confirm-{number}")))
                    return {"connection_id": connection_id, "number": number, "status": 200, "item": result}
                except AppError as exc:
                    require(exc.status_code == 409, "concurrent_unexpected_error")
                    return {"connection_id": connection_id, "number": number, "status": 409}
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(one, number) for number in (1, 2)]
            results = [future.result(timeout=20) for future in futures]
        require(len({row["connection_id"] for row in results}) == 2, "concurrency_not_two_mysql_connections")
        require(sorted(row["status"] for row in results) == [200, 409], "concurrent_revision_not_serialized")
        return results
    before_calls = provider.calls
    submissions = pair("submit", original)
    winner = next(row for row in submissions if row["status"] == 200)
    submitted = winner["item"]
    with factory() as session:
        service = build_service(session, provider)
        replay = submit(service, original, "concurrent", winner["number"])
        require(replay["submission"]["replayed"] and len(replay["attempts"]) == 1, "concurrent_submission_replay_created_attempt")
    confirmations = pair("confirm", submitted)
    winner = next(row for row in confirmations if row["status"] == 200)
    with factory() as session:
        service = build_service(session, provider)
        replay = await service.action(OWNER_ID, submitted["id"], "confirm", submitted["revision"],
            key("concurrent", f"confirm-{winner['number']}"), attempt_id=attempt_id(submitted))
        require(replay["replayed"] and replay["status"] == "completed", "confirmation_replay_failed")
        event_count = session.scalar(text("SELECT COUNT(*) FROM practice_events WHERE session_id=:id AND event_type='session_completed'"), {"id": submitted["id"]})
        require(event_count == 1, "concurrent_completion_event_duplicated")
    require(provider.calls == before_calls, "concurrent_local_action_called_provider")
    clean = lambda rows: [{key: value for key, value in row.items() if key != "item"} for row in rows]
    return {"state": brief(winner["item"]), "submissions": clean(submissions), "confirmations": clean(confirmations),
            "session_completed_events": 1, "provider_calls": 0}


async def timeout_case(factory, provider):
    with factory() as session:
        service = build_service(session, provider)
        item = submit(service, await create_ready(service, "timeout"), "timeout", 1)
        identity = attempt_id(item)
        provider.entered.clear()
        provider.release.clear()
        provider.block_next_review = True
        pending = asyncio.create_task(act(service, item, "timeout", "review", attempt_id=identity, suffix="blocked-review"))
        try:
            await asyncio.wait_for(provider.entered.wait(), timeout=10)
            with factory() as second_session:
                second = build_service(second_session, provider)
                running = second.get(OWNER_ID, item["id"])
                await expect_async(lambda: act(second, running, "timeout", "resume", suffix="early-resume"), 409, "live_lease_resumed")
                await expect_async(lambda: act(second, running, "timeout", "confirm", attempt_id=identity, suffix="running-confirm"), 409, "running_confirmation_allowed")
                # 仅推进Service读取的时钟，不篡改库中租约；与实际HTTP进程重启证据分开。
                with patch("app.services.practice.datetime", wraps=datetime) as controlled_clock:
                    controlled_clock.now.return_value = datetime.now(timezone.utc) + timedelta(minutes=2)
                    recovered = await act(second, running, "timeout", "resume")
                require(recovered["status"] == "waiting_confirmation" and recovered["model_request"]["error_code"] == "recovery_timeout", "expired_review_not_safe_wait")
                completed = await act(second, recovered, "timeout", "confirm", attempt_id=identity, suffix="implement-confirm")
            provider.release.set()
            late = await asyncio.wait_for(pending, timeout=15)
            require(late["detached"] and late["revision"] == completed["revision"] and late["status"] == "completed", "late_timeout_changed_completion")
            require(late["current_attempt"]["feedback"]["ai_static_review"] is None, "late_timeout_bound_advice")
            require(late["model_request"]["error_code"] == "recovery_timeout", "late_timeout_overwrote_error")
            return {"state": brief(late), "safe_resume": True, "late_result_detached": True,
                    "lease_expiry": "controlled_service_clock_against_real_persisted_lease"}
        finally:
            provider.release.set()
            if not pending.done():
                await asyncio.wait_for(pending, timeout=15)


async def insufficient_case(factory, provider):
    with factory() as session:
        service = build_service(session, provider)
        item = await create_ready(service, "insufficient")
        item = submit(service, item, "insufficient", 1, "Q14")
        identity = attempt_id(item)
        item = await act(service, item, "insufficient", "review", attempt_id=identity)
        check_evidence(item, "insufficient")
        before = provider.calls
        item = await act(service, item, "insufficient", "confirm", attempt_id=identity, suffix="implement-confirm")
        require(item["status"] == "completed", "insufficient_advice_blocked_personal_end")
        require(provider.calls == before, "insufficient_confirm_called_provider")
        require(item["current_attempt"]["feedback"]["ai_static_review"]["review"]["overall"] == "insufficient", "insufficient_advice_relabelled")
        return {"state": brief(item), "insufficient_retained": True, "personal_review_only": True}


async def api_case(factory, provider, guard):
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
        versions = dict(session.execute(text("SELECT id,auth_version FROM users WHERE id IN (:owner,:other)"), {"owner": OWNER_ID, "other": OTHER_OWNER_ID}).all())
    headers = {owner: {"Authorization": "Bearer " + security.create_access_token(owner, versions[owner] or 0).value} for owner in (OWNER_ID, OTHER_OWNER_ID)}
    codes, prefix = {}, get_settings().api_v1_prefix
    async def checked(client, label, method, path, expected, **kwargs):
        response = await client.request(method, prefix + path, **kwargs)
        codes[label] = response.status_code
        require(response.status_code == expected, "api_" + label + "_status_mismatch")
        return response
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://s08.local") as client:
            path = f"/projects/{PROJECT_ID}/practice-sessions"
            await checked(client, "unauthenticated", "GET", path, 401)
            response = await checked(client, "create", "POST", path, 201, headers=headers[OWNER_ID], json={"template_id": "python-learning-csv", "template_version": "1.0", "expected_context_version": CONTEXT_VERSION, "request_key": key("api", "create")})
            item = response.json()
            path = "/practice-sessions/" + item["id"]
            await checked(client, "cross_owner", "GET", path, 404, headers=headers[OTHER_OWNER_ID])
            for action, suffix in (("start", "start"), ("confirm", "understand-confirm")):
                response = await checked(client, action, "POST", path + "/actions", 200, headers=headers[OWNER_ID], json={"action": action, "expected_revision": item["revision"], "request_key": key("api", suffix)})
                item = response.json()
            fixture = fixtures()
            payload = {"expected_revision": item["revision"], "step_key": "implement", "request_key": key("api", "submit-1"), "code": fixture["cases"]["Q05"]["student_code"], "declared_output": {}, "self_statement": False}
            response = await checked(client, "submit", "POST", path + "/attempts", 201, headers=headers[OWNER_ID], json=payload)
            item = response.json()
            identity, calls = attempt_id(item), provider.calls
            response = await checked(client, "duplicate_submit", "POST", path + "/attempts", 201, headers=headers[OWNER_ID], json=payload)
            require(response.json()["submission"]["replayed"], "api_submit_replay_missing")
            await checked(client, "changed_payload", "POST", path + "/attempts", 409, headers=headers[OWNER_ID], json={**payload, "code": payload["code"] + "\n"})
            await checked(client, "cross_owner_submit", "POST", path + "/attempts", 404, headers=headers[OTHER_OWNER_ID], json={**payload, "request_key": key("api", "forbidden-submit")})
            await checked(client, "stale_revision", "POST", path + "/actions", 409, headers=headers[OWNER_ID], json={"action": "review", "attempt_id": identity, "expected_revision": 1, "request_key": key("api", "stale-review")})
            await checked(client, "cross_owner_confirm", "POST", path + "/actions", 404, headers=headers[OTHER_OWNER_ID], json={"action": "confirm", "attempt_id": identity, "expected_revision": item["revision"], "request_key": key("api", "forbidden-confirm")})
            require(provider.calls == calls, "api_invalid_or_replay_called_provider")
            response = await checked(client, "cancel", "POST", path + "/actions", 200, headers=headers[OWNER_ID], json={"action": "cancel", "expected_revision": item["revision"], "request_key": key("api", "cancel")})
            item = response.json()
            require(not item["current_attempt"]["can_confirm"], "api_cancelled_still_confirmable")
            await checked(client, "cancelled_confirm", "POST", path + "/actions", 409, headers=headers[OWNER_ID], json={"action": "confirm", "attempt_id": identity, "expected_revision": item["revision"], "request_key": key("api", "cancelled-confirm")})
            for action in ("resume", "confirm"):
                response = await checked(client, "implement_" + action, "POST", path + "/actions", 200, headers=headers[OWNER_ID], json={"action": action, "attempt_id": identity, "expected_revision": item["revision"], "request_key": key("api", "implement-" + action)})
                item = response.json()
            calls = provider.calls
            writes_before_gets = len(guard.writes)
            await checked(client, "owner_get", "GET", path, 200, headers=headers[OWNER_ID])
            await checked(client, "owner_list", "GET", f"/projects/{PROJECT_ID}/practice-sessions", 200, headers=headers[OWNER_ID])
            await checked(client, "s06_main", "GET", "/offline-analytics/batches/" + BATCHES[0], 200, headers=headers[OWNER_ID])
            await checked(client, "s06_boundary", "GET", "/offline-analytics/batches/" + BATCHES[1], 200, headers=headers[OTHER_OWNER_ID])
            require(provider.calls == calls and item["status"] == "completed", "api_get_or_completion_wrong")
            require(len(guard.writes) == writes_before_gets, "api_get_produced_dml")
            require(item["current_attempt"]["feedback"]["ai_static_review"] is None and item["current_attempt"]["feedback"]["teacher_confirmation"] is None, "api_direct_confirmation_fabricated_advice")
        return {"state": brief(item), "status_codes": codes, "authentication": "real_JWT_and_current_user",
                "transport": "ASGI_in_process", "get_dml_count": 0, "advice_not_requested": True}
    finally:
        app.dependency_overrides.clear()


def read_session_only(database, session_id):
    require(str(UUID(session_id)) == session_id, "invalid_session_uuid")
    engine = existing_target_engine(database)
    def no_write(connection, cursor, statement, parameters, context, executemany):
        del connection, cursor, parameters, context, executemany
        require(statement.lstrip().upper().startswith(("SELECT ", "SHOW ", "SET ")), "child_write_rejected")
    event.listen(engine, "before_cursor_execute", no_write)
    provider = FakePracticeProvider()
    try:
        with Session(engine, autoflush=False, expire_on_commit=False) as session:
            item = build_service(session, provider).get(OWNER_ID, session_id)
        require(provider.calls == 0, "read_restore_called_provider")
        return {"status": "passed", "restored_state": brief(item), "fake_provider_calls": 0}
    finally:
        event.remove(engine, "before_cursor_execute", no_write)
        engine.dispose()


def independent_restore(database, expected):
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "scripts.verify_s08_practice", "--database", database, "--read-session", expected["id"]], cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)
    require(result.returncode == 0, "independent_read_process_failed")
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise VerificationFailure("independent_read_invalid_json") from exc
    require(payload.get("status") == "passed" and payload.get("restored_state") == expected, "independent_restore_mismatch")
    return {"status": "passed", "restored_state": payload["restored_state"], "separate_python_process": True, "fake_provider_calls": 0}


def serve_readonly(database, port):
    """仅给本轮重启检查使用，真实路由/鉴权/库，所有SQL写入均拒绝。"""
    import uvicorn
    from app.api.deps import get_db_session
    from app.api.practice_deps import get_practice_service
    from app.main import create_app
    engine = existing_target_engine(database)
    def readonly(connection, cursor, statement, parameters, context, executemany):
        require(statement.lstrip().upper().startswith(("SELECT ", "SHOW ", "SET ")), "http_restore_write_rejected")
    event.listen(engine, "before_cursor_execute", readonly)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    provider = FakePracticeProvider()
    app = create_app()
    def database_override():
        with factory() as session:
            yield session
    async def service_override(session: Session = Depends(get_db_session)):
        yield build_service(session, provider)
    app.dependency_overrides[get_db_session] = database_override
    app.dependency_overrides[get_practice_service] = service_override
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, access_log=False, log_level="warning")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def tcp_restart(database, engine, expected, output_dir):
    import httpx
    from app.core.config import get_security_settings
    from app.core.security import SecurityService
    with engine.connect() as connection:
        auth_version = connection.scalar(text("SELECT auth_version FROM users WHERE id=:id"), {"id": OWNER_ID})
        before = {table: int(connection.scalar(text(f"SELECT COUNT(*) FROM {table}"))) for table in ROW_LIMITS}
    headers = {"Authorization": "Bearer " + SecurityService(get_security_settings()).create_access_token(OWNER_ID, auth_version or 0).value}
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    prefix = get_settings().api_v1_prefix
    observed = []
    for number in (1, 2):
        process = None
        with (output_dir / f"tcp-server-{number}.stdout.txt").open("x", encoding="utf-8") as stdout, \
             (output_dir / f"tcp-server-{number}.stderr.txt").open("x", encoding="utf-8") as stderr:
            try:
                process = subprocess.Popen([sys.executable, "-B", "-X", "utf8", "-m", "scripts.verify_s08_practice",
                    "--database", database, "--serve-readonly-port", str(port)], cwd=BACKEND,
                    stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3, trust_env=False) as client:
                    deadline = time.monotonic() + 20
                    while True:
                        require(process.poll() is None, "readonly_server_exited_early")
                        try:
                            if client.get(prefix + "/health").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        require(time.monotonic() < deadline, "readonly_server_start_timeout")
                        time.sleep(0.1)
                    response = client.get(prefix + "/practice-sessions/" + expected["id"], headers=headers)
                    require(response.status_code == 200, "tcp_restore_status_wrong")
                    item = response.json()
                    require(brief(item) == expected, "tcp_restart_state_mismatch")
                    require(item["current_attempt"]["code"] == fixtures()["cases"]["Q01"]["student_code"], "tcp_restart_code_mismatch")
                    require(item["current_attempt"]["feedback"]["ai_static_review"] is None, "tcp_restart_invented_advice")
                    observed.append({"process_id": process.pid, "http_status": response.status_code,
                                     "state": brief(item), "code_matches_current_fixture": True})
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    with engine.connect() as connection:
        after = {table: int(connection.scalar(text(f"SELECT COUNT(*) FROM {table}"))) for table in ROW_LIMITS}
    require(before == after, "tcp_get_or_restart_added_rows")
    require(observed[0]["process_id"] != observed[1]["process_id"], "tcp_server_not_restarted")
    return {"status": "passed", "transport": "real_TCP_loopback", "port": port,
            "runs": observed, "sql_write_policy": "SELECT_SHOW_SET_only", "row_deltas": {table: 0 for table in ROW_LIMITS},
            "real_model_calls": 0, "servers_stopped": True,
            "scope": "restart_at_persisted_human_wait_not_process_crash_during_provider"}


async def run_cases(factory, engine, results, guard):
    provider = FakePracticeProvider()
    for label, callback in (("direct_personal_end", first_case), ("optional_revisions", revision_case),
            ("cancelled_late", late_case), ("without_submission", empty_case),
            ("failed_advice_personal_end", failed_case), ("insufficient", insufficient_case),
            ("needs_changes_personal_end", advice_only_case), ("two_connection_concurrency", concurrent_case),
            ("expired_review", timeout_case)):
        results[label] = await callback(factory, provider)
    results["invalid_advice_personal_end"] = await failed_case(factory, provider, "invalid")
    results["transaction_rollback"] = await rollback_case(factory, provider, engine)
    results["api"] = await api_case(factory, provider, guard)
    results["fake_provider_calls"] = provider.calls
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--confirm-limits")
    parser.add_argument("--read-session")
    parser.add_argument("--serve-readonly-port", type=int)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.database != DATABASE:
        parser.error("目标必须是本轮已核对的专用隔离库")
    plan = {"stage": "S08", "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "database": DATABASE, "host": "127.0.0.1:3306", "run_id": RUN_ID,
        "mode": "apply" if args.apply else "dry_run", "limits": ROW_LIMITS,
        "authorization_source": "用户2026-10-26直接指令：进行收验把；仅补S08隔离真实工程验收，边界见同目录authorization.json",
        "limits_basis": "本轮必要样例的执行保护上限，不复用历史剩余额度",
        "initial_row_counts": INITIAL_COUNTS, "initial_table_count": 39, "migration": "not_required",
        "real_model_calls": 0, "student_code_execution": 0, "cleanup": "retain_new_evidence_rows"}
    if args.serve_readonly_port is not None:
        require(not args.apply and not args.read_session and not args.output, "readonly_server_mode_conflict")
        require(1024 <= args.serve_readonly_port <= 65535, "invalid_readonly_server_port")
        serve_readonly(args.database, args.serve_readonly_port)
        return 0
    if args.read_session:
        require(not args.apply, "read_with_apply_rejected")
        try:
            print(safe_json(read_session_only(args.database, args.read_session)))
            return 0
        except Exception as exc:
            print(safe_json({"status": "failed", "error_code": str(exc) if isinstance(exc, VerificationFailure) else type(exc).__name__}))
            return 1
    if not args.apply:
        plan["database_connection"] = "not_opened"
        print(safe_json(plan))
        return 0
    if args.confirm_database != args.database or args.confirm_limits != "14,20,180,28,28":
        parser.error("须确认同一数据库与14,20,180,28,28本轮执行上限；不得借旧tag许可")
    if not args.output:
        parser.error("执行必须指定新的证据JSON路径")
    output = Path(args.output)
    if output.exists():
        parser.error("证据已存在，禁止覆盖旧成功或失败")
    output.parent.mkdir(parents=True, exist_ok=True)
    engine = None
    baseline = None
    try:
        engine = existing_target_engine(args.database)
        baseline = snapshot(engine)
        verify_initial(baseline)
        plan["existing_run_ledger"] = baseline["run_ledger"]
        with WriteGuard(engine, baseline) as guard:
            factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
            plan["checks"] = {}
            asyncio.run(run_cases(factory, engine, plan["checks"], guard))
            waiting = plan["checks"]["cancelled_late"]["state"]
            plan["checks"]["independent_process_restore"] = independent_restore(args.database, waiting)
            plan["checks"]["http_server_restart"] = tcp_restart(args.database, engine, waiting, output.parent)
            plan["write_statement_count"] = len(guard.writes)
        final = snapshot(engine)
        plan["row_deltas"] = verify_preserved(baseline, final)
        plan["cumulative_run_ledger"] = final["run_ledger"]
        plan["protected_baseline_counts"] = baseline["row_counts"]
        plan["protected_s06_batches"] = final["batches"]
        plan["protected_s06_metrics"] = final["metrics"]
        plan["old_rows_preserved"] = True
        plan["model_quality"] = "not_evaluated_fake_only"
        plan["status"] = "passed"
    except Exception as exc:
        plan["status"] = "failed"
        plan["error_code"] = str(exc) if isinstance(exc, VerificationFailure) else type(exc).__name__
        if engine is not None:
            try:
                with engine.connect() as connection:
                    plan["cumulative_run_ledger"] = run_ledger(connection)
                if baseline is not None:
                    plan["row_deltas"] = verify_preserved(baseline, snapshot(engine))
                    plan["old_rows_preserved"] = True
            except Exception:
                plan["ledger_after_failure"] = "unavailable"
    finally:
        if engine is not None:
            engine.dispose()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(safe_json(plan) + "\n", encoding="utf-8")
    print(safe_json(plan))
    return 0 if plan["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
