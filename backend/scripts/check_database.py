from sqlalchemy.exc import SQLAlchemyError

from app.core.database import DatabaseConfigurationError, check_database_connection


def main() -> int:
    try:
        database_name = check_database_connection()
    except (DatabaseConfigurationError, SQLAlchemyError):
        print("数据库连接检查失败，请核对 DATABASE_URL、MySQL 服务和目标库。")
        return 1
    print(f"数据库连接正常，当前数据库：{database_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
