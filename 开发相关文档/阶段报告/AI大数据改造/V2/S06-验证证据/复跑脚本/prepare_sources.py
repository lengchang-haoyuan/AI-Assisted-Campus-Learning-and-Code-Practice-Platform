"""仅本轮明确批准目标的S06来源准备；不启动模型/Spark，不创建账号。"""

import asyncio
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from unittest.mock import patch

import httpx
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings, get_security_settings
from app.core.database import get_engine, get_session_factory

root = Path.cwd().parent
v2 = root / "开发相关文档/阶段报告/AI大数据改造/V2"
evidence = v2 / "S06-验证证据"
evidence.mkdir(parents=True, exist_ok=True)
database = "scholarhub_l4_s02_20261020"
configured = make_url(get_settings().database_url)
assert configured.host in ("127.0.0.1", "localhost") and (configured.port or 3306) == 3306
os.environ["DATABASE_URL"] = configured.set(database=database).render_as_string(hide_password=False)
os.environ["JWT_SECRET"] = token_urlsafe(48)
get_settings.cache_clear()
get_security_settings.cache_clear()
get_engine.cache_clear()
get_session_factory.cache_clear()

from app.core.security import SecurityService
from app.main import create_app
from app.models import Base
from app.models.user import User
from app.models.learning import LearningRecord
from analytics.snapshot_files import read_snapshot
from scripts.export_ods_snapshot import export_snapshot


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


engine = get_engine()
headers = {}
with Session(engine) as session:
    counts = {name: session.scalar(select(func.count()).select_from(table)) for name, table in Base.metadata.tables.items()}
    resuming = (evidence / "source-object.json").exists()
    assert counts["learning_records"] == (5 if resuming else 4) and counts["analytics_batches"] == 11 and counts["analytics_daily_metrics"] == 15
    if resuming:
        saved = json.loads((evidence / "source-object.json").read_text(encoding="utf-8"))
        existing = session.get(LearningRecord, saved["record_id"])
        assert existing.user_id == 3 and existing.duration_minutes == 15 and existing.record_metadata.get("verification") == "S06-20261021"
    for uid in (3, 4):
        user = session.get(User, uid)
        assert user.is_active and user.username.startswith("s02_3e08a80a_")
        headers[uid] = {"Authorization": "Bearer " + SecurityService(get_security_settings()).create_access_token(uid, user.auth_version).value}
baseline = {
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "target": {"host": "127.0.0.1", "port": 3306, "database": database}, "tables": len(inspect(engine).get_table_names()),
    "counts": counts, "preserve_local_only": [".rivet/", "tmp/"], "baseline_tracked_changes_before_S06": [],
}
if not (evidence / "baseline.json").exists():
    save(evidence / "baseline.json", baseline)
authorization = {
    "stage": "S06", "recorded_at": datetime.now(UTC).isoformat(),
    "user_reply": "批准本轮隔离验证与按标记清理（推荐）", "database": database,
    "source_record_limit": 1, "source_duration_minutes": 15, "new_batch_limit": 3, "new_daily_row_limit": 8,
    "scope": "new S06-tagged ordinary record via existing API; delete only new ID after snapshot/display; preserve originals and completed history; register two independently validated offline jobs",
    "evaluation_reply": "保持零调用，J1待评分，完整验收暂不宣称通过（推荐）",
    "real_model_calls_authorized": 0, "S06_formal_J1": "pending_not_run", "S06_full_acceptance": "not_claimed",
}
if not (evidence / "authorization.json").exists():
    save(evidence / "authorization.json", authorization)
app = create_app()
api_events = []
started = time.perf_counter()


async def prepare():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://s06-isolated") as client:
        body = {"title": "S06-20261021-15分钟隔离来源", "record_type": "study", "duration_minutes": 15,
                "occurred_at": "2026-10-20T04:00:00Z", "record_metadata": {"verification": "S06-20261021"}}
        if (evidence / "source-object.json").exists():
            saved = json.loads((evidence / "source-object.json").read_text(encoding="utf-8"))
            value = {"id": saved["record_id"]}
            api_events.append({"origin": "reused_API_POST_201_from_first_attempt", "raw_log": "prepare-sources.log", "record_id": value["id"]})
        else:
            response = await client.post("/api/v1/learning/records", headers=headers[3], json=body)
            assert response.status_code == 201, response.status_code
            value = response.json()
            safe = {key: value[key] for key in ("id", "record_type", "duration_minutes", "occurred_at")}
            api_events.append({"method": "POST", "path": "/api/v1/learning/records", "identity": 3, "status": 201, "safe_response": safe})
            save(evidence / "source-object.json", {"owner_user_id": 3, "record_id": value["id"], "marker": "S06-20261021", "duration_minutes": 15, "cleanup": "pending_after_browser"})
        for path in ("/learning/records/" + str(value["id"]), "/learning/tasks?page=1&page_size=10", "/campus/submissions/1", "/campus/submissions/2", "/campus/submissions/3", "/campus/submissions/1/versions"):
            result = await client.get("/api/v1" + path, headers=headers[3])
            assert result.status_code == 200, (path, result.status_code)
            data = result.json()
            # 保留状态/关联定位；不输出正文、仓库内容或认证值。
            summary = {key: data[key] for key in ("id", "status", "revision", "latest_version_number", "duration_minutes") if key in data}
            if "items" in data:
                summary["total"] = data["total"]
                if path.endswith("/versions"):
                    summary["versions"] = [{"version_number": row["version_number"], "status": row["status"], "feedback_decision": row["feedback"]["decision"] if row["feedback"] else None} for row in data["items"]]
            if "latest_version" in data:
                summary["latest_status"] = data["latest_version"]["status"]
            api_events.append({"method": "GET", "path": path, "identity": 3, "status": 200, "safe_response": summary})
with patch("app.ai.client.AIClient.complete", side_effect=AssertionError("S06 forbids model calls")) as model:
    asyncio.run(prepare())
    assert model.call_count == 0
save(evidence / "source-api.json", {"status": "passed", "events": api_events, "model_calls": 0, "seconds": time.perf_counter() - started})

snapshots = []
for uid, name in ((3, "s06-e2e-owner3-20261021"), (4, "s06-e2e-owner4-20261021")):
    before = time.perf_counter()
    path = v2 / "S06-ODS/snapshots" / name
    if path.exists():
        manifest, _tables = read_snapshot(path)
    else:
        path, manifest = export_snapshot(engine, v2 / "S06-ODS", name, uid, "2026-10-19", "2026-10-20", include_ai=True)
    snapshots.append({"owner_user_id": uid, "snapshot_id": name, "path": path.relative_to(v2).as_posix(), "source_cutoff": manifest["source_cutoff"], "seconds": time.perf_counter() - before, "row_counts": manifest["row_counts"]})
save(v2 / "S06-输入索引.json", {"controlled_snapshots": snapshots, "model_calls": 0, "original_sources_preserved": True})
save(evidence / "source-timings.json", {"source_api_and_snapshot_seconds": time.perf_counter() - started, "snapshots": snapshots})
engine.dispose()
print(json.dumps({"status": "prepared", "new_records": 1, "snapshots": [row["snapshot_id"] for row in snapshots], "model_calls": 0}))
