"""预览S07三表增量；显式apply且复核本轮专用隔离库后才执行DDL。"""

import argparse
from pathlib import Path
import re

from sqlalchemy import inspect
from sqlalchemy.engine import Engine, make_url

from app.core.config import get_settings
from app.core.database import create_database_engine
from scripts.verify_database_schema import verify_table

TABLES = ("practice_sessions", "practice_attempts", "practice_events")
MIGRATION = Path(__file__).resolve().parents[1] / "migrations/20261021_s07_practice.sql"
DATABASE_PATTERN = re.compile(r"scholarhub_l4_[a-z0-9_]+\Z")
REFERENCE_TABLES = {"users", "projects", "ai_requests"}


def validate_target(engine: Engine, database: str) -> None:
    if (
        not DATABASE_PATTERN.fullmatch(database)
        or engine.url.database != database
        or engine.url.get_backend_name() != "mysql"
        or engine.url.host not in ("127.0.0.1", "localhost")
        or (engine.url.port or 3306) != 3306
    ):
        raise ValueError("unauthorized_migration_target")


def verify_practice_schema(engine: Engine) -> list[str]:
    """仅复核新增三表，不要求或修改其他阶段表。"""
    inspector = inspect(engine)
    errors = [
        error
        for table in TABLES
        for error in verify_table(inspector, table)
    ]
    for table in TABLES:
        for column in inspector.get_columns(table):
            if column["name"] in {
                "id", "session_id", "attempt_id", "active_operation_id", "operation_id"
            } and str(column["type"]) != "CHAR(36)":
                errors.append(f"{table}.{column['name']}: UUID类型不一致")
    return errors


def apply(engine: Engine, database: str) -> str:
    """调用方须先取得本轮目标许可；不创建库、不清空数据、不修补半迁移。"""
    validate_target(engine, database)
    existing = set(inspect(engine).get_table_names())
    if not REFERENCE_TABLES.issubset(existing):
        raise ValueError("reference_tables_missing")
    present = set(TABLES) & existing
    if present and present != set(TABLES):
        raise ValueError("partial_migration_requires_inspection")
    if not present:
        sql = "\n".join(
            line
            for line in MIGRATION.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("--")
        )
        # MySQL DDL会隐式提交；半迁移只报告，不删除或重建任何既有表。
        with engine.connect() as connection:
            for statement in sql.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)
            connection.commit()
    if verify_practice_schema(engine):
        raise ValueError("practice_schema_mismatch")
    return "already_applied" if present else "applied"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database")
    args = parser.parse_args()
    if not DATABASE_PATTERN.fullmatch(args.database):
        parser.error("仅支持本轮明确授权的scholarhub_l4_专用隔离库")
    if not args.apply:
        print(f"dry_run: {args.database}; three new tables; no connection or write")
        print(f"migration: {MIGRATION.name}")
        return 0
    if args.confirm_database != args.database:
        parser.error("执行须使用--confirm-database重复确认同一隔离目标")

    url = make_url(get_settings().database_url).set(database=args.database)
    engine = create_database_engine(url.render_as_string(hide_password=False))
    try:
        print(apply(engine, args.database))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
