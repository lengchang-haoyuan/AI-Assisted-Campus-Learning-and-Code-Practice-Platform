import copy
import json
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from scripts.export_ods_snapshot import FIXTURE, select_practice_sources
from analytics.practice_answers import calculate_practice
from analytics.practice_ads import utc_session_rows
from analytics.practice_contract import PRACTICE_DEFINITIONS, validate_practice_sources
from analytics.practice_fixtures import FROZEN_TOTALS, make_practice_fixture, make_window_boundary_fixture
from analytics.practice_quality import logical_event_order_queries
from app.schemas.practice_analytics import PracticeSummary


class PracticePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self):
        self.fixture = make_practice_fixture(self.core)
        self.tables, self.manifest = self.fixture["tables"], self.fixture["manifest"]

    def test_fixed_four_paths_and_failure_restore_have_independent_totals(self):
        result = calculate_practice(self.tables, self.manifest)
        self.assertEqual({key: result[key] for key in FROZEN_TOTALS}, FROZEN_TOTALS)
        PracticeSummary.model_validate(result)

    def test_extract_has_only_bounded_projection_fields(self):
        validate_practice_sources(self.tables, self.manifest["owner_user_id"], datetime(2026, 10, 4))
        for table, definitions in PRACTICE_DEFINITIONS.items():
            for row in self.tables[table]:
                self.assertEqual(set(row), {field["field"] for field in definitions})
                self.assertFalse({"code_text", "feedback", "action_payload", "declared_output"} & set(row))

    def test_code_or_feedback_body_extra_field_is_rejected(self):
        self.tables["practice_attempts"][0]["code_text"] = "must remain outside ODS"
        with self.assertRaisesRegex(ValueError, "practice_schema_fields_mismatch"):
            validate_practice_sources(self.tables, self.manifest["owner_user_id"], datetime(2026, 10, 4))

    def test_wrong_owner_rejected(self):
        with self.assertRaisesRegex(ValueError, "practice_owner_mismatch"):
            validate_practice_sources(self.tables, 999, datetime(2026, 10, 4))

    def test_conflicting_primary_key_not_arbitrarily_kept(self):
        other = copy.deepcopy(self.tables["practice_attempts"][0])
        other["attempt_no"] += 1
        self.tables["practice_attempts"].append(other)
        with self.assertRaisesRegex(ValueError, "practice_duplicate_primary_key"):
            validate_practice_sources(self.tables, self.manifest["owner_user_id"], datetime(2026, 10, 4))

    def test_unknown_teaching_evidence_stays_null(self):
        result = calculate_practice(self.tables, self.manifest)
        self.assertIsNone(result["teacher_confirmation_count"])
        self.assertTrue(all(s["teacher_confirmation"] is None for s in result["sessions"]))
        self.assertTrue(all(s["output_comparison"] == "unknown" for s in result["sessions"]))

    def test_bound_operation_controls_advice_without_relabeling_old_events(self):
        before = copy.deepcopy(self.tables["practice_events"])
        repeated = [a for a in self.tables["practice_attempts"] if a["bound_operation_id"]]
        target = repeated[0]
        target["bound_operation_id"] = None
        target["bound_ai_request_id"] = None
        result = calculate_practice(self.tables, self.manifest)
        self.assertFalse(any(a["attempt_id"] == target["id"] for s in result["sessions"] for a in s["advice"]))
        self.assertEqual(self.tables["practice_events"], before)

    def test_null_coverage_for_empty_owner_is_not_a_zero_date(self):
        empty = {**self.tables, **{key: [] for key in PRACTICE_DEFINITIONS}}
        result = calculate_practice(empty, {**self.manifest, "observed_event_coverage_start": None})
        self.assertEqual(result["session_count"], 0)
        self.assertIsNone(result["observed_event_coverage_start"])
        self.assertIsNone(result["teacher_confirmation_count"])

    def test_empty_extract_projects_no_private_json_column(self):
        class Reader:
            def __init__(self):
                self.reads = []
                self.queries = []
            def query(self, sql, params):
                self.queries.append(sql)
                return [{"first_at": None}] if "MIN(e.occurred_at)" in sql else []
        reader = Reader()
        rows, coverage = select_practice_sources(reader, 1, datetime(2026, 10, 1), datetime(2026, 10, 4), datetime(2026, 10, 4))
        self.assertEqual(rows, {key: [] for key in PRACTICE_DEFINITIONS})
        self.assertIsNone(coverage)
        self.assertTrue(all("code_text" not in sql and "context_snapshot" not in sql for sql in reader.queries))

    def order_errors(self):
        # 两条顺序查询使用标准SQL；内存SQLite直接执行相同查询，不依赖真实MySQL或Spark。
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE v_practice_events (id TEXT,session_id TEXT,attempt_id TEXT,event_type TEXT,occurred_at TEXT,revision INTEGER)")
            connection.executemany("INSERT INTO v_practice_events VALUES (?,?,?,?,?,?)", [tuple(row[k] for k in
                ("id", "session_id", "attempt_id", "event_type", "occurred_at", "revision")) for row in self.tables["practice_events"]])
            return {reason: [r[0] for r in connection.execute(query)] for _, query, reason in logical_event_order_queries()}

    def test_same_transaction_cross_clock_created_time_is_not_business_inversion(self):
        for session in self.tables["practice_sessions"]:
            creation = next(e for e in self.tables["practice_events"] if e["session_id"] == session["id"] and e["event_type"] == "session_created")
            session["created_at"] = (datetime.fromisoformat(creation["occurred_at"].replace("Z", "+00:00")) + timedelta(microseconds=323)).isoformat().replace("+00:00", "Z")
        for attempt in self.tables["practice_attempts"]:
            submission = next(e for e in self.tables["practice_events"] if e["attempt_id"] == attempt["id"] and e["event_type"] == "attempt_submitted")
            attempt["created_at"] = (datetime.fromisoformat(submission["occurred_at"].replace("Z", "+00:00")) + timedelta(microseconds=9)).isoformat().replace("+00:00", "Z")
        self.assertTrue(all(not errors for errors in self.order_errors().values()))

    def test_actual_event_before_creation_still_rejected(self):
        target = next(e for e in self.tables["practice_events"] if e["event_type"] == "attempt_submitted")
        target["occurred_at"] = "2026-10-01T00:00:00Z"
        self.assertIn(target["id"], self.order_errors()["practice_event_before_creation_event"])

    def test_actual_review_before_submission_still_rejected(self):
        target = next(e for e in self.tables["practice_events"] if e["event_type"] == "review_started")
        submitted = next(e for e in self.tables["practice_events"] if e["attempt_id"] == target["attempt_id"] and e["event_type"] == "attempt_submitted")
        target["occurred_at"] = (datetime.fromisoformat(submitted["occurred_at"].replace("Z", "+00:00")) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        self.assertIn(target["id"], self.order_errors()["practice_event_before_submission_event"])

    def test_equivalent_utc_and_shanghai_source_times_emit_same_utc_microseconds(self):
        expected = calculate_practice(self.tables, self.manifest)
        shifted = copy.deepcopy(self.tables)
        shanghai = timezone(timedelta(hours=8))
        for session in shifted["practice_sessions"]:
            session["created_at"] = datetime.fromisoformat(session["created_at"].replace("Z", "+00:00")).astimezone(shanghai).isoformat()
        actual = calculate_practice(shifted, self.manifest)
        self.assertEqual(actual, expected)
        self.assertTrue(all(s["created_at"].endswith(".000000Z") for s in actual["sessions"]))

    def test_non_utc_spark_session_is_explicitly_rejected_before_collection(self):
        class Config:
            def get(self, key):
                return "Asia/Shanghai"
        class Spark:
            conf = Config()
        with self.assertRaisesRegex(ValueError, "practice_utc_spark_session_required"):
            utc_session_rows(Spark())

    def test_snapshot_attempts_and_window_submission_end_events_are_distinct(self):
        data = make_window_boundary_fixture(self.core)
        result = calculate_practice(data["tables"], data["manifest"])
        PracticeSummary.model_validate(result)
        self.assertEqual(result["session_count"], 1)
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(result["submission_event_count"], 1)
        self.assertEqual(result["personal_end_count"], 0)
        session = result["sessions"][0]
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["latest_attempt_no"], 2)
        self.assertEqual([a["attempt_no"] for a in session["advice"]], [1])


if __name__ == "__main__":
    unittest.main()
