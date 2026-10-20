import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.export_ods_snapshot import FIXTURE, utc_window, validate_sources

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analytics.fixture_answers import assert_subset, calculate, deduplicate
from analytics.snapshot_files import begin_snapshot, publish_snapshot, read_snapshot


class OdsSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self):
        self.tables = copy.deepcopy(self.fixture["base_input"])
        self.manifest = copy.deepcopy(self.fixture["manifest"])

    def test_independent_answer_matches_frozen_full_D00(self):
        assert_subset(calculate(self.tables, self.manifest), self.fixture["base_expected"])

    def test_shanghai_window_utc_half_open(self):
        start, end = utc_window("2026-10-01", "2026-10-02")
        self.assertEqual(start.isoformat(), "2026-09-30T16:00:00")
        self.assertEqual(end.isoformat(), "2026-10-02T16:00:00")

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            utc_window("2026-10-03", "2026-10-01")

    def test_conflicting_primary_key_fails(self):
        self.tables["learning_records"][-1]["duration_minutes"] = 999
        with self.assertRaisesRegex(ValueError, "duplicate_key_conflict"):
            calculate(self.tables, self.manifest)

    def test_forged_source_does_not_become_trusted(self):
        self.tables["source_claim_projection"].append({"learning_record_id": 5, "source_claim": "teaching_submission",
                                                      "submission_id_claim": 701, "version_number_claim": 2})
        answer = calculate(self.tables, self.manifest)
        self.assertEqual(answer["records"]["trusted_teaching_count"], 2)
        self.assertEqual(answer["records"]["unverified_claim_count"], 1)

    def test_wrong_teacher_class_fails(self):
        self.tables["class_memberships"][1]["class_id"] = 999
        with self.assertRaises(ValueError):
            calculate(self.tables, self.manifest)

    def test_wrong_record_owner_fails(self):
        self.tables["learning_records"][2]["user_id"] = 999
        with self.assertRaisesRegex(ValueError, "relation_mismatch"):
            calculate(self.tables, self.manifest)

    def test_missing_link_preserves_teacher_confirmation(self):
        self.tables["learning_records"] = [r for r in self.tables["learning_records"] if r["id"] != 3]
        self.tables["feedback"][1]["learning_record_id"] = None
        answer = calculate(self.tables, self.manifest)
        self.assertEqual(answer["topic"]["confirmed_count"], 2)
        self.assertEqual(answer["topic"]["missing_teaching_record_links"], 1)

    def test_empty_owner_retained_without_false_percentage(self):
        answer = calculate({t: [] for t in self.tables}, self.manifest)
        self.assertEqual(answer["owner_user_id"], 1001)
        self.assertIsNone(answer["tasks"]["completion_rate"]["percent"])

    def test_extract_schema_and_owner_guard(self):
        tables, _ = deduplicate(self.tables)
        from datetime import datetime
        cutoff = datetime(2026, 10, 4)
        validate_sources(tables, 1001, cutoff)
        with self.assertRaisesRegex(ValueError, "owner_mismatch"):
            validate_sources(tables, 1002, cutoff)
        tables["learning_records"][0]["content"] = "must not export"
        with self.assertRaisesRegex(ValueError, "schema_fields_mismatch"):
            validate_sources(tables, 1001, cutoff)

    def test_completed_snapshot_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            pending, final = begin_snapshot(directory, "fixed")
            publish_snapshot(pending, final, self.tables, dict(self.manifest, snapshot_id="fixed"))
            before = {p.name: p.read_bytes() for p in final.iterdir()}
            with self.assertRaises(FileExistsError):
                begin_snapshot(directory, "fixed")
            self.assertEqual(before, {p.name: p.read_bytes() for p in final.iterdir()})
            self.assertEqual(read_snapshot(final), read_snapshot(final))

    def test_partial_snapshot_not_consumable(self):
        with tempfile.TemporaryDirectory() as directory:
            pending, final = begin_snapshot(directory, "partial")
            (pending / "learning_records.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_snapshot(pending)
            self.assertFalse(final.exists())

    def test_truncated_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            pending, final = begin_snapshot(directory, "fixed")
            publish_snapshot(pending, final, self.tables, dict(self.manifest, snapshot_id="fixed"))
            (final / "learning_records.jsonl").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "snapshot_size_mismatch"):
                read_snapshot(final)


if __name__ == "__main__":
    unittest.main()
