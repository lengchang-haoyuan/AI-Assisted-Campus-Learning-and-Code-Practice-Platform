"""S09专用隔离MySQL/Fake浏览器验收；默认只盘点，不迁移、不清表、不调用外部模型。"""
import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time

from fastapi import Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from sqlalchemy import event, text
from sqlalchemy.orm import Session, sessionmaker
import uvicorn

from app.ai.client import AIClient
from app.ai.provider import AIClientError, AIFailureCategory, AIProvider, AIProviderResult, AIUsage
from app.api.deps import get_ai_service, get_db_session, get_workflow_execution_service
from app.api.practice_deps import get_practice_service
from app.context.context_manager import ContextManager
from app.core.config import get_security_settings
from app.core.security import SecurityService
from app.main import create_app
from app.repositories.workflow import WorkflowRepository
from app.repositories.workflow_execution import WorkflowExecutionRepository
from app.services.workflow import WorkflowService
from app.workflow.agents import RequirementsAnalysisWorkflowAgent
from app.workflow.engine import WorkflowEngine, WorkflowEngineLimits
from app.workflow.registry import WorkflowAgentRegistry
from scripts.verify_s08_practice import DATABASE, WRITE_PATTERN, build_service, existing_target_engine, require, safe_json, snapshot

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "开发相关文档/阶段报告/AI大数据改造/V2/S09-证据"
TAG = "s09-student-ui-20261026"
PORT = 56593
LIMITS = {"projects": 1, "workflows": 1, "workflow_nodes": 1, "workflow_runs": 2,
          "practice_sessions": 6, "practice_attempts": 10, "practice_events": 100,
          "ai_requests": 16, "ai_results": 16}


class FakeProvider(AIProvider):
    def __init__(self):
        self.calls, self.sessions = 0, []

    @property
    def name(self):
        return "fake"

    async def complete(self, request):
        self.calls += 1
        require(self.calls <= LIMITS["ai_requests"], "fake_budget_exceeded")
        require(all(not session.in_transaction() for session in self.sessions), "model_wait_inside_transaction")
        messages = "\n".join(message.content for message in request.messages)
        if request.response_schema_name == "practice_review_v1":
            if "FAIL_ADVICE" in messages:
                raise AIClientError("S09固定Fake上游失败", category=AIFailureCategory.UPSTREAM,
                                    observed_usage=AIUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20))
            code = next(message.content.split("<STUDENT_CODE_PART>\n", 1)[1].rsplit("\n</STUDENT_CODE_PART>", 1)[0]
                        for message in request.messages if "<STUDENT_CODE_PART>\n" in message.content)
            quote = next(line for line in code.splitlines() if line.strip())
            result = {"summary": "Fake 工程建议：返回字段请自行核对。", "overall": "needs_changes",
                      "criteria": [{"criterion_id": f"C{i:02}", "verdict": "fail" if i == 5 else "pass",
                                    "issue_type": "empty_result_contract" if i == 5 else None,
                                    "evidence_span": quote, "reason": "固定Fake仅验证状态与来源展示。",
                                    "suggested_self_test": "自行核对完整五字段" if i == 5 else None,
                                    "next_action": "自行决定是否修改" if i == 5 else None} for i in range(1, 7)]}
        elif '"requirements_analysis"' in messages:
            result = {"result_type": "requirements_analysis", "summary": "Fake 工程需求样例",
                      "requirements": [{"title": "CSV纯函数", "description": "逐行校验并返回五字段", "acceptance_criteria": ["本人自行审阅"]}],
                      "features": ["逐行统计"], "constraints": ["平台不执行提交代码"]}
        else:
            result = {"summary": "Fake 工程说明", "guidance": ["逐行区分未知分钟与已知零。"], "checks": ["自行核对公开T01/T04。"]}
        return AIProviderResult(provider="fake", model="fake-s09", content=json.dumps(result, ensure_ascii=False),
                                finish_reason="stop", usage=AIUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20))


class Guard:
    """只允许新项目及本轮新行；旧行、DDL、删除和表外写入立即拒绝。"""
    def __init__(self, engine, baseline):
        self.engine, self.baseline = engine, baseline
        self.ids = {table: set() for table in LIMITS}
        self.failure = None

    def __enter__(self):
        event.listen(self.engine, "before_cursor_execute", self.before)
        event.listen(self.engine, "after_cursor_execute", self.after)
        return self

    def __exit__(self, *args):
        event.remove(self.engine, "before_cursor_execute", self.before)
        event.remove(self.engine, "after_cursor_execute", self.after)

    def before(self, connection, cursor, statement, parameters, context, executemany):
        try:
            self._before(connection, cursor, statement, parameters, context, executemany)
        except RuntimeError as exc:
            self.failure = str(exc)
            raise

    def _before(self, connection, cursor, statement, parameters, context, executemany):
        del cursor, parameters, executemany
        if statement.lstrip().upper().startswith(("SELECT ", "SHOW ", "SET ")):
            return
        match = WRITE_PATTERN.match(statement)
        require(match is not None, "unknown_write_rejected")
        verb, table = match.group(1).upper(), match.group(2)
        require(table in LIMITS and not verb.startswith("DELETE"), "table_or_delete_rejected")
        records = context.compiled_parameters or []
        require(bool(records), "unbound_write_rejected")
        if verb.startswith("INSERT"):
            cur = connection.connection.cursor()
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                require(int(cur.fetchone()[0]) - self.baseline["row_counts"][table] + len(records) <= LIMITS[table], "row_budget_exceeded")
            finally:
                cur.close()
            for row in records:
                if table == "projects":
                    require(row.get("owner_id") == 3 and row.get("name") == TAG, "wrong_project_fixture")
                elif table in {"workflows", "practice_sessions", "ai_requests"}:
                    require(row.get("project_id") in self.ids["projects"], "outside_new_project")
                elif table in {"workflow_nodes", "workflow_runs"}:
                    require(row.get("workflow_id") in self.ids["workflows"], "outside_new_workflow")
                elif table in {"practice_attempts", "practice_events"}:
                    require(row.get("session_id") in self.ids["practice_sessions"], "outside_new_session")
                elif table == "ai_results":
                    require(row.get("request_id") in self.ids["ai_requests"], "outside_new_request")
            return
        where = re.search(r"\bWHERE\s+`?" + re.escape(table) + r"`?\.`?id`?\s*=\s*%\((\w+)\)s\s*$", statement, re.I)
        if table == "workflow_nodes" and where is None:
            bulk = re.search(r"WHERE workflow_nodes.workflow_id = %\((\w+)\)s AND workflow_nodes.status = %\((\w+)\)s\s*$", statement)
            require(bulk is not None and all(row.get(bulk.group(1)) in self.ids["workflows"] for row in records), "bulk_outside_new_workflow")
            return
        require(where is not None, "update_requires_single_pk")
        require(all(row.get(where.group(1)) in self.ids[table] for row in records), "old_row_update_rejected")

    def after(self, connection, cursor, statement, parameters, context, executemany):
        del connection, parameters, executemany
        match = WRITE_PATTERN.match(statement)
        if not match or not match.group(1).upper().startswith("INSERT"):
            return
        table, rows = match.group(2), context.compiled_parameters or []
        if table in {"practice_sessions", "practice_attempts", "practice_events"}:
            self.ids[table].update(row["id"] for row in rows)
        else:
            require(len(rows) == 1, "auto_id_batch_insert_rejected")
            self.ids[table].add(rows[0].get("id") or cursor.lastrowid)


def application(engine, provider, readonly=False):
    factory = sessionmaker(engine, expire_on_commit=False)
    app = create_app()
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:4197"], allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Accept", "Authorization", "Content-Type"])

    def database_override():
        with factory() as session:
            yield session

    async def practice_override(session: Session = Depends(get_db_session)):
        yield build_service(session, provider)

    async def workflow_override(session: Session = Depends(get_db_session)):
        client = AIClient(provider, total_timeout_seconds=20, max_retries=0, retry_base_delay_seconds=0, max_retry_delay_seconds=0)
        registry = WorkflowAgentRegistry()
        registry.register("requirements_analysis", lambda tokens: RequirementsAnalysisWorkflowAgent(client, model="fake-s09", max_tokens=tokens, temperature=0))
        repository = WorkflowExecutionRepository(session)
        yield WorkflowService(WorkflowRepository(session), repository, WorkflowEngine(repository, registry, ContextManager(), WorkflowEngineLimits(2, 2, 1500, 4000, 30, 30)))

    def blocked_ai():
        raise HTTPException(403, "S09验收禁用收费与旧AI工具调用")

    app.dependency_overrides[get_db_session] = database_override
    app.dependency_overrides[get_practice_service] = practice_override
    app.dependency_overrides[get_workflow_execution_service] = workflow_override
    app.dependency_overrides[get_ai_service] = blocked_ai

    @app.middleware("http")
    async def narrow_requests(request, call_next):
        path = request.url.path.removeprefix("/api/v1")
        allowed = request.method in {"GET", "OPTIONS"} or (not readonly and (
            path == "/projects" or re.fullmatch(r"/projects/\d+/(context|practice-sessions)", path)
            or re.fullmatch(r"/practice-sessions/[a-f0-9-]+/(attempts|actions)", path)
            or path == "/workflows" or re.fullmatch(r"/workflows/\d+/(nodes|run)", path)
            or re.fullmatch(r"/workflows/\d+/nodes/\d+/context/write", path)))
        if not allowed:
            from starlette.responses import JSONResponse
            return JSONResponse({"error": {"message": "S09验收范围之外"}}, status_code=403)
        return await call_next(request)
    return app


def browser(mode, token, project_id, workflow_id, context_version=2, resume_first="", tail=False):
    environment = os.environ.copy()
    environment.update(S09_TOKEN=token, S09_PROJECT=str(project_id), S09_WORKFLOW=str(workflow_id),
                       S09_CONTEXT_VERSION=str(context_version),
                       S09_RESUME_FIRST_SESSION=resume_first,
                       S09_TAIL_ONLY="1" if tail else "0",
                       NODE_PATH=r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules")
    return subprocess.run(["node", str(ROOT / "frontend/scripts/verify-s09-ui.cjs"), mode], cwd=ROOT, env=environment,
                          capture_output=True, timeout=185).returncode


def api_call(client, method, path, payload=None):
    response = client.request(method, path, json=payload)
    require(response.is_success, f"fixture_api_{response.status_code}")
    return response.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--serve-readonly", action="store_true")
    parser.add_argument("--resume-partial", action="store_true")
    args = parser.parse_args()
    engine = existing_target_engine(DATABASE)
    if args.serve_readonly:
        @event.listens_for(engine, "before_cursor_execute")
        def read_only(connection, cursor, statement, parameters, context, executemany):
            require(statement.lstrip().upper().startswith(("SELECT ", "SHOW ", "SET ")), "restart_write_rejected")
        uvicorn.run(application(engine, FakeProvider(), True), host="127.0.0.1", port=PORT, access_log=False, log_level="critical")
        return
    baseline = snapshot(engine)
    require(len(baseline["tables"]) == 39, "table_count_changed")
    prior_rows = [row for row in baseline["rows"]["projects"].values() if row["name"] == TAG]
    prior = None
    if args.resume_partial:
        prior = json.loads((OUTPUT / "mysql-results.json").read_text(encoding="utf-8"))
        require(not prior["passed"] and prior.get("code") in {"fixture_api_500", "legacy_workflow_fake_failed", "real_browser_failed_see_results"} and prior["all_old_rows_preserved"], "partial_state_not_expected")
        expected_first = {"projects": 1, "workflows": 1, "workflow_nodes": 1, "workflow_runs": 2, "practice_sessions": 1, "practice_attempts": 1, "practice_events": 4, "ai_requests": 3, "ai_results": 2}
        expected_tail = {"projects": 1, "workflows": 1, "workflow_nodes": 1, "workflow_runs": 2, "practice_sessions": 4, "practice_attempts": 5, "practice_events": 31, "ai_requests": 8, "ai_results": 6}
        require(prior["deltas"] in ({table: int(table == "projects") for table in LIMITS}, {table: int(table in {"projects", "workflows", "workflow_nodes"}) for table in LIMITS}, {table: int(table in {"projects", "workflows", "workflow_nodes", "workflow_runs", "ai_requests"}) for table in LIMITS}, expected_first, expected_tail), "partial_rows_not_expected")
        require(len(prior_rows) == 1 and prior_rows[0]["owner_id"] == 3, "partial_project_not_expected")
        require(baseline["row_counts"] == prior["final_counts"], "partial_counts_changed")
        archive = next((OUTPUT / f"mysql-attempt-{number:02}.json" for number in range(1, 10) if not (OUTPUT / f"mysql-attempt-{number:02}.json").exists()), None)
        require(archive is not None, "failure_archive_limit")
        archive.write_text(safe_json(prior), encoding="utf-8")
    else:
        require(not prior_rows, "existing_tag_requires_manual_inspection")
    plan = {"run_id": TAG, "target": f"127.0.0.1:3306/{DATABASE}", "initial_counts": baseline["row_counts"], "limits": LIMITS,
            "real_model_calls": 0, "new_fees": 0, "scope": "新专用项目/Context、旧WorkflowRun Fake、实践四路径、浏览器与实际只读进程重启；不改旧行、不DDL/DELETE"}
    protected = baseline
    if prior:
        plan["initial_counts"] = prior["initial_counts"]
        plan["resume_partial_project_id"] = prior_rows[0]["id"]
        # 仅放行本轮上次已创建的专用项目，其余所有当前行仍逐值保护。
        project_id = prior_rows[0]["id"]
        resume_ids = {table: set() for table in LIMITS}
        resume_ids["projects"].add(project_id)
        resume_ids["workflows"] = {row["id"] for row in baseline["rows"]["workflows"].values() if row["project_id"] == project_id}
        resume_ids["workflow_nodes"] = {row["id"] for row in baseline["rows"]["workflow_nodes"].values() if row["workflow_id"] in resume_ids["workflows"]}
        resume_ids["workflow_runs"] = {row["id"] for row in baseline["rows"]["workflow_runs"].values() if row["workflow_id"] in resume_ids["workflows"]}
        resume_ids["ai_requests"] = {row["id"] for row in baseline["rows"]["ai_requests"].values() if row["project_id"] == project_id}
        resume_ids["ai_results"] = {row["id"] for row in baseline["rows"]["ai_results"].values() if row["request_id"] in resume_ids["ai_requests"]}
        resume_ids["practice_sessions"] = {row["id"] for row in baseline["rows"]["practice_sessions"].values() if row["project_id"] == project_id}
        for table in ("practice_attempts", "practice_events"):
            resume_ids[table] = {row["id"] for row in baseline["rows"][table].values() if row["session_id"] in resume_ids["practice_sessions"]}
        require(all(len(resume_ids[table]) == prior["deltas"][table] for table in LIMITS), "partial_id_scope_mismatch")
        protected = {**baseline, "rows": {table: {key: row for key, row in rows.items() if table not in resume_ids or row["id"] not in resume_ids[table]} for table, rows in baseline["rows"].items()}}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "database-plan.json").write_text(safe_json(plan), encoding="utf-8")
    if not args.apply and not args.resume_partial:
        print(safe_json({"dryrun": True, **plan})); return
    with socket.socket() as check:
        require(check.connect_ex(("127.0.0.1", PORT)) != 0, "test_port_in_use")
    with engine.connect() as connection:
        auth_version = connection.scalar(text("SELECT auth_version FROM users WHERE id=3 AND is_active=1"))
        require(auth_version is not None, "owner_fixture_missing")
    token = SecurityService(get_security_settings()).create_access_token(3, auth_version).value
    provider = FakeProvider()
    server = uvicorn.Server(uvicorn.Config(application(engine, provider), host="127.0.0.1", port=PORT, access_log=False, log_level="critical"))
    thread = threading.Thread(target=server.run, daemon=True)
    child = None
    try:
        with Guard(engine, {**baseline, "row_counts": plan["initial_counts"]}) as guard:
            if prior: guard.ids = resume_ids
            thread.start()
            for _ in range(50):
                if server.started: break
                time.sleep(.1)
            require(server.started, "api_start_failed")
            with httpx.Client(base_url=f"http://127.0.0.1:{PORT}/api/v1", headers={"Authorization": "Bearer " + token}, timeout=40) as client:
                project = api_call(client, "GET", f"/projects/{prior_rows[0]['id']}") if prior else api_call(client, "POST", "/projects", {"name": TAG, "description": "S09隔离UI工程样例；模型全部Fake。", "difficulty": "beginner", "language": "Python", "output_requirement": "提交纯函数与可选自测记录"})
                if not prior or prior_rows[0]["context_data"] is None: api_call(client, "POST", f"/projects/{project['id']}/context")
                workflow = api_call(client, "GET", f"/workflows/{next(iter(guard.ids['workflows']))}") if guard.ids["workflows"] else api_call(client, "POST", "/workflows", {"project_id": project["id"], "name": "S09旧工作流兼容Fake", "description": "真实接口与Fake节点，不代表模型质量", "status": "draft"})
                if not guard.ids["workflow_nodes"]: api_call(client, "POST", f"/workflows/{workflow['id']}/nodes", {"node_key": "requirements", "node_type": "requirements_analysis", "name": "Fake需求", "position_x": 0, "position_y": 0, "config": None})
                detail = api_call(client, "GET", f"/workflows/{workflow['id']}")
                old_runs = [row for row in baseline["rows"]["workflow_runs"].values() if row["workflow_id"] == workflow["id"] and row["status"] == "completed"]
                run = api_call(client, "GET", f"/workflows/{workflow['id']}/runs/{old_runs[0]['id']}") if old_runs else api_call(client, "POST", f"/workflows/{workflow['id']}/run", {"expected_version": detail["version"], "mode": "all"})
                require(run["status"] == "completed", "legacy_workflow_fake_failed")
                plan.update(project_id=project["id"], workflow_id=workflow["id"], workflow_run_id=run["id"])
                (OUTPUT / "database-plan.json").write_text(safe_json(plan), encoding="utf-8")
                context = api_call(client, "GET", f"/projects/{project['id']}/context")
                resume_first = next(iter(resume_ids["practice_sessions"]), "") if prior else ""
                tail = prior is not None and prior["deltas"] == expected_tail
                require(browser("real", token, project["id"], workflow["id"], context["version"], resume_first, tail) == 0, "real_browser_failed_see_results")
            plan["new_ids"] = {table: sorted(ids, key=str) for table, ids in guard.ids.items()}
        server.should_exit = True; thread.join(10); require(not thread.is_alive(), "api_stop_failed")
        # 真正新进程、只读引擎，浏览器刷新读取同一持久attempt。不会重复模型请求。
        child = subprocess.Popen([sys.executable, "-B", "-X", "utf8", "-m", "scripts.verify_s09_student_ui", "--serve-readonly"], cwd=ROOT / "backend", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        with httpx.Client(timeout=1) as probe:
            for _ in range(80):
                try:
                    if probe.get(f"http://127.0.0.1:{PORT}/api/v1/health").is_success: break
                except httpx.HTTPError: pass
                time.sleep(.1)
            else: require(False, "restart_start_failed")
        require(browser("restart", token, project["id"], workflow["id"]) == 0, "restart_browser_failed_see_results")
        plan.update(passed=True, fake_calls_this_process=provider.calls, restart_process_id=child.pid)
    except Exception as exc:
        plan.update(passed=False, failure=type(exc).__name__, code=str(exc) if isinstance(exc, RuntimeError) else "see_bounded_check")
    finally:
        if 'guard' in locals():
            plan["guard_failure"] = guard.failure
            plan["new_ids"] = {table: sorted(ids, key=str) for table, ids in guard.ids.items()}
        server.should_exit = True
        if thread.is_alive(): thread.join(10)
        if child:
            child.terminate(); child.wait(timeout=10)
        final = snapshot(engine)
        plan["final_counts"] = final["row_counts"]
        plan["deltas"] = {table: final["row_counts"][table] - plan["initial_counts"][table] for table in LIMITS}
        plan["all_old_rows_preserved"] = all(all(final["rows"][table].get(identity) == value for identity, value in rows.items()) for table, rows in protected["rows"].items())
        plan["outside_tables_unchanged"] = all(final["row_counts"][table] == count for table, count in baseline["row_counts"].items() if table not in LIMITS)
        plan["within_limits"] = all(0 <= count <= LIMITS[table] for table, count in plan["deltas"].items())
        requests = [row for row in final["rows"]["ai_requests"].values() if row["project_id"] == plan.get("project_id")]
        plan["all_requests_fake"] = bool(requests) and all(row["provider"] == "fake" for row in requests)
        plan["fake_calls"] = len(requests)
        plan["cleanup"] = {"temporary_api_stopped": not thread.is_alive(), "restart_process_stopped": child is None or child.poll() is not None, "fixtures_retained": True, "ddl": 0, "deletes": 0}
        plan["passed"] = bool(plan.get("passed") and plan["all_old_rows_preserved"] and plan["outside_tables_unchanged"] and plan["within_limits"])
        (OUTPUT / "mysql-results.json").write_text(safe_json(plan), encoding="utf-8")
        engine.dispose()
    print(safe_json({key: plan.get(key) for key in ("passed", "code", "deltas", "fake_calls", "all_old_rows_preserved", "cleanup")}))
    if not plan["passed"]: sys.exit(1)


if __name__ == "__main__":
    main()
