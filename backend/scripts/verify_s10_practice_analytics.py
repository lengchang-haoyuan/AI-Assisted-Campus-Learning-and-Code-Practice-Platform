"""S10专用隔离验收；默认只读盘点，所有写入须显式阶段开关与同库确认。"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import threading
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from fastapi import Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from sqlalchemy import event, text
from sqlalchemy.orm import Session, sessionmaker
import uvicorn

from app.api.deps import get_ai_service, get_db_session, get_workflow_execution_service
from app.api.practice_deps import get_practice_service
from app.core.config import get_security_settings
from app.core.security import SecurityService
from app.main import create_app
from scripts.verify_s08_practice import (
    BATCHES, DATABASE, WRITE_PATTERN, build_service, existing_target_engine,
    require, safe_json, snapshot,
)
from scripts.verify_s09_student_ui import FakeProvider

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "开发相关文档/阶段报告/AI大数据改造/V2"
OUTPUT = V2 / "S10-证据"
TAG = "s10-practice-20261026"
PORT = 56594
OWNER = 3
LIMITS = {
    "projects": 1, "practice_sessions": 6, "practice_attempts": 12,
    "practice_events": 120, "ai_requests": 24, "ai_results": 24,
    "analytics_batches": 3, "analytics_daily_metrics": 18,
    "daily_tasks": 6, "practice_recommendation_applications": 6,
}
INITIAL_COUNTS = {"projects": 2, "daily_tasks": 204, "practice_sessions": 31,
                  "practice_attempts": 28, "practice_events": 219,
                  "analytics_batches": 14, "analytics_daily_metrics": 20,
                  "ai_requests": 56, "ai_results": 50,
                  "practice_recommendation_applications": 0}
CODE = "def summarize_records(csv_text):\n    return {}\n"


def key(label):
    return str(uuid5(NAMESPACE_URL, TAG + ":" + label))


def write_result(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(safe_json(value) + "\n", encoding="utf-8")


def read_result(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def fingerprint(rows):
    """只保存旧行摘要，跨阶段核对保护性验证，不持久化旧正文或凭证。"""
    ordered = sorted((safe_json(identity), safe_json(value)) for identity, value in rows.items())
    return hashlib.sha256(json.dumps(ordered, ensure_ascii=False).encode("utf-8")).hexdigest()


def baseline_record(state):
    return {"tables": state["tables"], "row_counts": state["row_counts"],
            "protected": {table: {"keys": [safe_json(identity) for identity in rows],
                                  "fingerprint": fingerprint(rows)} for table, rows in state["rows"].items()}}


def validate_preserved(baseline, current):
    require(baseline["tables"] == current["tables"], "unexpected_table_set")
    for table, info in baseline["protected"].items():
        encoded = {safe_json(identity): (identity, row) for identity, row in current["rows"][table].items()}
        require(all(identity in encoded for identity in info["keys"]), "old_row_deleted_" + table)
        protected = {encoded[identity][0]: encoded[identity][1] for identity in info["keys"]}
        require(fingerprint(protected) == info["fingerprint"], "old_row_changed_" + table)
    deltas = {table: current["row_counts"].get(table, 0) - count for table, count in baseline["row_counts"].items()}
    require(all(0 <= count <= LIMITS.get(table, 0) for table, count in deltas.items()), "write_scope_or_limit_exceeded")
    return {table: deltas[table] for table in LIMITS}


def discover_ids(state):
    ids = {table: set() for table in LIMITS}
    ids["projects"] = {row["id"] for row in state["rows"]["projects"].values() if row["name"] == TAG and row["owner_id"] == OWNER}
    require(len(ids["projects"]) <= 1, "duplicate_fixture_project")
    for table in ("practice_sessions", "ai_requests", "daily_tasks"):
        ids[table] = {row["id"] for row in state["rows"][table].values() if row["project_id"] in ids["projects"]}
    for table in ("practice_attempts", "practice_events"):
        ids[table] = {row["id"] for row in state["rows"][table].values() if row["session_id"] in ids["practice_sessions"]}
    ids["ai_results"] = {row["id"] for row in state["rows"]["ai_results"].values() if row["request_id"] in ids["ai_requests"]}
    ids["analytics_batches"] = {row["batch_id"] for row in state["rows"]["analytics_batches"].values()
                                if row["owner_user_id"] == OWNER and row["artifact_ref"].startswith("s10-")}
    ids["analytics_daily_metrics"] = {(row["batch_id"], row["metric_date"]) for row in state["rows"]["analytics_daily_metrics"].values() if row["batch_id"] in ids["analytics_batches"]}
    ids["practice_recommendation_applications"] = {row["id"] for row in state["rows"]["practice_recommendation_applications"].values() if row["batch_id"] in ids["analytics_batches"] and row["owner_user_id"] == OWNER}
    return ids


class Guard:
    """仅本轮行可写；禁止DDL、旧行修改和有数据的DELETE。"""
    def __init__(self, engine, baseline, ids=None, write_tables=None):
        self.engine, self.baseline = engine, baseline
        self.ids = ids or {table: set() for table in LIMITS}
        self.writes = []
        self.empty_delete_statements = 0
        self.actual_rows_deleted = 0
        self.write_tables = set(LIMITS) if write_tables is None else set(write_tables)

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
        require(table in self.write_tables, "write_table_rejected")
        records = context.compiled_parameters or []
        require(bool(records), "unbound_write_rejected")
        if verb.startswith("DELETE"):
            # 既有发布服务清理新prepared批次的空日表：只允许实际删除0行。
            require(table == "analytics_daily_metrics", "delete_rejected")
            where = re.search(r"WHERE analytics_daily_metrics.batch_id = %\((\w+)\)s\s*$", statement)
            require(where is not None, "delete_scope_rejected")
            for row in records:
                identity = row.get(where.group(1))
                require(identity in self.ids["analytics_batches"], "old_batch_delete_rejected")
                count = connection.scalar(text("SELECT COUNT(*) FROM analytics_daily_metrics WHERE batch_id=:id"), {"id": identity})
                require(count == 0, "nonempty_delete_rejected")
        elif verb.startswith("INSERT"):
            current = connection.scalar(text("SELECT COUNT(*) FROM " + table))
            require(current - self.baseline["row_counts"][table] + len(records) <= LIMITS[table], "row_budget_exceeded")
            for row in records:
                if table == "projects":
                    require(row.get("owner_id") == OWNER and row.get("name") == TAG, "wrong_project_fixture")
                elif table in ("practice_sessions", "ai_requests", "daily_tasks"):
                    require(row.get("project_id") in self.ids["projects"], "outside_new_project")
                    owner_field = "owner_user_id" if table == "practice_sessions" else "user_id"
                    require(row.get(owner_field) == OWNER, "wrong_fixture_owner")
                    if table == "daily_tasks":
                        require(row.get("plan_id") is None, "task_plan_write_rejected")
                elif table in ("practice_attempts", "practice_events"):
                    require(row.get("session_id") in self.ids["practice_sessions"], "outside_new_session")
                elif table == "ai_results":
                    require(row.get("request_id") in self.ids["ai_requests"], "outside_new_request")
                elif table == "analytics_batches":
                    require(row.get("owner_user_id") == OWNER and row.get("artifact_ref", "").startswith("s10-"), "outside_new_batch")
                else:
                    require(row.get("batch_id") in self.ids["analytics_batches"], "outside_new_batch")
                    if table == "practice_recommendation_applications":
                        require(row.get("owner_user_id") == OWNER and row.get("task_id") in self.ids["daily_tasks"], "outside_new_application")
        else:
            require(table in {"projects", "practice_sessions", "practice_attempts", "ai_requests", "analytics_batches", "daily_tasks"}, "immutable_row_update")
            primary = "batch_id" if table == "analytics_batches" else "id"
            where = re.search(r"\bWHERE\s+`?" + table + r"`?\.`?" + primary + r"`?\s*=\s*%\((\w+)\)s\s*$", statement, re.I)
            require(where is not None, "update_requires_single_pk")
            require(all(row.get(where.group(1)) in self.ids[table] for row in records), "old_row_update_rejected")
            if table == "practice_attempts":
                setters = statement.split("WHERE", 1)[0].lower()
                require(not any(re.search(r"\b" + field + r"\s*=", setters) for field in ("code_text", "declared_output", "self_statement", "request_key", "session_id", "attempt_no", "step_key")), "attempt_payload_update")
        self.writes.append({"verb": verb, "table": table})

    def after(self, connection, cursor, statement, parameters, context, executemany):
        del connection, parameters, executemany
        match = WRITE_PATTERN.match(statement)
        if not match:
            return
        if match.group(1).upper().startswith("DELETE"):
            require(cursor.rowcount == 0, "actual_delete_rejected")
            self.empty_delete_statements += 1
            return
        if not match.group(1).upper().startswith("INSERT"):
            return
        table, records = match.group(2), context.compiled_parameters or []
        for row in records:
            if table == "analytics_daily_metrics":
                identity = (row["batch_id"], row["metric_date"])
            elif table == "analytics_batches":
                identity = row["batch_id"]
            else:
                require(len(records) == 1 or row.get("id") is not None, "auto_id_bulk_rejected")
                identity = row.get("id") or cursor.lastrowid
            self.ids[table].add(identity)


def application(engine, provider, readonly=False, application_only=False):
    app = create_app()
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:4198"], allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Accept", "Authorization", "Content-Type"])
    factory = sessionmaker(engine, expire_on_commit=False)

    def database_override():
        with factory() as session:
            yield session

    async def practice_override(session: Session = Depends(get_db_session)):
        yield build_service(session, provider)

    def blocked_ai():
        raise HTTPException(403, "S10验收仅允许显式Fake实践")

    app.dependency_overrides[get_db_session] = database_override
    app.dependency_overrides[get_practice_service] = practice_override
    app.dependency_overrides[get_ai_service] = blocked_ai
    app.dependency_overrides[get_workflow_execution_service] = blocked_ai

    @app.middleware("http")
    async def narrow_requests(request, call_next):
        path = request.url.path.removeprefix("/api/v1")
        application_post = request.method == "POST" and re.fullmatch(r"/offline-analytics/batches/[a-f0-9-]+/recommendation-applications", path)
        allowed = request.method in {"GET", "OPTIONS"} or (not readonly and (application_post or (not application_only and (
            (request.method == "POST" and (path == "/projects" or re.fullmatch(r"/projects/\d+/(context|practice-sessions)", path)
             or re.fullmatch(r"/practice-sessions/[a-f0-9-]+/(attempts|actions)", path)))
            or (request.method == "PUT" and re.fullmatch(r"/learning/tasks/\d+", path))))))
        if not allowed:
            from starlette.responses import JSONResponse
            return JSONResponse({"error": {"message": "S10验收范围之外"}}, status_code=403)
        return await call_next(request)
    return app


def token(engine, owner=OWNER):
    with engine.connect() as connection:
        version = connection.scalar(text("SELECT auth_version FROM users WHERE id=:id AND is_active=1"), {"id": owner})
    require(version is not None, "fixture_owner_missing")
    return SecurityService(get_security_settings()).create_access_token(owner, version).value


async def call(client, method, path, payload=None, expected=None):
    response = await client.request(method, path, json=payload)
    if expected is None:
        require(response.is_success, "api_" + str(response.status_code))
    else:
        require(response.status_code == expected, "expected_" + str(expected) + "_got_" + str(response.status_code))
    return response.json()


class Journal:
    """只记录虚构样例与确定请求；失败后须显式resume，不能重新耗用次数。"""
    def __init__(self, resume):
        self.path = OUTPUT / "setup-journal.json"
        require(resume or not self.path.exists(), "existing_setup_requires_resume")
        self.values = json.loads(self.path.read_text(encoding="utf-8")) if resume else {}

    async def step(self, client, label, method, path, payload=None, expected=None):
        previous = self.values.get(label)
        if previous and "response" in previous:
            return previous["response"]
        if previous:
            require(previous["method"] == method and previous["path"] == path, "journal_request_changed")
            payload = previous["payload"]
        else:
            self.values[label] = {"method": method, "path": path, "payload": payload}
            self.save()
        result = await call(client, method, path, payload, expected)
        self.values[label]["response"] = result
        self.save()
        return result

    def save(self):
        write_result("setup-journal.json", self.values)


async def setup(engine, provider, resume=False):
    journal = Journal(resume)
    transport = httpx.ASGITransport(app=application(engine, provider), raise_app_exceptions=False)
    headers = {"Authorization": "Bearer " + token(engine)}
    results = {}
    async with httpx.AsyncClient(transport=transport, base_url="http://s10/api/v1", headers=headers, timeout=45) as client:
        project = await journal.step(client, "project", "POST", "/projects", {"name": TAG, "description": "S10隔离过程分析样例；Fake建议不代表质量。", "language": "Python", "output_requirement": "CSV纯函数与本人审阅"})
        project_id = project["id"]
        context = await journal.step(client, "context", "POST", f"/projects/{project_id}/context")

        async def create(label):
            item = await journal.step(client, label + ":create", "POST", f"/projects/{project_id}/practice-sessions", {
                "template_id": "python-learning-csv", "template_version": "1.0", "expected_context_version": context["version"], "request_key": key(label + ":create")})
            item = await act(item, label + ":start", "start")
            return await act(item, label + ":understanding", "confirm")

        async def act(item, label, action, attempt=False, expected=None):
            payload = {"action": action, "expected_revision": item["revision"], "request_key": key(label)}
            if attempt:
                payload["attempt_id"] = item["current_attempt"]["id"]
            return await journal.step(client, label, "POST", f"/practice-sessions/{item['id']}/actions", payload, expected)

        async def submit(item, label, code=CODE):
            return await journal.step(client, label, "POST", f"/practice-sessions/{item['id']}/attempts", {
                "expected_revision": item["revision"], "step_key": "implement", "request_key": key(label),
                "code": code, "declared_output": {}, "self_statement": None})

        item = await submit(await create("direct"), "direct:submit")
        item = await act(item, "direct:personal-end", "confirm", True)
        require(item["status"] == "completed", "direct_end_failed")
        results["direct"] = summary(item)

        item = await submit(await create("modify"), "modify:submit1")
        item = await act(item, "modify:review1", "review", True)
        item = await submit(item, "modify:submit2", "# 自选修改第2版\n" + CODE)
        item = await act(item, "modify:review2", "review", True)
        item = await act(item, "modify:personal-end", "confirm", True)
        require(len(item["attempts"]) == 2 and item["status"] == "completed", "optional_revision_failed")
        results["modify"] = summary(item)

        item = await create("empty")
        require(item["status"] == "waiting_submission" and item["current_attempt"] is None, "empty_state_wrong")
        await act(item, "empty:reject-end", "confirm", False, 409)
        results["empty"] = summary(item)

        item = await submit(await create("cancel"), "cancel:submit1")
        item = await act(item, "cancel:review1", "review", True)
        item = await act(item, "cancel:cancel", "cancel")
        item = await act(item, "cancel:resume", "resume")
        item = await submit(item, "cancel:submit2", "# 取消恢复后的自选版本\n" + CODE)
        item = await act(item, "cancel:review2", "review", True)
        results["cancel"] = summary(item)

        item = await submit(await create("failure"), "failure:submit", "# FAIL_ADVICE\n" + CODE)
        pending_failure = journal.values.get("failure:review")
        if pending_failure and "response" not in pending_failure:
            # 上轮已发生502但来不及保存响应：只核实持久失败，禁止再次发送模型动作。
            observed = await call(client, "GET", f"/practice-sessions/{item['id']}")
            request = observed.get("model_request") or {}
            attempt = observed.get("current_attempt") or {}
            require(observed["status"] == "failed" and request.get("status") == "failed"
                    and request.get("provider") == "fake" and request.get("error_code") == "upstream"
                    and attempt.get("id") == pending_failure["payload"]["attempt_id"], "pending_failure_requires_inspection")
            with engine.connect() as connection:
                bound_failure = connection.scalar(text("SELECT COUNT(*) FROM practice_events WHERE session_id=:session "
                    "AND event_key=:key AND event_type='review_failed' AND attempt_id=:attempt "
                    "AND JSON_UNQUOTE(JSON_EXTRACT(action_payload,'$.ai_request_id'))=:request"),
                    {"session": item["id"], "key": pending_failure["payload"]["request_key"] + ":action:failed",
                     "attempt": attempt["id"], "request": str(request["id"])})
            require(bound_failure == 1, "failed_request_binding_not_observed")
            pending_failure["response"] = {"persisted_failure_observed": True, "provider": "fake", "error_code": "upstream",
                                           "ai_request_id": request["id"], "model_post_reissued": False}
            journal.save()
        else:
            await act(item, "failure:review", "review", True, 502)
        item = await journal.step(client, "failure:query-failed", "GET", f"/practice-sessions/{item['id']}")
        require(item["status"] == "failed", "fake_failure_not_persisted")
        item = await act(item, "failure:resume", "resume")
        item = await act(item, "failure:personal-end", "confirm", True)
        require(item["status"] == "completed", "failure_blocked_personal_end")
        results["failure"] = summary(item)

        item = await submit(await create("candidate"), "candidate:submit1")
        item = await act(item, "candidate:review1", "review", True)
        item = await submit(item, "candidate:submit2", "# 供可选重复建议提醒的第2次提交\n" + CODE)
        item = await act(item, "candidate:review2", "review", True)
        await act(item, "candidate:same-attempt-review", "review", True, 409)
        results["candidate"] = summary(item)
        before_calls = provider.calls
        restored = await call(client, "GET", f"/practice-sessions/{item['id']}")
        require(summary(restored) == summary(item) and provider.calls == before_calls, "query_changed_current_attempt")
        results.update(passed=True, project_id=project_id, fake_calls_this_process=provider.calls, real_model_calls=0)
    write_result("setup-results.json", results)
    return results


def summary(item):
    attempt = item.get("current_attempt")
    return {"id": item["id"], "status": item["status"], "revision": item["revision"],
            "current_step_key": item["current_step_key"], "attempt_count": len(item["attempts"]),
            "attempt_id": attempt["id"] if attempt else None,
            "attempt_no": attempt["attempt_no"] if attempt else None}


async def verify_applications(engine, provider, batch_id, guard):
    from app.repositories.recommendation import RecommendationRepository

    setup_result = read_result("setup-results.json")
    app = application(engine, provider)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"Authorization": "Bearer " + token(engine)}
    result = {"checks": [], "batch_id": batch_id, "real_model_calls": 0}
    async with httpx.AsyncClient(transport=transport, base_url="http://s10/api/v1", headers=headers, timeout=45) as client:
        writes_before, calls_before = len(guard.writes), provider.calls
        detail = await call(client, "GET", f"/offline-analytics/batches/{batch_id}")
        listing = await call(client, "GET", "/offline-analytics/batches?dataset_kind=controlled&page_size=50")
        require(any(row["schema_version"] == "scholarhub-source-1.0" for row in listing["items"]) and any(row["schema_version"] == "scholarhub-source-2.0" for row in listing["items"]), "mixed_batch_list_missing")
        await call(client, "GET", f"/offline-analytics/batches/{BATCHES[0]}")
        require(len(guard.writes) == writes_before and provider.calls == calls_before, "get_has_side_effects")
        result["checks"].append("mixed_old_new_list_and_old_detail_get_zero_writes_models")
        own_candidates = {candidate["session_id"]: candidate for candidate in detail["recommendations"] if candidate["project_id"] == setup_result["project_id"]}
        candidate = own_candidates[setup_result["candidate"]["id"]]
        cancel_candidate = own_candidates[setup_result["cancel"]["id"]]
        require(len(candidate["references"]) == 2, "same_attempt_rereview_amplified_candidate")
        result["checks"].append("two_distinct_attempts_latest_bound_advice_only")

        def payload(source, suffix):
            return {"request_key": TAG + ":" + suffix, "candidate_key": source["candidate_key"],
                    "expected_metric_version": "learning-process-2.0", "expected_rule_version": "B-R1-advisory-1.0",
                    "expected_session_revision": source["session_revision"], "title": source["title"],
                    "scheduled_date": "2026-10-27", "project_id": setup_result["project_id"]}

        path = f"/offline-analytics/batches/{batch_id}/recommendation-applications"
        original_counts = snapshot(engine)["row_counts"]
        with patch.object(RecommendationRepository, "save_application", side_effect=RuntimeError("S10固定映射写入故障")):
            await call(client, "POST", path, payload(candidate, "rollback"), 500)
        after_rollback = snapshot(engine)["row_counts"]
        require(after_rollback["daily_tasks"] == original_counts["daily_tasks"] and after_rollback["practice_recommendation_applications"] == original_counts["practice_recommendation_applications"], "partial_task_after_failure")
        result["checks"].append("task_flush_then_mapping_failure_rolls_back_both")

        before = dict(payload(candidate, "concurrent-a"))
        alternate = dict(payload(candidate, "concurrent-b"))
        async def post_once(body):
            response = await client.post(path, json=body)
            return response.status_code, response.json()
        responses = await asyncio.gather(post_once(before), post_once(alternate))
        require(sorted(status for status, _ in responses) == [200, 409], "candidate_concurrency_not_single_winner")
        winner_index = next(index for index, (status, _) in enumerate(responses) if status == 200)
        winner_payload = (before, alternate)[winner_index]
        winner = responses[winner_index][1]
        task_id = winner["task_id"]
        result["checks"].append("same_candidate_different_request_concurrent_one_task")

        replay = await call(client, "POST", path, winner_payload)
        require(replay["task_id"] == task_id and replay["replayed"], "same_request_replay_failed")
        changed = {**winner_payload, "title": "S10异载荷"}
        await call(client, "POST", path, changed, 409)
        await call(client, "PUT", f"/learning/tasks/{task_id}", {"title": "S10用户后续编辑任务标题"})
        replay = await call(client, "POST", path, winner_payload)
        require(replay["task_id"] == task_id and replay["replayed"], "replay_compared_editable_task")
        task = await call(client, "GET", f"/learning/tasks/{task_id}")
        require(task["title"] == "S10用户后续编辑任务标题" and task["plan"] is None and batch_id in task["description"], "source_backlink_or_plan_wrong")
        result["checks"].append("same_payload_replay_after_task_edit_and_source_backlink")
        await call(client, "POST", f"/offline-analytics/batches/{BATCHES[0]}/recommendation-applications", payload(candidate, "old-batch"), 409)
        await call(client, "POST", path, {**payload(candidate, "wrong-version"), "expected_metric_version": "learning-process-1.0"}, 422)
        result["checks"].append("old_batch_and_wrong_metric_rejected")

        async with httpx.AsyncClient(transport=transport, base_url="http://s10/api/v1", headers={"Authorization": "Bearer " + token(engine, 4)}) as other:
            await call(other, "POST", path, payload(candidate, "other-owner"), 404)
            await call(other, "GET", f"/learning/tasks/{task_id}", expected=403)
        result["checks"].append("cross_owner_batch_application_and_task_rejected")

        item = await call(client, "GET", f"/practice-sessions/{cancel_candidate['session_id']}")
        await call(client, "POST", f"/practice-sessions/{item['id']}/actions", {"action": "confirm", "expected_revision": item["revision"], "request_key": key("cancel:after-cutoff-end"), "attempt_id": item["current_attempt"]["id"]})
        stale = await call(client, "POST", path, payload(cancel_candidate, "stale-source"), 409)
        require("来源已变化" in stale["error"]["message"], "stale_source_hidden_by_existing_candidate")
        result["checks"].append("source_revision_changed_after_cutoff_rejected")
        final_counts = snapshot(engine)["row_counts"]
        require(final_counts["daily_tasks"] == original_counts["daily_tasks"] + 1 and final_counts["practice_recommendation_applications"] == original_counts["practice_recommendation_applications"] + 1, "unexpected_application_rows")
        require(provider.calls == calls_before, "recommendation_application_called_model")
        result.update(passed=True, application=winner, winner_request=winner_payload, task_id=task_id,
                      same_candidate_statuses=[status for status, _ in responses], fake_calls=provider.calls)
    write_result("application-results.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    stage = parser.add_mutually_exclusive_group()
    stage.add_argument("--setup", action="store_true")
    stage.add_argument("--export", action="store_true")
    stage.add_argument("--publish-job")
    stage.add_argument("--verify-applications")
    stage.add_argument("--serve-readonly", action="store_true")
    stage.add_argument("--serve-writer-only-application", action="store_true")
    parser.add_argument("--serve-seconds", type=int, default=180)
    parser.add_argument("--confirm-database")
    parser.add_argument("--resume-partial", action="store_true")
    args = parser.parse_args()
    writing = args.setup or args.publish_job or args.verify_applications or args.serve_writer_only_application
    if writing and args.confirm_database != DATABASE:
        parser.error("写验收须--confirm-database精确确认本轮隔离库")
    require(not args.resume_partial or args.setup, "resume_only_setup")
    require(1 <= args.serve_seconds <= 300, "server_duration_out_of_range")
    engine = existing_target_engine(DATABASE)
    provider = FakeProvider()
    try:
        if args.serve_readonly:
            @event.listens_for(engine, "before_cursor_execute")
            def readonly(connection, cursor, statement, parameters, context, executemany):
                require(statement.lstrip().upper().startswith(("SELECT ", "SHOW ", "SET ")), "readonly_write_rejected")
            uvicorn.run(application(engine, provider, True), host="127.0.0.1", port=PORT, access_log=False, log_level="critical")
            return 0
        current = snapshot(engine)
        if not (args.setup or args.export or args.publish_job or args.verify_applications or args.serve_writer_only_application):
            plan = {"database": DATABASE, "tables": len(current["tables"]), "counts": current["row_counts"], "limits": LIMITS,
                    "tag": TAG, "readonly": True, "real_model_calls": 0, "mapping_table_exists": "practice_recommendation_applications" in current["tables"]}
            write_result("database-plan.json", plan)
            print(safe_json(plan))
            return 0
        require(len(current["tables"]) == 40 and "practice_recommendation_applications" in current["tables"], "s10_migration_required")
        baseline_path = OUTPUT / "protected-baseline.json"
        if args.setup and (OUTPUT / "setup-results.json").exists():
            require(not read_result("setup-results.json").get("passed"), "setup_already_complete")
        if args.setup and not args.resume_partial:
            require(not baseline_path.exists(), "existing_baseline_requires_inspection")
            require(all(current["row_counts"][table] == count for table, count in INITIAL_COUNTS.items()), "initial_counts_changed")
            write_result("protected-baseline.json", baseline_record(current))
        baseline = read_result("protected-baseline.json")
        validate_preserved(baseline, current)
        ids = discover_ids(current)
        if args.serve_writer_only_application:
            require(read_result("setup-results.json").get("passed") is True, "setup_not_complete")
            serve_application_only(engine, provider, baseline, current, ids, args.serve_seconds)
            return 0
        if args.export:
            from scripts.export_ods_snapshot import export_snapshot
            path, manifest = export_snapshot(engine, V2 / "S10-样本", "s10-practice-owner3-20261026", OWNER,
                                             "2026-10-21", "2026-10-26", include_practice=True)
            write_result("export-results.json", {"passed": True, "path": str(path), "manifest": manifest, "real_model_calls": 0})
            print(safe_json({"passed": True, "snapshot_id": manifest["snapshot_id"], "counts": manifest["row_counts"]}))
            return 0
        with Guard(engine, baseline, ids) as guard:
            try:
                if args.setup:
                    result = asyncio.run(setup(engine, provider, args.resume_partial))
                elif args.publish_job:
                    from app.repositories.analytics import AnalyticsRepository
                    from app.services.analytics import AnalyticsService
                    from app.services.analytics_artifacts import load_publication
                    with Session(engine) as session:
                        identity, replayed = AnalyticsService(AnalyticsRepository(session)).publish(load_publication(args.publish_job))
                    result = {"passed": True, "batch_id": identity, "replayed": replayed, "job_id": args.publish_job}
                    write_result("publication-results.json", result)
                else:
                    require(not (OUTPUT / "application-results.json").exists(), "application_acceptance_already_run_requires_inspection")
                    result = asyncio.run(verify_applications(engine, provider, args.verify_applications, guard))
            finally:
                final = snapshot(engine)
                deltas = validate_preserved(baseline, final)
                requests = [row for row in final["rows"]["ai_requests"].values() if row["project_id"] in guard.ids["projects"]]
                require(all(row["provider"] == "fake" for row in requests), "nonfake_request_found")
                write_result("mysql-results.json", {"all_old_rows_preserved": True, "within_limits": True, "deltas": deltas,
                            "final_counts": final["row_counts"], "fake_calls": len(requests), "real_model_calls": 0,
                            "fixtures_retained": True, "guarded_writes": guard.writes,
                            "empty_delete_statements": guard.empty_delete_statements, "actual_rows_deleted": guard.actual_rows_deleted})
        print(safe_json({"passed": result.get("passed"), "deltas": deltas, "real_model_calls": 0}))
        return 0
    finally:
        engine.dispose()


def serve_application_only(engine, provider, baseline, initial, ids, seconds):
    """临时浏览器验收服务：只允许建议应用写入，并有界优雅退出。"""
    config = uvicorn.Config(application(engine, provider, application_only=True), host="127.0.0.1", port=PORT,
                            access_log=False, log_level="critical")
    server = uvicorn.Server(config)
    timer = threading.Timer(seconds, lambda: setattr(server, "should_exit", True))
    timer.daemon = True
    with Guard(engine, baseline, ids, {"daily_tasks", "practice_recommendation_applications"}) as guard:
        timer.start()
        try:
            server.run()
        finally:
            timer.cancel()
            require(server.started, "application_writer_server_not_started")
            final = snapshot(engine)
            deltas = validate_preserved(baseline, final)
            server_deltas = {table: final["row_counts"][table] - initial["row_counts"][table] for table in LIMITS}
            require(provider.calls == 0, "writer_server_called_model")
            write_result("writer-server-results.json", {
                "passed": True, "all_old_rows_preserved": True, "within_limits": True,
                "server_deltas": server_deltas, "total_deltas": deltas,
                "delta_scope": "all_authorized_processes_observed_between_server_start_and_stop",
                "initial_counts": initial["row_counts"],
                "final_counts": final["row_counts"], "guarded_writes": guard.writes,
                "empty_delete_statements": guard.empty_delete_statements,
                "actual_rows_deleted": guard.actual_rows_deleted,
                "fake_calls": 0, "real_model_calls": 0,
                "fixtures_retained": True, "temporary_api_stopped": True,
            })


if __name__ == "__main__":
    raise SystemExit(main())
