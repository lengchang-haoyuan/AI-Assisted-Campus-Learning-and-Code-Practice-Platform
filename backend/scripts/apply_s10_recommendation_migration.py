"""只创建S01已批准的第四张B表；默认不连接、不执行。"""

import argparse
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.database import create_database_engine
from scripts.apply_s07_practice_migration import validate_target
from scripts.verify_database_schema import verify_table

TABLE = "practice_recommendation_applications"
MIGRATION = Path(__file__).resolve().parents[1] / "migrations/20261026_s10_recommendation_applications.sql"


def apply(engine, database):
    validate_target(engine, database)
    names = set(inspect(engine).get_table_names())
    if not {"users", "analytics_batches", "daily_tasks"}.issubset(names):
        raise ValueError("reference_tables_missing")
    existed = TABLE in names
    if not existed:
        sql = "\n".join(line for line in MIGRATION.read_text(encoding="utf-8").splitlines()
                        if not line.lstrip().startswith("--"))
        with engine.connect() as connection:
            for statement in sql.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)
            connection.commit()
    errors = verify_table(inspect(engine), TABLE)
    if errors:
        raise ValueError("recommendation_schema_mismatch")
    return "already_applied" if existed else "applied"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database")
    args = parser.parse_args()
    if not args.apply:
        print("dry_run: one new table; no connection or write")
        return 0
    if args.database != args.confirm_database:
        parser.error("需要重复确认本轮专用隔离库")
    engine = create_database_engine(make_url(get_settings().database_url)
                                    .set(database=args.database).render_as_string(hide_password=False))
    try:
        print(apply(engine, args.database))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
