from datetime import UTC, datetime
import os
from secrets import token_urlsafe
import unittest
from uuid import uuid4

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.api.deps import get_current_user, get_db_session
from app.api.practice_deps import get_practice_service
from app.main import create_app
from app.services.auth import UserIdentity
from tests.test_api_foundation import request
from tests.test_practice_service import build_service

NOW = datetime(2026, 10, 21, 8, tzinfo=UTC)


def current_user(owner_id=1):
    return UserIdentity(
        id=owner_id,
        username=f"student-{owner_id}",
        email=f"student-{owner_id}@example.com",
        avatar_url=None,
        bio=None,
        is_active=True,
        created_at=NOW,
    )


def forbid_database():
    raise AssertionError("本测试不得连接数据库")


def create_body(**changes):
    return {
        "template_id": "python-learning-csv",
        "template_version": "1.0",
        "expected_context_version": 1,
        "request_key": str(uuid4()),
        **changes,
    }


class PracticeAPITests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.service, self.repo, self.provider = build_service()
        self.user = current_user()
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_practice_service] = lambda: self.service
        self.app.dependency_overrides[get_db_session] = forbid_database

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def create_session(self, **changes):
        response = request(
            self.app,
            "POST",
            "/api/v1/projects/7/practice-sessions",
            body=create_body(**changes),
        )
        self.assertEqual(response.status_code, 201, response.body)
        return response.json()

    def action(self, item, action, **changes):
        return request(
            self.app,
            "POST",
            f"/api/v1/practice-sessions/{item['id']}/actions",
            body={
                "action": action,
                "expected_revision": item["revision"],
                "request_key": str(uuid4()),
                **changes,
            },
        )

    def test_create_start_wait_confirm_cancel_resume_and_get_use_real_router(self):
        item = self.create_session()
        self.assertEqual((item["status"], item["template_id"]), ("ready", "python-learning-csv"))
        self.assertEqual(self.provider.requests, [])
        response = self.action(item, "start")
        self.assertEqual(response.status_code, 200, response.body)
        item = response.json()
        self.assertEqual(item["status"], "waiting_confirmation")
        self.assertEqual(item["model_request"]["provider"], "fake")
        response = self.action(item, "confirm")
        self.assertEqual(response.status_code, 200, response.body)
        item = response.json()
        self.assertEqual((item["status"], item["current_step_key"]), ("waiting_submission", "implement"))
        item = self.action(item, "cancel").json()
        self.assertEqual(item["status"], "cancelled")
        item = self.action(item, "resume").json()
        self.assertEqual(item["status"], "waiting_submission")
        detail = request(self.app, "GET", f"/api/v1/practice-sessions/{item['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["revision"], item["revision"])
        history = request(self.app, "GET", "/api/v1/projects/7/practice-sessions?offset=0&limit=1")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["id"], item["id"])
        self.assertEqual(len(self.provider.requests), 1)

    def test_creation_and_action_replays_are_exposed_without_repeat_model(self):
        key = str(uuid4()).upper()
        item = self.create_session(request_key=key)
        replay = self.create_session(request_key=key.lower())
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["id"], item["id"])
        self.assertEqual(len(self.repo.state.sessions), 1)
        action_key = str(uuid4())
        started = self.action(item, "start", request_key=action_key)
        replay = self.action(item, "start", request_key=action_key)
        self.assertEqual(started.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(replay.json()["active_operation_id"], started.json()["active_operation_id"])
        conflict = self.action(started.json(), "explain", request_key=action_key)
        self.assertEqual(conflict.status_code, 409)
        version = self.action(item, "cancel")
        self.assertEqual(version.status_code, 409)
        self.assertEqual(len(self.provider.requests), 1)
        self.assertEqual(len(self.repo.state.events), 2)

    def test_all_five_routes_require_login_without_using_database_or_provider(self):
        self.app.dependency_overrides.pop(get_current_user)
        session_id = str(uuid4())
        for method, path, body in (
            ("POST", "/api/v1/projects/7/practice-sessions", create_body()),
            ("GET", "/api/v1/projects/7/practice-sessions", None),
            ("GET", f"/api/v1/practice-sessions/{session_id}", None),
            ("POST", f"/api/v1/practice-sessions/{session_id}/actions", {"action": "start", "expected_revision": 1, "request_key": str(uuid4())}),
            ("POST", f"/api/v1/practice-sessions/{session_id}/attempts", {}),
        ):
            with self.subTest(method=method, path=path):
                response = request(self.app, method, path, body=body)
                self.assertEqual(response.status_code, 401, response.body)
                self.assertEqual(response.json()["error"]["code"], "authentication_required")
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(self.repo.state.sessions, {})

    def test_other_user_cannot_read_act_or_learn_unsupported_submission_detail(self):
        item = self.create_session()
        self.user = current_user(2)
        operations = [
            ("GET", "/api/v1/projects/7/practice-sessions", None),
            ("GET", f"/api/v1/practice-sessions/{item['id']}", None),
            ("POST", f"/api/v1/practice-sessions/{item['id']}/actions", {"action": "review", "expected_revision": 1, "request_key": str(uuid4())}),
            ("POST", f"/api/v1/practice-sessions/{item['id']}/attempts", {
                "code": "private-placeholder", "declared_output": {}, "self_statement": None,
                "expected_revision": 1, "step_key": "implement", "request_key": str(uuid4())}),
        ]
        for method, path, body in operations:
            with self.subTest(path=path):
                response = request(self.app, method, path, body=body)
                self.assertEqual(response.status_code, 404, response.body)
                self.assertEqual(response.json()["error"]["code"], "resource_not_found")
        self.assertEqual(self.provider.requests, [])

    def test_request_schema_rejects_invalid_ids_versions_actions_and_extra_text(self):
        item = self.create_session()
        for body in (
            create_body(template_id="arbitrary"),
            create_body(template_version="2.0"),
            create_body(expected_context_version=0),
            create_body(request_key="invalid"),
            create_body(task="arbitrary-free-text"),
        ):
            with self.subTest(body=body):
                response = request(self.app, "POST", "/api/v1/projects/7/practice-sessions", body=body)
                self.assertEqual(response.status_code, 422, response.body)
        for changes in (
            {"action": "complete"},
            {"expected_revision": 0},
            {"request_key": "invalid"},
            {"attempt_id": "invalid"},
            {"question": "arbitrary-free-text"},
        ):
            with self.subTest(changes=changes):
                response = self.action(item, changes.get("action", "start"), **{key: value for key, value in changes.items() if key != "action"})
                self.assertEqual(response.status_code, 422, response.body)
        for path in (
            "/api/v1/practice-sessions/not-a-uuid",
            "/api/v1/projects/0/practice-sessions",
            "/api/v1/projects/7/practice-sessions?limit=101",
            "/api/v1/projects/7/practice-sessions?offset=-1",
        ):
            with self.subTest(path=path):
                response = request(self.app, "GET", path)
                self.assertEqual(response.status_code, 422, response.body)
        self.assertEqual(len(self.repo.state.sessions), 1)
        self.assertEqual(self.provider.requests, [])

    def test_unsupported_review_attempt_and_implement_confirm_are_explicit(self):
        item = self.create_session()
        response = self.action(item, "review")
        self.assertEqual(response.status_code, 422)
        response = request(
            self.app,
            "POST",
            f"/api/v1/practice-sessions/{item['id']}/attempts",
            body={"code": "private-placeholder", "declared_output": {}},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(self.repo.state.events), 1)
        item = self.action(item, "start").json()
        item = self.action(item, "confirm").json()
        response = self.action(item, "confirm")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "conflict")
        self.assertEqual(self.service.get(1, item["id"])["status"], "waiting_submission")
        self.assertEqual(len(self.provider.requests), 1)


if __name__ == "__main__":
    unittest.main()
