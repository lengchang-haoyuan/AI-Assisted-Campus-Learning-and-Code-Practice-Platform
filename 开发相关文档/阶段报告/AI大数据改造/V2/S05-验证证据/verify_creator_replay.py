"""强制首次创建者让出执行顺序，验证双方都不携带过期RR快照。"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_database_engine
from app.models.analytics import AnalyticsBatch, AnalyticsDailyMetric
from app.repositories.analytics import AnalyticsRepository
from app.services.analytics import AnalyticsService
from app.services.analytics_artifacts import load_publication

url = make_url(get_settings().database_url)
assert url.host in ("127.0.0.1", "localhost") and (url.port or 3306) == 3306
engine = create_database_engine(url.set(database="scholarhub_l4_s02_20261020").render_as_string(hide_password=False))
payload = load_publication("v2-controlled").model_copy(deep=True)
payload.job_id = "s05-creator-yields-v4"
payload.quality["transaction_fixture"] = True
reserved, second_done = Event(), Event()


class YieldingCreatorRepository(AnalyticsRepository):
    def reserve(self, values):
        identity = super().reserve(values)
        reserved.set()
        assert second_done.wait(10)
        return identity


def worker(creator):
    with engine.connect() as connection:
        connection_id = connection.exec_driver_sql("SELECT CONNECTION_ID()").scalar_one()
        connection.commit()
        with Session(bind=connection) as session:
            if not creator:
                assert reserved.wait(10)
            repository = YieldingCreatorRepository(session) if creator else AnalyticsRepository(session)
            result = AnalyticsService(repository).publish(payload)
            if not creator:
                second_done.set()
            return {"connection_id": connection_id, "batch_id": result[0], "replayed": result[1]}


with ThreadPoolExecutor(max_workers=2) as pool:
    first = pool.submit(worker, True)
    second = pool.submit(worker, False)
    results = [first.result(timeout=30), second.result(timeout=30)]
assert len({item["connection_id"] for item in results}) == 2
assert len({item["batch_id"] for item in results}) == 1
assert [item["replayed"] for item in results] == [True, False]
with Session(engine) as session:
    daily_rows = session.scalar(select(func.count()).select_from(AnalyticsDailyMetric).where(AnalyticsDailyMetric.batch_id == results[0]["batch_id"]))
    assert daily_rows == 2
    counts = {"batches": session.scalar(select(func.count()).select_from(AnalyticsBatch)), "daily_rows": session.scalar(select(func.count()).select_from(AnalyticsDailyMetric))}
    assert counts == {"batches": 11, "daily_rows": 15}
evidence = Path("../开发相关文档/阶段报告/AI大数据改造/V2/S05-验证证据")
(evidence / "creator-replay.json").write_text(json.dumps({"status": "passed", "first_creator_waited_for_second_publication": True, "held_connections": results, "daily_rows": daily_rows, "counts": counts}, indent=2), encoding="utf-8")
print(json.dumps({"status": "passed", "held_connections": results, "counts": counts}))
engine.dispose()
