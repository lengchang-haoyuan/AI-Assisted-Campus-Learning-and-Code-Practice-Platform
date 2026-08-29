from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, TypeEngine

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

MYSQL_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class UTCDateTime(TypeDecorator[datetime]):
    """MySQL 保存无时区 UTC，Python 边界始终使用带时区 datetime。"""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[datetime]:
        if dialect.name == "mysql":
            return dialect.type_descriptor(DATETIME(fsp=6))
        return dialect.type_descriptor(DateTime())

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("数据库时间必须包含时区信息")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("CURRENT_TIMESTAMP(6)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=text(
            "CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"
        ),
    )
