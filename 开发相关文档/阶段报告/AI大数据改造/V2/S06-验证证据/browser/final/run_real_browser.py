"""真实FastAPI认证/MySQL+浏览器验证；配置、令牌仅在独立进程内。"""

import contextvars
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from secrets import token_urlsafe

import httpx
import uvicorn
from sqlalchemy import event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings, get_security_settings
from app.core.database import get_engine, get_session_factory

root = Path.cwd().parent
v2 = root / "开发相关文档/阶段报告/AI大数据改造/V2"
temporary = Path(os.environ["TEMP"]) / "ScholarHub-S06-20261021"
round_name = os.environ.get("S06_BROWSER_ROUND", "round1")
evidence = v2 / "S06-验证证据/browser" / round_name
evidence.mkdir(parents=True, exist_ok=True)
url = make_url(get_settings().database_url)
assert url.host in ("localhost", "127.0.0.1") and (url.port or 3306) == 3306
os.environ["DATABASE_URL"] = url.set(database="scholarhub_l4_s02_20261020").render_as_string(hide_password=False)
os.environ["JWT_SECRET"] = token_urlsafe(48)
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:5176"
get_settings.cache_clear()
get_security_settings.cache_clear()
get_engine.cache_clear()
get_session_factory.cache_clear()
from app.core.security import SecurityService
from app.main import create_app
from app.models import Base
from app.models.user import User
from app.services.analytics import AnalyticsService
from app.ai.client import AIClient

engine = get_engine()
app = create_app()
method = contextvars.ContextVar("s06_http_method", default="")
counters = {"GET_DML": [], "GET_process_calls": 0, "GET_publish_calls": 0, "model_calls": 0, "requests": []}


@event.listens_for(engine, "before_cursor_execute")
def track(connection, cursor, statement, parameters, context, many):
    verb = statement.strip().split()[0].upper()
    if method.get() == "GET" and verb in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}:
        counters["GET_DML"].append(verb)


@app.middleware("http")
async def monitor(request, call_next):
    token = method.set(request.method)
    try:
        response = await call_next(request)
        counters["requests"].append({"method": request.method, "path": request.url.path, "status": response.status_code})
        return response
    finally:
        method.reset(token)


original_popen = subprocess.Popen
original_publish = AnalyticsService.publish


def guard_popen(*arguments, **keywords):
    if method.get() == "GET":
        counters["GET_process_calls"] += 1
        raise AssertionError("GET attempted a process")
    return original_popen(*arguments, **keywords)


def guard_publish(self, *arguments, **keywords):
    if method.get() == "GET":
        counters["GET_publish_calls"] += 1
        raise AssertionError("GET attempted publication")
    return original_publish(self, *arguments, **keywords)


async def guard_model(*arguments, **keywords):
    counters["model_calls"] += 1
    raise AssertionError("S06 forbids model calls")


subprocess.Popen = guard_popen
AnalyticsService.publish = guard_publish
AIClient.complete = guard_model
environment = dict(os.environ)
with Session(engine) as session:
    before = {name: session.scalar(select(func.count()).select_from(table)) for name, table in Base.metadata.tables.items()}
    for uid in (3, 4):
        user = session.get(User, uid)
        assert user.username.startswith("s02_3e08a80a_")
        environment["S06_TEST_TOKEN" + str(uid)] = SecurityService(get_security_settings()).create_access_token(uid, user.auth_version).value
environment["NODE_PATH"] = r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
environment["S06_EVIDENCE"] = str(evidence)
environment["S06_BROWSER_ROUND"] = round_name
environment["VITE_API_BASE_URL"] = "http://127.0.0.1:8016/api/v1"
environment["SCHOLARHUB_BROWSER_PATH"] = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
for port in (8016, 5176):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8016, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
frontend = None
with (evidence / "frontend-server.log").open("w", encoding="utf-8") as log:
    try:
        frontend = subprocess.Popen(["node", str(root / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "5176", "--strictPort"], cwd=root / "frontend", env=environment, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        for attempt in range(100):
            try:
                if server.started and httpx.get("http://127.0.0.1:5176", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        else:
            raise AssertionError("isolated servers did not start")
        result = subprocess.run(["node", str(temporary / "verify-real-browser.cjs")], cwd=root, env=environment, capture_output=True, text=True, encoding="utf-8")
        (evidence / "browser.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        assert result.returncode == 0, "browser verification failed; see safe browser.log"
    finally:
        if frontend is not None:
            frontend.terminate()
            frontend.wait(timeout=10)
        server.should_exit = True
        thread.join(timeout=10)
        with Session(engine) as session:
            after = {name: session.scalar(select(func.count()).select_from(table)) for name, table in Base.metadata.tables.items()}
        (evidence / "server-observation.json").write_text(json.dumps({**counters, "all_table_counts_before": before, "all_table_counts_after": after, "row_counts_unchanged": before == after, "transmission": "real TCP HTTP to FastAPI + real authenticated MySQL; no API response interception", "servers_stopped": not thread.is_alive()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        engine.dispose()
assert before == after
assert counters["GET_DML"] == [] and counters["GET_process_calls"] == counters["GET_publish_calls"] == counters["model_calls"] == 0
print(json.dumps({"status": "passed", "round": round_name, "real_HTTP_requests": len(counters["requests"]), "GET_DML": [], "model_calls": 0, "servers_stopped": True}))
