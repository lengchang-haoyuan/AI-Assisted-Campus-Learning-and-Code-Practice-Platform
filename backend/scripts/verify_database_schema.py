from collections.abc import Iterable
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.core.database import DatabaseConfigurationError, get_engine
from app.models import Base


def normalized_columns(columns: Iterable[str]) -> tuple[str, ...]:
    return tuple(columns)


def verify_table(inspector: Any, table_name: str) -> list[str]:
    errors: list[str] = []
    model_table = Base.metadata.tables[table_name]

    actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
    expected_columns = set(model_table.columns.keys())
    if actual_columns != expected_columns:
        errors.append(f"{table_name}: 列集合不一致")

    actual_pk = normalized_columns(
        inspector.get_pk_constraint(table_name).get("constrained_columns") or ()
    )
    expected_pk = normalized_columns(column.name for column in model_table.primary_key)
    if actual_pk != expected_pk:
        errors.append(f"{table_name}: 主键不一致")

    actual_foreign_keys = {
        (
            normalized_columns(item["constrained_columns"]),
            item["referred_table"],
            normalized_columns(item["referred_columns"]),
            (item.get("options") or {}).get("ondelete", "").upper(),
        )
        for item in inspector.get_foreign_keys(table_name)
    }
    expected_foreign_keys = {
        (
            normalized_columns(column.name for column in constraint.columns),
            constraint.referred_table.name,
            normalized_columns(element.column.name for element in constraint.elements),
            (constraint.ondelete or "").upper(),
        )
        for constraint in model_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    if actual_foreign_keys != expected_foreign_keys:
        errors.append(f"{table_name}: 外键或删除语义不一致")

    actual_unique = {
        item["name"] for item in inspector.get_unique_constraints(table_name)
    }
    expected_unique = {
        constraint.name
        for constraint in model_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    if actual_unique != expected_unique:
        errors.append(f"{table_name}: 唯一约束不一致")

    actual_checks = {
        item["name"] for item in inspector.get_check_constraints(table_name)
    }
    expected_checks = {
        constraint.name
        for constraint in model_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    if actual_checks != expected_checks:
        errors.append(f"{table_name}: 检查约束不一致")

    actual_indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    expected_indexes = {index.name for index in model_table.indexes}
    if not expected_indexes.issubset(actual_indexes):
        errors.append(f"{table_name}: 缺少模型声明的索引")

    return errors


def main() -> int:
    try:
        inspector = inspect(get_engine())
        actual_tables = set(inspector.get_table_names())
    except (DatabaseConfigurationError, SQLAlchemyError):
        print("数据库结构检查失败，请核对 DATABASE_URL 和 MySQL 服务。")
        return 1

    expected_tables = set(Base.metadata.tables)
    if actual_tables != expected_tables:
        print("数据库结构检查失败：表集合与 SQLAlchemy metadata 不一致。")
        return 1

    errors = [
        error
        for table_name in sorted(expected_tables)
        for error in verify_table(inspector, table_name)
    ]
    if errors:
        print("数据库结构检查失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    foreign_key_count = sum(
        len(inspector.get_foreign_keys(table_name)) for table_name in expected_tables
    )
    print(
        f"数据库结构检查通过：{len(expected_tables)} 张表，"
        f"{foreign_key_count} 个外键，约束和索引与 Models 一致。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
