"""S10验收器的本地保护检查；不连接MySQL、不执行模型请求。"""

import io
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from scripts import verify_s10_practice_analytics as verifier
from scripts.verify_s08_practice import VerificationFailure


class S10GuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = verifier.Guard(None, {"row_counts": verifier.INITIAL_COUNTS})
        self.guard.ids["projects"].add(3)

    def update(self, sql, identity):
        context = SimpleNamespace(compiled_parameters=[{"pk": identity}])
        self.guard.before(None, None, sql, None, context, False)

    def test_only_new_project_update_allowed(self):
        for table in ("projects", "`projects`"):
            self.update(f"UPDATE {table} SET context_data=%(data)s WHERE {table}.id = %(pk)s", 3)
        with self.assertRaisesRegex(VerificationFailure, "old_row_update"):
            self.update("UPDATE projects SET context_data=%(data)s WHERE projects.id = %(pk)s", 1)

    def test_account_ddl_and_unbounded_writes_rejected(self):
        for sql in ("ALTER TABLE projects ADD test INT", "UPDATE users SET username='x'", "UPDATE projects SET context_data='x'", "DELETE FROM practice_sessions WHERE id='x'"):
            with self.subTest(sql=sql), self.assertRaises(VerificationFailure):
                self.update(sql, 3)

    def test_attempt_code_cannot_be_overwritten(self):
        self.guard.ids["practice_attempts"].add("new")
        with self.assertRaisesRegex(VerificationFailure, "attempt_payload_update"):
            self.update("UPDATE practice_attempts SET code_text=%(code)s WHERE practice_attempts.id = %(pk)s", "new")

    def test_new_uuid_events_may_be_saved_in_one_transaction(self):
        context = SimpleNamespace(compiled_parameters=[{"id": "a"}, {"id": "b"}])
        self.guard.after(None, None, "INSERT INTO practice_events (id) VALUES (%(id)s)", None, context, True)
        self.assertEqual(self.guard.ids["practice_events"], {"a", "b"})

    def test_apply_requires_target_before_database_connection(self):
        with patch.object(sys, "argv", ["verify", "--setup"]), \
             patch.object(verifier, "existing_target_engine", side_effect=AssertionError("no database")), \
             patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
            verifier.main()
        self.assertEqual(raised.exception.code, 2)

    def test_old_row_fingerprint_checks_only_original_keys(self):
        original = {"tables": ["projects"], "row_counts": {"projects": 1}, "rows": {"projects": {(1,): {"id": 1, "value": "old"}}}}
        baseline = verifier.baseline_record(original)
        later = {"tables": ["projects"], "row_counts": {"projects": 2}, "rows": {"projects": {(1,): {"id": 1, "value": "old"}, (2,): {"id": 2, "value": "new"}}}}
        with patch.object(verifier, "LIMITS", {"projects": 1}):
            self.assertEqual(verifier.validate_preserved(baseline, later), {"projects": 1})
            later["rows"]["projects"][(1,)]["value"] = "changed"
            with self.assertRaisesRegex(VerificationFailure, "old_row_changed"):
                verifier.validate_preserved(baseline, later)

    def test_idempotency_keys_are_stable_and_phase_specific(self):
        self.assertEqual(verifier.key("candidate:review1"), verifier.key("candidate:review1"))
        self.assertNotEqual(verifier.key("candidate:review1"), verifier.key("candidate:review2"))

    def test_application_only_sql_guard_rejects_practice_write(self):
        guard = verifier.Guard(None, {"row_counts": verifier.INITIAL_COUNTS}, write_tables={"daily_tasks", "practice_recommendation_applications"})
        context = SimpleNamespace(compiled_parameters=[{"pk": "new"}])
        with self.assertRaisesRegex(VerificationFailure, "write_table_rejected"):
            guard.before(None, None, "UPDATE practice_sessions SET status=%(status)s WHERE practice_sessions.id = %(pk)s", None, context, False)


class S10ApplicationOnlyServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_writer_surface_denies_other_mutations_before_database(self):
        provider = verifier.FakeProvider()
        app = verifier.application(None, provider, application_only=True)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://s10/api/v1") as client:
            for method, path in (("POST", "/projects"), ("POST", "/practice-sessions/00000000-0000-0000-0000-000000000000/actions"),
                                 ("PUT", "/learning/tasks/1"), ("POST", "/learning/tasks")):
                with self.subTest(path=path):
                    self.assertEqual((await client.request(method, path, json={})).status_code, 403)
            self.assertEqual((await client.get("/projects")).status_code, 401)
            endpoint = "/offline-analytics/batches/00000000-0000-0000-0000-000000000000/recommendation-applications"
            self.assertEqual((await client.post(endpoint, json={})).status_code, 401)
        self.assertEqual(provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
