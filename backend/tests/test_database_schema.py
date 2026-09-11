from datetime import UTC, datetime
from pathlib import Path
import re
import unittest

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable, ForeignKeyConstraint

from app.models import Base
from app.models.base import UTCDateTime

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BACKEND_DIR / "schema.sql"
EXPECTED_TABLES = {
    "account_audits",
    "ai_requests",
    "ai_results",
    "campus_invitations",
    "campus_memberships",
    "class_memberships",
    "comments",
    "community_governance_actions",
    "community_governance_cases",
    "community_publication_versions",
    "community_publications",
    "courses",
    "daily_tasks",
    "favorites",
    "learning_plans",
    "learning_records",
    "learning_reports",
    "likes",
    "project_tags",
    "project_views",
    "projects",
    "password_resets",
    "feedback",
    "notifications",
    "submissions",
    "submission_versions",
    "tags",
    "teaching_assignments",
    "teaching_classes",
    "users",
    "workflow_edges",
    "workflow_nodes",
    "workflow_runs",
    "workflows",
}
CREATE_TABLE_PATTERN = re.compile(
    r"CREATE TABLE\s+([a-z_]+)\s*\((.*?)\)\s*ENGINE=",
    re.IGNORECASE | re.DOTALL,
)
COLUMN_PATTERN = re.compile(
    r"^\s+`?([a-z_][a-z0-9_]*)`?\s+"
    r"(?:BIGINT|INTEGER|INT|SMALLINT|VARCHAR|TEXT|BOOLEAN|DATETIME|DATE|TIME|JSON|NUMERIC|BINARY)\b",
    re.IGNORECASE | re.MULTILINE,
)


def schema_tables(schema_sql: str) -> dict[str, set[str]]:
    return {
        table_name: set(COLUMN_PATTERN.findall(table_body))
        for table_name, table_body in CREATE_TABLE_PATTERN.findall(schema_sql)
    }


class DatabaseSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_mappers()
        cls.schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    def test_metadata_discovers_all_tables(self) -> None:
        self.assertEqual(set(Base.metadata.tables), EXPECTED_TABLES)

    def test_schema_tables_and_columns_match_metadata(self) -> None:
        sql_tables = schema_tables(self.schema_sql)
        self.assertEqual(set(sql_tables), EXPECTED_TABLES)
        for table_name, table in Base.metadata.tables.items():
            with self.subTest(table=table_name):
                self.assertEqual(sql_tables[table_name], set(table.columns.keys()))

    def test_named_constraints_and_indexes_exist_in_schema(self) -> None:
        expected_names: set[str] = set()
        for table in Base.metadata.tables.values():
            expected_names.update(
                constraint.name
                for constraint in table.constraints
                if constraint.name is not None
            )
            expected_names.update(index.name for index in table.indexes)
        missing = sorted(name for name in expected_names if name not in self.schema_sql)
        self.assertEqual(missing, [])

    def test_mysql_ddl_compiles_for_every_table(self) -> None:
        dialect = mysql.dialect()
        for table in Base.metadata.sorted_tables:
            with self.subTest(table=table.name):
                ddl = str(CreateTable(table).compile(dialect=dialect))
                self.assertIn(f"CREATE TABLE {table.name}", ddl)

    def test_workflow_edges_require_nodes_from_same_workflow(self) -> None:
        edge_table = Base.metadata.tables["workflow_edges"]
        composite_targets = {
            tuple(element.target_fullname for element in constraint.elements)
            for constraint in edge_table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
            and len(constraint.elements) == 2
        }
        self.assertEqual(
            composite_targets,
            {
                ("workflow_nodes.id", "workflow_nodes.workflow_id"),
            },
        )
        composite_sources = {
            tuple(column.name for column in constraint.columns)
            for constraint in edge_table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
            and len(constraint.elements) == 2
        }
        self.assertEqual(
            composite_sources,
            {
                ("source_node_id", "workflow_id"),
                ("target_node_id", "workflow_id"),
            },
        )

    def test_core_delete_semantics(self) -> None:
        expected = {
            ("projects", "owner_id", "users.id"): "RESTRICT",
            ("comments", "user_id", "users.id"): "RESTRICT",
            ("comments", "project_id", "projects.id"): "CASCADE",
            ("project_views", "user_id", "users.id"): "RESTRICT",
            ("project_views", "project_id", "projects.id"): "CASCADE",
            ("learning_plans", "user_id", "users.id"): "RESTRICT",
            ("workflows", "project_id", "projects.id"): "CASCADE",
            ("workflow_nodes", "workflow_id", "workflows.id"): "CASCADE",
            ("workflow_runs", "started_by_id", "users.id"): "SET NULL",
            ("learning_plans", "project_id", "projects.id"): "SET NULL",
            ("learning_records", "course_id", "courses.id"): "SET NULL",
            ("ai_requests", "user_id", "users.id"): "RESTRICT",
            ("ai_requests", "project_id", "projects.id"): "SET NULL",
            ("ai_requests", "workflow_run_id", "workflow_runs.id"): "SET NULL",
            ("ai_results", "request_id", "ai_requests.id"): "CASCADE",
            ("learning_reports", "ai_result_id", "ai_results.id"): "SET NULL",
        }
        actual: dict[tuple[str, str, str], str | None] = {}
        for table in Base.metadata.tables.values():
            for foreign_key in table.foreign_keys:
                actual[(table.name, foreign_key.parent.name, foreign_key.target_fullname)] = (
                    foreign_key.ondelete
                )
        for relation, ondelete in expected.items():
            with self.subTest(relation=relation):
                self.assertEqual(actual[relation], ondelete)

    def test_sensitive_fields_are_not_modeled(self) -> None:
        all_columns = {
            column.name
            for table in Base.metadata.tables.values()
            for column in table.columns
        }
        self.assertIn("password_hash", all_columns)
        self.assertTrue(
            {"password", "api_key", "secret_key", "raw_prompt", "raw_input"}.isdisjoint(
                all_columns
            )
        )

    def test_utc_datetime_rejects_naive_values(self) -> None:
        utc_type = UTCDateTime()
        with self.assertRaisesRegex(ValueError, "必须包含时区"):
            utc_type.process_bind_param(datetime(2026, 8, 29, 12, 0), mysql.dialect())
        stored = utc_type.process_bind_param(
            datetime(2026, 8, 29, 20, 0, tzinfo=UTC), mysql.dialect()
        )
        self.assertIsNone(stored.tzinfo)
        loaded = utc_type.process_result_value(stored, mysql.dialect())
        self.assertEqual(loaded.tzinfo, UTC)


if __name__ == "__main__":
    unittest.main()
