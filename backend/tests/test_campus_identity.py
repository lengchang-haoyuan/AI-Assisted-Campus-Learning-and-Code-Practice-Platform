from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import RLock, Thread
import unittest

from app.api.deps import get_campus_service, get_current_user
from app.main import create_app
from app.core.config import SecuritySettings
from app.core.exceptions import (
    AuthenticationRequiredError,
    ConflictError,
    InputError,
    PermissionDeniedError,
)
from app.core.security import SecurityService
from app.models.campus import (
    AccountAudit,
    CampusInvitation,
    CampusMembership,
    CampusRole,
    InvitationStatus,
    MembershipStatus,
    PasswordReset,
)
from app.models.user import User
from app.services.auth import UserIdentity
from app.services.campus import CampusService
from tests.test_auth import request


class FakeCampusRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}
        self.memberships: dict[int, CampusMembership] = {}
        self.invitations: dict[bytes, CampusInvitation] = {}
        self.resets: dict[bytes, PasswordReset] = {}
        self.audits: list[AccountAudit] = []
        self._next_id = 100
        self._lock = RLock()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            yield

    def add(self, value: object) -> None:
        now = datetime.now(UTC)
        if getattr(value, "id", None) is None:
            setattr(value, "id", self._next_id)
            self._next_id += 1
        if hasattr(value, "created_at") and getattr(value, "created_at", None) is None:
            setattr(value, "created_at", now)
            setattr(value, "updated_at", now)
        if isinstance(value, User):
            if value.is_active is None:
                value.is_active = True
            self.users[value.id] = value
        elif isinstance(value, CampusMembership):
            self.memberships[value.user_id] = value
        elif isinstance(value, CampusInvitation):
            self.invitations[value.token_digest] = value
        elif isinstance(value, PasswordReset):
            self.resets[value.token_digest] = value
        elif isinstance(value, AccountAudit):
            self.audits.append(value)

    def flush(self) -> None:
        return None

    def user(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def user_by_username(self, username: str) -> User | None:
        return next((user for user in self.users.values() if user.username == username), None)

    def user_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    def membership(self, user_id: int) -> CampusMembership | None:
        return self.memberships.get(user_id)

    def invitation(self, digest: bytes) -> CampusInvitation | None:
        return self.invitations.get(digest)

    def invitation_by_id(self, invitation_id: int) -> CampusInvitation | None:
        return next((value for value in self.invitations.values() if value.id == invitation_id), None)

    def password_reset(self, digest: bytes) -> PasswordReset | None:
        return self.resets.get(digest)

    def revoke_pending_resets(self, user_id: int, now: datetime) -> None:
        for value in self.resets.values():
            if value.user_id == user_id and value.consumed_at is None and value.revoked_at is None:
                value.revoked_at = now

    def active_administrators(self) -> list[CampusMembership]:
        return [
            membership
            for membership in self.memberships.values()
            if membership.role == CampusRole.ADMINISTRATOR
            and membership.status == MembershipStatus.ACTIVE
            and self.users[membership.user_id].is_active
        ]


def make_user(user_id: int, security: SecurityService) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        username=f"user_{user_id}",
        email=f"user{user_id}@example.com",
        password_hash=security.hash_password("correct-password"),
        auth_version=0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def identity(user: User) -> UserIdentity:
    return UserIdentity(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar_url=None,
        bio=None,
        is_active=user.is_active,
        created_at=user.created_at,
        auth_version=user.auth_version or 0,
    )


class CampusIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.security = SecurityService(
            SecuritySettings(
                jwt_secret="test-secret-that-is-at-least-thirty-two-bytes",
                jwt_algorithm="HS256",
                jwt_expire_minutes=30,
            )
        )
        self.admin = make_user(1, self.security)
        self.student = make_user(2, self.security)
        self.other = make_user(3, self.security)
        self.repository = FakeCampusRepository([self.admin, self.student, self.other])
        self.service = CampusService(self.repository, self.security)
        self.service.initialize_first_admin(user_id=1, reason="isolated test")
        self.admin_identity = identity(self.admin)

    def test_invitation_is_bound_and_concurrent_redeem_grants_once(self) -> None:
        invitation, token = self.service.issue_invitation(
            self.admin_identity,
            target_user_id=self.student.id,
            target_email=None,
            role=CampusRole.STUDENT,
            expires_in_hours=1,
            reason="verified learner",
        )
        self.assertEqual(invitation.status, InvitationStatus.PENDING)
        with self.assertRaises(PermissionDeniedError):
            self.service.redeem_invitation(identity(self.other), token=token)
        stale_identity = identity(self.student)
        outcomes: list[str] = []

        def redeem() -> None:
            try:
                self.service.redeem_invitation(stale_identity, token=token)
                outcomes.append("success")
            except AuthenticationRequiredError:
                outcomes.append("stale")

        threads = [Thread(target=redeem), Thread(target=redeem)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(outcomes), ["stale", "success"])
        self.assertEqual(len([m for m in self.repository.memberships.values() if m.user_id == 2]), 1)

    def test_student_cannot_manage_accounts_and_admin_invite_is_rejected(self) -> None:
        student_membership = CampusMembership(
            id=200,
            user_id=2,
            role=CampusRole.STUDENT,
            status=MembershipStatus.ACTIVE,
            verified_by_user_id=1,
            verified_at=datetime.now(UTC),
            revision=1,
        )
        self.repository.memberships[2] = student_membership
        with self.assertRaises(PermissionDeniedError):
            self.service.accounts(identity(self.student), query=None, page=1, page_size=20)
        with self.assertRaises(InputError):
            self.service.issue_invitation(
                self.admin_identity,
                target_user_id=2,
                target_email=None,
                role=CampusRole.ADMINISTRATOR,
                expires_in_hours=1,
                reason="forged role",
            )

    def test_password_change_reset_replay_and_last_admin_are_protected(self) -> None:
        old_identity = identity(self.student)
        with self.assertRaises(InputError):
            self.service.change_password(
                old_identity, current_password="wrong-password", new_password="new-password"
            )
        self.service.change_password(
            old_identity,
            current_password="correct-password",
            new_password="new-password",
        )
        with self.assertRaises(AuthenticationRequiredError):
            self.service.me(old_identity)

        reset_token, _ = self.service.issue_password_reset(
            self.admin_identity, user_id=2, reason="identity verified"
        )
        self.service.reset_password(token=reset_token, new_password="reset-password")
        with self.assertRaises(ConflictError):
            self.service.reset_password(token=reset_token, new_password="another-password")

        with self.assertRaises(ConflictError):
            self.service.update_account(
                self.admin_identity,
                user_id=1,
                reason="must retain administrator",
                expected_revision=None,
                expected_auth_version=self.admin.auth_version,
                role=None,
                campus_status=None,
                account_enabled=False,
            )

    def test_token_version_round_trip(self) -> None:
        token = self.security.create_access_token(2, 7)
        token_identity = self.security.get_identity(token.value)
        self.assertEqual((token_identity.user_id, token_identity.auth_version), (2, 7))

    def test_email_invitation_can_register_atomically(self) -> None:
        _, token = self.service.issue_invitation(
            self.admin_identity,
            target_user_id=None,
            target_email="new-user@example.com",
            role=CampusRole.STUDENT,
            expires_in_hours=1,
            reason="verified email",
        )
        user = self.service.register_with_invitation(
            username="new_user",
            email="new-user@example.com",
            password="new-user-password",
            token=token,
        )
        self.assertEqual(self.repository.memberships[user.id].role, CampusRole.STUDENT)
        with self.assertRaises(ConflictError):
            self.service.register_with_invitation(
                username="other_user",
                email="new-user@example.com",
                password="other-password",
                token=token,
            )


class CampusIdentityAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.security = SecurityService(
            SecuritySettings(
                jwt_secret="test-secret-that-is-at-least-thirty-two-bytes",
                jwt_algorithm="HS256",
                jwt_expire_minutes=30,
            )
        )
        self.admin = make_user(1, self.security)
        self.student = make_user(2, self.security)
        self.repository = FakeCampusRepository([self.admin, self.student])
        self.service = CampusService(self.repository, self.security)
        self.service.initialize_first_admin(user_id=1, reason="isolated test")
        self.admin_identity = identity(self.admin)

    def test_anonymous_and_student_admin_access_are_rejected(self) -> None:
        anonymous_app = create_app()
        anonymous = request(anonymous_app, "GET", "/api/v1/campus/me")
        self.assertEqual(anonymous.status_code, 401)

        student_membership = CampusMembership(
            id=201,
            user_id=2,
            role=CampusRole.STUDENT,
            status=MembershipStatus.ACTIVE,
            verified_by_user_id=1,
            verified_at=datetime.now(UTC),
            revision=1,
        )
        self.repository.memberships[2] = student_membership
        application = create_app()
        application.dependency_overrides[get_current_user] = lambda: identity(self.student)
        application.dependency_overrides[get_campus_service] = lambda: self.service
        response = request(application, "GET", "/api/v1/campus/admin/accounts")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "permission_denied")

    def test_administrator_role_cannot_be_forged_through_invitation_api(self) -> None:
        application = create_app()
        application.dependency_overrides[get_current_user] = lambda: self.admin_identity
        application.dependency_overrides[get_campus_service] = lambda: self.service
        response = request(
            application,
            "POST",
            "/api/v1/campus/invitations",
            body={
                "target_user_id": 2,
                "role": "administrator",
                "expires_in_hours": 1,
                "reason": "forged role",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "input_error")


if __name__ == "__main__":
    unittest.main()
