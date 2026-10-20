"""S05 收尾：真实认证/隔离 MySQL GET、结构检查和发布重放，不创建新对象。"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path
from secrets import token_urlsafe
from unittest.mock import patch

import httpx
from sqlalchemy import event, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings, get_security_settings
from app.core.database import get_engine, get_session_factory

root = Path.cwd().parent
evidence = root / "开发相关文档/阶段报告/AI大数据改造/V2/S05-验证证据"
temporary = Path(os.environ["TEMP"]) / "ScholarHub-S05-20261020"
database = "scholarhub_l4_s02_20261020"
configured = make_url(get_settings().database_url)
assert configured.host in ("localhost", "127.0.0.1")
assert (configured.port or 3306) == 3306
assert configured.database != database
os.environ["DATABASE_URL"] = configured.set(database=database).render_as_string(hide_password=False)
os.environ["JWT_SECRET"] = token_urlsafe(48)
get_settings.cache_clear()
get_security_settings.cache_clear()
get_engine.cache_clear()
get_session_factory.cache_clear()

from app.core.security import SecurityService
from app.main import create_app
from app.models import Base
from app.models.analytics import AnalyticsBatch, AnalyticsDailyMetric
from app.models.user import User
from app.services.analytics import AnalyticsService

engine = get_engine()
app = create_app()
headers = {}
events = []
get_dml = []
monitor = {"enabled": False}


def save(name, data):
    (evidence / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )


@event.listens_for(engine, "before_cursor_execute")
def track(connection, cursor, statement, parameters, context, executemany):
    verb = statement.strip().split()[0].upper()
    if monitor["enabled"] and verb not in ("SELECT", "SHOW", "DESCRIBE", "EXPLAIN", "SET"):
        get_dml.append(verb)


with Session(engine) as session:
    before = [session.scalar(select(func.count()).select_from(model)) for model in (AnalyticsBatch, AnalyticsDailyMetric)]
    for uid in (3, 4):
        user = session.get(User, uid)
        assert user.username.startswith("s02_3e08a80a_")
        headers[uid] = {"Authorization": "Bearer " + SecurityService(get_security_settings()).create_access_token(uid, user.auth_version).value}
    main = session.scalar(select(AnalyticsBatch).where(AnalyticsBatch.artifact_ref == "s03-owner3-restored/v2-controlled"))
    empty = session.scalar(select(AnalyticsBatch).where(AnalyticsBatch.artifact_ref == "s05-permission-empty/s05-empty-permission-fixture"))
    main_id, empty_id = main.batch_id, empty.batch_id


async def get(path, uid=3, status=200, reason=None):
    monitor["enabled"] = True
    try:
        with patch("subprocess.Popen", side_effect=AssertionError("GET started a process")) as spawn, patch("app.ai.client.AIClient.complete", side_effect=AssertionError("GET called a model")) as model, patch.object(AnalyticsService, "publish", side_effect=AssertionError("GET published")) as publisher:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://s05-isolated") as client:
                response = await client.get("/api/v1" + path, headers=headers.get(uid, {}))
            counts = [spawn.call_count, model.call_count, publisher.call_count]
            assert counts == [0, 0, 0]
    finally:
        monitor["enabled"] = False
    body = response.json()
    assert response.status_code == status, (path, response.status_code)
    if reason is not None:
        assert body["empty_reason"] == reason
    events.append({"path": path, "identity": uid, "status": response.status_code, "response": body, "process_model_publish_calls": counts})
    return body


async def readonly():
    await get("/offline-analytics/batches", reason="no_completed_batch")
    await get("/offline-analytics/batches?dataset_kind=controlled&period_start=2025-01-01&period_end=2025-01-02", reason="no_matching_batch")
    await get("/offline-analytics/batches?dataset_kind=controlled&page=999", reason="page_empty")
    listed = await get("/offline-analytics/batches?dataset_kind=controlled")
    assert listed["empty_reason"] is None
    assert str(main_id) in [item["batch_id"] for item in listed["items"]]
    detail = await get("/offline-analytics/batches/" + main_id)
    assert detail["records_summary"]["known_minutes"] == 75
    await get("/offline-analytics/batches/" + main_id, uid=4, status=404)
    zero = await get("/offline-analytics/batches/" + empty_id)
    assert zero["daily"] == [] and zero["tasks_summary"]["completion_rate"]["percent"] is None
    await get("/offline-analytics/batches/" + empty_id, uid=4, status=404)
    await get("/offline-analytics/batches/" + empty_id, uid=None, status=401)


asyncio.run(readonly())
assert get_dml == []
save("final-readonly-api.json", {"status": "passed", "requests": events, "GET_DML": get_dml, "credential_values_saved": False})

# 进程环境仅指向本轮授权库；命令不得打印连接串或秘密。
commands = [
    ("migration-replay.log", [sys.executable, "-B", "-X", "utf8", "-m", "scripts.apply_s05_analytics_migration", "--database", database]),
    ("schema-final.log", [sys.executable, "-B", "-X", "utf8", "-m", "scripts.verify_database_schema"]),
    ("publish-replay.log", [sys.executable, "-B", "-X", "utf8", "-m", "scripts.publish_analytics", "--database", database, "--job-id", "v2-controlled"]),
]
results = []
for name, command in commands:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    (temporary / name).write_text(completed.stdout + completed.stderr, encoding="utf-8")
    assert completed.returncode == 0, name
    if name == "publish-replay.log":
        replay = json.loads(completed.stdout)
        assert replay["batch_id"] == main_id and replay["replayed"] is True
    results.append({"command": command, "exit_code": completed.returncode, "log": name})

with Session(engine) as session:
    source_counts = {name: session.scalar(select(func.count()).select_from(table)) for name, table in Base.metadata.tables.items() if not name.startswith("analytics_")}
    original_counts = json.loads((evidence / "source-counts-before.json").read_text(encoding="utf-8"))
    assert source_counts == original_counts
    after = [session.scalar(select(func.count()).select_from(model)) for model in (AnalyticsBatch, AnalyticsDailyMetric)]
    assert after == before == [11, 15]
    assert after[0] <= 12 and after[1] <= 40
    batches = [
        {"batch_id": row.batch_id, "owner_user_id": row.owner_user_id, "state": row.state, "dataset_kind": row.dataset_kind, "artifact_ref": row.artifact_ref, "quality": row.quality, "daily_rows": session.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id == row.batch_id))}
        for row in session.scalars(select(AnalyticsBatch).order_by(AnalyticsBatch.created_at, AnalyticsBatch.batch_id))
    ]
save("final-state.json", {
    "verified_at": datetime.now(UTC).isoformat(), "target": {"host": "127.0.0.1", "port": 3306, "database": database},
    "tables": len(inspect(engine).get_table_names()), "before_final_checks": before, "after_final_checks": after,
    "analytics_counts": {"batches": after[0], "daily_rows": after[1]}, "limit": {"batches": 12, "daily_rows": 40},
    "source_counts_unchanged": True, "source_counts": source_counts, "retained_batches": batches,
    "commands": results, "readonly_requests": len(events), "GET_DML": get_dml,
    "service_configuration_changed": False, "new_batch_or_daily_created_in_final_checks": False,
})
engine.dispose()
print(json.dumps({"status": "passed", "requests": len(events), "source_tables_unchanged": len(source_counts), "batches": after[0], "daily_rows": after[1], "GET_DML": get_dml}))
