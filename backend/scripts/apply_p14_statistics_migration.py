from pathlib import Path

from pymysql.constants import CLIENT
import pymysql
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import DatabaseConfigurationError, get_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATION_PATH = BACKEND_DIR / "migrations" / "20260902_p14_statistics.sql"
NEW_INDEXES = {
    "projects": {
        "ix_projects_created_at",
        "ix_projects_completed_at",
        "ix_projects_published_at",
    },
    "comments": {"ix_comments_created_at"},
    "likes": {"ix_likes_created_at"},
    "favorites": {"ix_favorites_created_at"},
    "daily_tasks": {"ix_daily_tasks_completed_at"},
}


def migration_state() -> str:
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())
    has_view_table = "project_views" in tables
    project_columns = {item["name"] for item in inspector.get_columns("projects")}
    has_completed_at = "completed_at" in project_columns
    index_states = [
        expected.issubset(
            {item["name"] for item in inspector.get_indexes(table_name)}
        )
        for table_name, expected in NEW_INDEXES.items()
    ]
    applied_parts = [has_view_table, has_completed_at, *index_states]
    if all(applied_parts):
        return "applied"
    if any(applied_parts):
        return "partial"
    return "baseline"


def apply_migration() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseConfigurationError("未配置 DATABASE_URL")
    url = make_url(settings.database_url)
    password = url.password or ""
    connection = pymysql.connect(
        host=url.host or "127.0.0.1",
        port=url.port or 3306,
        user=url.username or "",
        password=password,
        database=url.database,
        charset=(url.query.get("charset") or "utf8mb4"),
        autocommit=True,
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    try:
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        with connection.cursor() as cursor:
            cursor.execute(sql)
            while cursor.nextset():
                pass
    finally:
        connection.close()


def main() -> int:
    try:
        state = migration_state()
        if state == "applied":
            print("P14 数据库迁移已完整应用，无需重复执行。")
            return 0
        if state == "partial":
            print("检测到部分 P14 结构，已拒绝继续；请先人工核对迁移状态。")
            return 1
        apply_migration()
        get_engine().dispose()
        if migration_state() != "applied":
            print("P14 数据库迁移执行后结构不完整，请人工核对。")
            return 1
    except (DatabaseConfigurationError, SQLAlchemyError, pymysql.MySQLError, OSError):
        print("P14 数据库迁移失败，请核对 DATABASE_URL、MySQL 服务和迁移前置结构。")
        return 1
    print("P14 数据库迁移完成：访问明细、项目完成时间和统计索引已创建。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
