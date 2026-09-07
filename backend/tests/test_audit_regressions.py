import unittest
from threading import get_ident
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from app.api.deps import get_auth_service, get_campus_service
from app.core.exceptions import ConflictError, RateLimitError
from app.main import create_app
from app.models.enums import RecordType, TaskStatus, WorkflowStatus
from app.repositories.campus import CampusRepository
from app.repositories.workflow import WorkflowRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.rate_limit import SensitiveActionLimiter, get_sensitive_action_limiter
from app.services.slider_captcha import SliderTicket, get_slider_captcha_service
from app.services.workflow import WorkflowService, WorkflowUpdateData
from app.services.workspace import LearningRecordCreateData, WorkspaceService
from tests.test_api_foundation import request
from tests.test_auth import create_security_service, create_user
from tests.test_workflow import make_node, make_workflow
from tests.test_workspace import make_task_model


class WorkspaceRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=WorkspaceRepository)
        self.service = WorkspaceService(self.repository)

    def test_cancelled_task_cannot_be_completed(self) -> None:
        task = make_task_model()
        task.status = TaskStatus.CANCELLED
        self.repository.get_task.return_value = task
        with self.assertRaises(ConflictError):
            self.service.complete_task(task.id, task.user_id)
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertIsNone(task.completed_at)
        self.repository.update_task.assert_not_called()

    def test_active_tasks_still_complete(self) -> None:
        for status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            with self.subTest(status=status):
                task = make_task_model()
                task.status = status
                self.repository.get_task.return_value = task
                self.repository.update_task.side_effect = lambda item: item
                result = self.service.complete_task(task.id, task.user_id)
                self.assertEqual(result.status, TaskStatus.COMPLETED)
                self.assertIsNotNone(result.completed_at)

    def test_records_require_a_supported_source(self) -> None:
        for kind in (RecordType.PROJECT, RecordType.COURSE, RecordType.TASK):
            with self.subTest(kind=kind), self.assertRaises(ConflictError):
                self.service.create_record(1, LearningRecordCreateData(
                    title="来源校验", content=None, record_type=kind,
                    duration_minutes=30, project_id=None, occurred_at=None,
                ))
        self.repository.create_record.assert_not_called()


class WorkflowStatusRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=WorkflowRepository)
        self.workflow = make_workflow(nodes=[make_node(21, "requirements_analysis", "需求")])
        self.repository.get_workflow.return_value = self.workflow
        self.repository.update_workflow.side_effect = lambda item: item
        self.service = WorkflowService(self.repository)

    def test_execution_statuses_cannot_be_forged(self) -> None:
        for status in (
            WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED, WorkflowStatus.STALE,
        ):
            with self.subTest(status=status), self.assertRaises(ConflictError):
                self.service.update_workflow(11, 1, WorkflowUpdateData({"status": status}))
        self.assertEqual(self.workflow.status, WorkflowStatus.DRAFT)
        self.repository.update_workflow.assert_not_called()

    def test_ready_and_draft_remain_editable(self) -> None:
        for status in (WorkflowStatus.READY, WorkflowStatus.DRAFT):
            result = self.service.update_workflow(11, 1, WorkflowUpdateData({"status": status}))
            self.assertEqual(result.status, status)

    def test_running_workflow_cannot_reset_status(self) -> None:
        self.workflow.status = WorkflowStatus.RUNNING
        for status in (WorkflowStatus.DRAFT, WorkflowStatus.READY):
            with self.subTest(status=status), self.assertRaises(ConflictError):
                self.service.update_workflow(11, 1, WorkflowUpdateData({"status": status}))
        self.repository.update_workflow.assert_not_called()

    def test_completed_workflow_can_be_renamed_without_status_change(self) -> None:
        self.workflow.status = WorkflowStatus.COMPLETED
        result = self.service.update_workflow(11, 1, WorkflowUpdateData({"name": "新名称"}))
        self.assertEqual(result.name, "新名称")
        self.assertEqual(result.status, WorkflowStatus.COMPLETED)

    def test_empty_workflow_still_cannot_be_ready(self) -> None:
        self.workflow.nodes = []
        with self.assertRaises(ConflictError):
            self.service.update_workflow(
                11, 1, WorkflowUpdateData({"status": WorkflowStatus.READY}),
            )
        self.repository.update_workflow.assert_not_called()


class AuthLimitRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.limiter = SensitiveActionLimiter()
        self.auth = Mock()
        self.campus = Mock()
        self.captcha = Mock()
        self.captcha.create_challenge.return_value = SliderTicket("x" * 43, 120)
        self.captcha.verify.return_value = SliderTicket("y" * 43, 60)
        self.app.dependency_overrides[get_sensitive_action_limiter] = lambda: self.limiter
        self.app.dependency_overrides[get_auth_service] = lambda: self.auth
        self.app.dependency_overrides[get_campus_service] = lambda: self.campus
        self.app.dependency_overrides[get_slider_captcha_service] = lambda: self.captcha

    def test_both_registration_paths_share_limit_before_hashing(self) -> None:
        user = create_user(create_security_service())
        self.auth.register.return_value = user
        self.campus.register_with_invitation.return_value = user
        base = {
            "username": "audit_student", "email": "audit@example.com",
            "password": "password-test",
        }
        for index in range(8):
            body = dict(base)
            if index % 2:
                body["invite_token"] = "x" * 43
            response = request(self.app, "POST", "/api/v1/auth/register", body=body)
            self.assertEqual(response.status_code, 201)
        for body in (base, {**base, "invite_token": "x" * 43}):
            response = request(self.app, "POST", "/api/v1/auth/register", body=body)
            self.assertEqual(response.status_code, 429)
        self.assertEqual(self.auth.register.call_count, 4)
        self.assertEqual(self.campus.register_with_invitation.call_count, 4)

    def test_slider_endpoints_limit_before_allocating_or_verifying(self) -> None:
        for endpoint, body, method in (
            ("challenge", None, self.captcha.create_challenge),
            ("verify", {"challenge_id": "x" * 43, "position": 100}, self.captcha.verify),
        ):
            with self.subTest(endpoint=endpoint):
                for _ in range(30):
                    response = request(
                        self.app, "POST", f"/api/v1/auth/slider/{endpoint}", body=body,
                    )
                    self.assertEqual(response.status_code, 200)
                response = request(self.app, "POST", f"/api/v1/auth/slider/{endpoint}", body=body)
                self.assertEqual(response.status_code, 429)
                self.assertEqual(method.call_count, 30)

    def test_limit_recovers_after_window(self) -> None:
        with patch("app.services.rate_limit.monotonic", return_value=100):
            self.limiter.check("registration", limit=1, window_seconds=300)
            with self.assertRaises(RateLimitError):
                self.limiter.check("registration", limit=1, window_seconds=300)
        with patch("app.services.rate_limit.monotonic", return_value=400):
            self.limiter.check("registration", limit=1, window_seconds=300)

    def test_sync_registration_runs_outside_event_loop_thread(self) -> None:
        event_loop_thread = get_ident()
        worker_threads = []
        user = create_user(create_security_service())

        def register_user(**kwargs):
            worker_threads.append(get_ident())
            return user

        self.auth.register.side_effect = register_user
        response = request(self.app, "POST", "/api/v1/auth/register", body={
            "username": "audit_student", "email": "audit@example.com", "password": "password-test",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(worker_threads), 1)
        self.assertNotEqual(worker_threads[0], event_loop_thread)


class CampusLockRegressionTests(unittest.TestCase):
    """用真实 Session 和连接池验证生命周期，仅模拟连接级命名锁函数。"""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", poolclass=QueuePool, pool_size=1, max_overflow=0)
        self.engine.dialect.name = "mysql"
        self.held = False
        self.lock_available = True
        self.returned_while_locked = []

        @event.listens_for(self.engine, "connect")
        def configure(connection, record):
            def acquire(name, timeout):
                self.held = self.lock_available
                return int(self.lock_available)

            def release(name):
                result = int(self.held)
                self.held = False
                return result

            connection.create_function("GET_LOCK", 2, acquire)
            connection.create_function("RELEASE_LOCK", 1, release)

        @event.listens_for(self.engine, "checkin")
        def check_return(connection, record):
            self.returned_while_locked.append(self.held)

        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE audit_probe (value INTEGER UNIQUE)"))
        self.session = Session(self.engine)
        self.repository = CampusRepository(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def assert_released(self) -> None:
        self.assertFalse(self.held)
        self.assertNotIn(True, self.returned_while_locked)
        self.assertIs(self.session.bind, self.engine)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    def test_commit_releases_lock_before_connection_returns_to_pool(self) -> None:
        with self.repository.transaction():
            self.session.execute(text("INSERT INTO audit_probe VALUES (1)"))
        self.assert_released()
        self.assertEqual(self.session.scalar(text("SELECT COUNT(*) FROM audit_probe")), 1)

    def test_exception_rolls_back_and_releases_lock(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "test rollback"):
            with self.repository.transaction():
                self.session.execute(text("INSERT INTO audit_probe VALUES (1)"))
                raise RuntimeError("test rollback")
        self.assert_released()
        self.assertEqual(self.session.scalar(text("SELECT COUNT(*) FROM audit_probe")), 0)

    def test_integrity_error_rolls_back_and_releases_lock(self) -> None:
        with self.assertRaises(ConflictError):
            with self.repository.transaction():
                self.session.execute(text("INSERT INTO audit_probe VALUES (1), (1)"))
        self.assert_released()
        self.assertEqual(self.session.scalar(text("SELECT COUNT(*) FROM audit_probe")), 0)

    def test_lock_timeout_does_not_enter_transaction_body(self) -> None:
        self.lock_available = False
        with self.assertRaises(ConflictError):
            with self.repository.transaction():
                self.fail("未获得命名锁时不能进入业务事务")
        self.assert_released()
