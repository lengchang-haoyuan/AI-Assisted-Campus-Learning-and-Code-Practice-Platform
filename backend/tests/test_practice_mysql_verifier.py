"""S08隔离验收器的本地守卫与场景检查；本模块不连接MySQL。"""

import asyncio
from contextlib import nullcontext, redirect_stdout
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.ai.client import AIClient
from app.practice.agent import PracticeGuidanceAgent
from app.practice.review import PracticeCodeGuidanceAgent, PracticeReviewAgent
from app.services.practice import PracticeService
from scripts import verify_s08_practice as verifier
from tests.test_practice_submission import SubmissionMemoryRepository


class PracticeMySQLVerifierTests(unittest.TestCase):
    def test_dry_run_never_opens_database_and_uses_new_run_scope(self):
        output = io.StringIO()
        with patch.object(verifier.sys, "argv", ["verify", "--database", verifier.DATABASE]), \
             patch.object(verifier, "existing_target_engine", side_effect=AssertionError("no database")), \
             redirect_stdout(output):
            self.assertEqual(verifier.main(), 0)
        plan = json.loads(output.getvalue())
        self.assertEqual(plan["database_connection"], "not_opened")
        self.assertEqual(plan["run_id"], "s08-advisory-db-20261026")
        self.assertEqual(list(plan["limits"].values()), [14, 20, 180, 28, 28])
        self.assertEqual(plan["real_model_calls"], 0)

    def test_wrong_target_and_old_apply_limits_are_rejected_before_connection(self):
        with self.assertRaisesRegex(verifier.VerificationFailure, "unexpected_database"):
            verifier.existing_target_engine("business_database")
        with patch.object(verifier.sys, "argv", ["verify", "--database", verifier.DATABASE,
                "--apply", "--confirm-database", verifier.DATABASE, "--confirm-limits", "10,20,150,24,24"]), \
             patch.object(verifier, "existing_target_engine", side_effect=AssertionError("no database")), \
             redirect_stdout(io.StringIO()), patch.object(verifier.sys, "stderr", io.StringIO()), \
             self.assertRaises(SystemExit) as raised:
            verifier.main()
        self.assertEqual(raised.exception.code, 2)

    def test_write_guard_rejects_delete_ddl_protected_tables_and_old_row_update(self):
        guard = verifier.WriteGuard(None, {"row_counts": verifier.INITIAL_COUNTS})
        context = SimpleNamespace(compiled_parameters=[{"pk": "old", "status": "completed"}])
        for sql, code in (
            ("DROP TABLE practice_sessions", "ddl_or_unknown_write_rejected"),
            ("DELETE FROM practice_sessions WHERE id='old'", "delete_rejected"),
            ("UPDATE users SET id=3", "write_table_rejected"),
            ("UPDATE practice_sessions SET status=%(status)s WHERE practice_sessions.id = %(pk)s", "old_row_update"),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(verifier.VerificationFailure, code):
                guard.before(None, None, sql, None, context, False)
        guard.new_ids["practice_attempts"].add("old")
        with self.assertRaisesRegex(verifier.VerificationFailure, "attempt_payload_update"):
            guard.before(None, None, "UPDATE practice_attempts SET code_text=%(code)s WHERE practice_attempts.id = %(pk)s",
                         None, context, False)

    def test_advisory_scenarios_run_locally_with_same_fake_without_database(self):
        cases = (verifier.first_case, verifier.revision_case, verifier.late_case, verifier.empty_case,
                 verifier.failed_case, verifier.insufficient_case, verifier.advice_only_case, verifier.timeout_case)
        for callback in cases:
            with self.subTest(case=callback.__name__):
                repo = SubmissionMemoryRepository()
                provider = verifier.FakePracticeProvider()
                client = AIClient(provider, total_timeout_seconds=5, max_retries=0,
                                  retry_base_delay_seconds=0, max_retry_delay_seconds=0)
                options = {"model": "fake-model", "max_tokens": 1500, "temperature": 0}
                service = PracticeService(repo, PracticeGuidanceAgent(client, **options),
                    provider_name="fake", model="fake-model", operation_timeout_seconds=2,
                    review_agent=PracticeReviewAgent(client, **options),
                    code_guidance_agent=PracticeCodeGuidanceAgent(client, **options))
                with patch.multiple(verifier, OWNER_ID=1, OTHER_OWNER_ID=2, PROJECT_ID=7), \
                     patch.object(verifier, "build_service", return_value=service):
                    result = asyncio.run(callback(lambda: nullcontext(object()), provider))
                self.assertIn("state", result)
                self.assertFalse(repo.in_transaction)


if __name__ == "__main__":
    unittest.main()
