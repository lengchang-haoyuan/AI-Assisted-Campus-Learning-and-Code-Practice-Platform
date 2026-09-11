from pathlib import Path

from pymysql.constants import CLIENT
import pymysql
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import DatabaseConfigurationError, get_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATION_PATH = BACKEND_DIR / "migrations" / "20260911_p21_community_governance.sql"
NEW_TABLES = {
    "community_publications",
    "community_publication_versions",
    "community_governance_actions",
    "community_governance_cases",
}
COMMENT_COLUMNS = {"moderation_status", "moderated_at", "revision"}
NOTIFICATION_COLUMNS = {"community_publication_id", "community_case_id"}


def migration_state() -> str:
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())
    parts = [table in tables for table in NEW_TABLES]
    if "comments" in tables:
        names = {column["name"] for column in inspector.get_columns("comments")}
        parts.append(COMMENT_COLUMNS.issubset(names))
    else:
        parts.append(False)
    if "notifications" in tables:
        names = {column["name"] for column in inspector.get_columns("notifications")}
        parts.append(NOTIFICATION_COLUMNS.issubset(names))
    else:
        parts.append(False)
    if all(parts):
        return "applied"
    if any(parts):
        return "partial"
    return "baseline"


def apply_migration() -> None:
    settings = get_settings()
    if settings.database_url is None:
        raise DatabaseConfigurationError("未配置 DATABASE_URL")
    url = make_url(settings.database_url)
    connection = pymysql.connect(
        host=url.host or "127.0.0.1",
        port=url.port or 3306,
        user=url.username or "",
        password=url.password or "",
        database=url.database,
        charset=(url.query.get("charset") or "utf8mb4"),
        autocommit=True,
        client_flag=CLIENT.MULTI_STATEMENTS,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(MIGRATION_PATH.read_text(encoding="utf-8"))
            while cursor.nextset():
                pass
    finally:
        connection.close()


def verify_history() -> tuple[int, int]:
    with get_engine().connect() as connection:
        published = int(connection.scalar(text("SELECT COUNT(*) FROM projects WHERE is_published = TRUE")) or 0)
        legacy = int(connection.scalar(text("SELECT COUNT(*) FROM community_publications WHERE status = 'legacy_review_required'")) or 0)
    return published, legacy


def main() -> int:
    try:
        state = migration_state()
        if state == "applied":
            print("P21 数据库迁移已完整应用，无需重复执行。")
            return 0
        if state == "partial":
            print("检测到部分 P21 结构，已拒绝继续；请按迁移备份人工核对。")
            return 1
        apply_migration()
        get_engine().dispose()
        if migration_state() != "applied":
            print("P21 数据库迁移执行后结构不完整，请按备份人工核对。")
            return 1
        published, legacy = verify_history()
        if legacy != published:
            print("P21 历史公开项目迁移数量不一致，请按备份人工核对。")
            return 1
    except (DatabaseConfigurationError, SQLAlchemyError, pymysql.MySQLError, OSError):
        print("P21 数据库迁移失败，请核对 DATABASE_URL、MySQL 服务和迁移前置结构。")
        return 1
    print(f"P21 数据库迁移完成：{legacy} 个历史公开项目标记为待补审。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
