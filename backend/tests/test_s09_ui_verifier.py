import unittest
from types import SimpleNamespace

from scripts.verify_s08_practice import VerificationFailure
from scripts.verify_s09_student_ui import FakeProvider, Guard
from app.ai.client import AIClient
from app.workflow.agents import RequirementsAnalysisWorkflowAgent
from tests.test_practice_agent import make_context


class S09VerifierGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = Guard(None, {})
        self.guard.ids["projects"].add(2)
        self.guard.ids["workflows"].add(1)

    def update(self, sql, identity):
        self.guard.before(None, None, sql, None, SimpleNamespace(compiled_parameters=[{"projects_id": identity}]), False)

    def test_unquoted_and_quoted_single_new_project_updates(self):
        for sql in ("UPDATE projects SET context_data=%(data)s WHERE projects.id = %(projects_id)s", "UPDATE `projects` SET context_data=%(data)s WHERE `projects`.`id` = %(projects_id)s"):
            self.update(sql, 2)

    def test_old_row_and_unbounded_update_rejected(self):
        with self.assertRaisesRegex(VerificationFailure, "old_row_update"):
            self.update("UPDATE projects SET context_data=%(data)s WHERE projects.id = %(projects_id)s", 1)
        with self.assertRaisesRegex(VerificationFailure, "single_pk"):
            self.update("UPDATE projects SET context_data=%(data)s", 2)

    def test_delete_ddl_and_account_write_rejected(self):
        for sql in ("DELETE FROM projects WHERE id=2", "ALTER TABLE projects ADD x INT", "UPDATE users SET username='fixture' WHERE users.id = %(projects_id)s"):
            with self.assertRaises(VerificationFailure):
                self.update(sql, 2)

    def test_recovery_bulk_is_scoped_to_new_workflow(self):
        sql = "UPDATE workflow_nodes SET status=%(status)s WHERE workflow_nodes.workflow_id = %(workflow_id_1)s AND workflow_nodes.status = %(status_1)s"
        self.guard.before(None, None, sql, None, SimpleNamespace(compiled_parameters=[{"workflow_id_1": 1, "status_1": "running"}]), False)
        with self.assertRaises(VerificationFailure):
            self.guard.before(None, None, sql, None, SimpleNamespace(compiled_parameters=[{"workflow_id_1": 99, "status_1": "running"}]), False)

    def test_atomic_confirmation_can_append_two_uuid_events(self):
        self.guard.after(None, None, "INSERT INTO practice_events (id) VALUES (%(id)s)", None,
                         SimpleNamespace(compiled_parameters=[{"id": "event-a"}, {"id": "event-b"}]), True)
        self.assertEqual(self.guard.ids["practice_events"], {"event-a", "event-b"})


class S09FakeFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_json_object_schema_returns_valid_requirements(self):
        provider = FakeProvider()
        client = AIClient(provider, max_retries=0, total_timeout_seconds=20, retry_base_delay_seconds=0, max_retry_delay_seconds=0)
        result = await RequirementsAnalysisWorkflowAgent(client, model="fake-s09", max_tokens=1500, temperature=0).run(make_context(), {})
        self.assertEqual(result.result.result_type, "requirements_analysis")
        self.assertEqual(result.result.features, ["逐行统计"])
        self.assertEqual(provider.calls, 1)
