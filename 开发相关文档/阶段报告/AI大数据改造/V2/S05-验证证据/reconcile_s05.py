"""逐字段对照冻结答案、Spark ADS、发布载荷、真实表和已保存API返回。"""

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_database_engine
from app.models.analytics import AnalyticsBatch, AnalyticsDailyMetric
from app.schemas.analytics import DailyMetric

v2 = Path.cwd().parent / "开发相关文档/阶段报告/AI大数据改造/V2"
evidence = v2 / "S05-验证证据"
url = make_url(get_settings().database_url)
assert url.host in ("127.0.0.1", "localhost") and (url.port or 3306) == 3306
engine = create_database_engine(url.set(database="scholarhub_l4_s02_20261020").render_as_string(hide_password=False))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


main_api = next(item["response"] for item in load(evidence / "final-readonly-api.json")["requests"] if item["status"] == 200 and item["response"].get("source", {}).get("job_id") == "v2-controlled")
boundary_api = next(item["response"] for item in load(evidence / "api-evidence.json") if item["status"] == 200 and item["response"].get("source", {}).get("job_id") == "v1-boundary")
layers = []
with Session(engine) as session:
    for job, uid, api in [("v2-controlled", 3, main_api), ("v1-boundary", 4, boundary_api)]:
        payload = load(v2 / "S05-发布输入" / job / "payload.json")
        ads = load(v2 / "S04-产物/jobs" / job / "ads/answers.json")[str(uid)]
        batch = session.get(AnalyticsBatch, api["batch_id"])
        assert batch.owner_user_id == uid and batch.state == "completed"
        daily = [DailyMetric.model_validate({key: getattr(row, key) for key in DailyMetric.model_fields}).model_dump(mode="json") for row in session.scalars(select(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id == batch.batch_id).order_by(AnalyticsDailyMetric.metric_date))]
        for key, ads_key in [("records_summary", "records"), ("tasks_summary", "tasks"), ("topic_summary", "topic")]:
            stored = batch.topic_summary if key == "topic_summary" else batch.input_counts[key]
            assert stored == ads[ads_key] == payload[key] == api[key], (job, key)
        assert daily == payload["daily"] == api["daily"]
        totals = {key: sum(row[key] for row in daily) for key in DailyMetric.model_fields if key != "metric_date"}
        if uid == 3:
            expected = load(evidence / "hand-ADS-storage-API.json")["expected"]
            assert [totals[key] for key in ("known_minutes", "missing_duration_count", "completed", "task_total", "cohort_count", "revised_count", "confirmed_count")] == list(expected.values())
        else:
            expected = {"completed": 199, "task_total": 200, "completion_rate_percent": "99.500000"}
            assert totals["completed"] == 199 and totals["task_total"] == 200
            assert batch.input_counts["tasks_summary"]["completion_rate"]["percent"] == "99.500000"
        layers.append({"job_id": job, "batch_id": batch.batch_id, "owner_user_id": uid, "frozen_expected": expected, "summary_fields_equal_ADS_payload_storage_API": True, "daily_fields_equal_payload_storage_API": True, "stored_daily": daily, "stored_daily_totals": totals})
(evidence / "four-layer-reconciliation.json").write_text(json.dumps({"status": "passed", "data_queries_only": True, "layers": layers}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
engine.dispose()
print(json.dumps({"status": "passed", "jobs": len(layers), "summary_and_daily_fields_matched": True}))
