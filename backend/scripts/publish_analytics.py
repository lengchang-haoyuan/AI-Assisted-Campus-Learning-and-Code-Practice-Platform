"""受控离线发布，不接受任意产物路径，不启动Spark。"""

import argparse
import json

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_database_engine
from app.repositories.analytics import AnalyticsRepository
from app.services.analytics import AnalyticsService
from app.services.analytics_artifacts import load_publication


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",required=True)
    parser.add_argument("--job-id",required=True)
    args=parser.parse_args()
    url=make_url(get_settings().database_url)
    if args.database!="scholarhub_l4_s02_20261020" or url.host not in ("127.0.0.1","localhost") or (url.port or 3306)!=3306:
        parser.error("本轮仅允许已确认隔离库；其他目标须另有授权")
    payload=load_publication(args.job_id)
    engine=create_database_engine(url.set(database=args.database).render_as_string(hide_password=False))
    try:
        with Session(engine) as session:
            batch_id,replayed=AnalyticsService(AnalyticsRepository(session)).publish(payload)
        print(json.dumps({"batch_id":batch_id,"job_id":args.job_id,"state":"completed","replayed":replayed}))
    finally:engine.dispose()


if __name__=="__main__":main()
