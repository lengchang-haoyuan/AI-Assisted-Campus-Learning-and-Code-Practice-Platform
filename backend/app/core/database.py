from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class DatabaseConfigurationError(RuntimeError):
    """数据库连接配置缺失或不符合当前驱动约定。"""


def create_database_engine(database_url: str) -> Engine:
    """创建延迟连接的 MySQL Engine，并固定每个连接的会话时区。"""
    url = make_url(database_url)
    if url.drivername != "mysql+pymysql" or not url.database:
        raise DatabaseConfigurationError("数据库 URL 必须指定 MySQL PyMySQL 驱动和库名")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    @event.listens_for(engine, "connect")
    def set_utc_timezone(
        dbapi_connection: Any, connection_record: Any
    ) -> None:
        del connection_record
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")

    return engine


@lru_cache
def get_engine() -> Engine:
    database_url = get_settings().database_url
    if database_url is None:
        raise DatabaseConfigurationError("未配置 DATABASE_URL")
    return create_database_engine(database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def check_database_connection(engine: Engine | None = None) -> str:
    """执行无副作用连接检查，返回当前数据库名。"""
    target_engine = engine or get_engine()
    with target_engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        database_name = connection.scalar(text("SELECT DATABASE()"))
    if not isinstance(database_name, str) or not database_name:
        raise DatabaseConfigurationError("数据库连接未选定具体库")
    return database_name
