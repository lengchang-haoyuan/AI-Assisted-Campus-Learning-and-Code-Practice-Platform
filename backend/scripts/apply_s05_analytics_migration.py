"""只对本轮明确授权隔离目标执行增量两表DDL。"""

import argparse
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.database import create_database_engine
from scripts.verify_database_schema import verify_table

TABLES={"analytics_batches","analytics_daily_metrics"}
MIGRATION=Path(__file__).resolve().parents[1]/"migrations/20261020_s05_offline_analytics.sql"


def apply(engine):
    if engine.url.database!="scholarhub_l4_s02_20261020" or engine.url.host not in ("127.0.0.1","localhost") or (engine.url.port or 3306)!=3306:
        raise ValueError("unauthorized_migration_target")
    present=TABLES & set(inspect(engine).get_table_names())
    if present and present!=TABLES:
        raise ValueError("partial_migration_requires_inspection")
    if not present:
        sql="\n".join(line for line in MIGRATION.read_text(encoding="utf-8").splitlines() if not line.startswith("--"))
        with engine.connect() as connection:
            for statement in sql.split(";"):
                if statement.strip():connection.exec_driver_sql(statement)
            connection.commit()
    errors=[error for table in sorted(TABLES) for error in verify_table(inspect(engine),table)]
    for table in TABLES:
        column=next(c for c in inspect(engine).get_columns(table) if c["name"]=="batch_id")
        if str(column["type"])!="CHAR(36)":errors.append("batch_id_type_mismatch")
    if errors:raise ValueError("analytics_schema_mismatch")
    return "already_applied" if present else "applied"


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--database",required=True)
    args=parser.parse_args()
    if args.database!="scholarhub_l4_s02_20261020":parser.error("目标未授权")
    url=make_url(get_settings().database_url).set(database=args.database)
    engine=create_database_engine(url.render_as_string(hide_password=False))
    try:print(apply(engine))
    finally:engine.dispose()


if __name__=="__main__":main()
