from datetime import UTC, datetime
import os
from secrets import token_urlsafe
import unittest
from unittest.mock import Mock

from pydantic import SecretStr, ValidationError

os.environ.setdefault("JWT_SECRET", token_urlsafe(48))

from app.core.config import SecuritySettings
from app.core.exceptions import (
    AuthenticationRequiredError,
    ConflictError,
    PermissionDeniedError,
)
from app.core.security import InvalidAccessTokenError, SecurityService
from app.api.deps import get_auth_service
from app.main import create_app
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from tests.test_api_foundation import request


def create_security_service() -> SecurityService:
    return SecurityService(
        SecuritySettings(
            jwt_secret=SecretStr(token_urlsafe(48)),
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
        )
    )


def create_user(
    security: SecurityService,
    *,
    user_id: int = 1,
    password: str = "correct-password",
    is_active: bool = True,
) -> User:
    return User(
        id=user_id,
        username="student_01",
        email="student@example.com",
        password_hash=security.hash_password(password),
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class SecurityTests(unittest.TestCase):
    def test_short_jwt_secret_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SecuritySettings(
                jwt_secret=SecretStr("too-short"),
                jwt_algorithm="HS256",
                jwt_expire_minutes=30,
            )

    def test_password_hash_and_jwt_round_trip(self) -> None:
        security = create_security_service()
        password_hash = security.hash_password("correct-password")

        self.assertTrue(password_hash.startswith("$argon2id$"))
        self.assertNotIn("correct-password", password_hash)
        self.assertTrue(security.verify_password("correct-password", password_hash))
        self.assertFalse(security.verify_password("wrong-password", password_hash))

        token = security.create_access_token(42)
        self.assertEqual(security.get_user_id(token.value), 42)
        self.assertEqual(token.expires_in, 1800)
        with self.assertRaises(InvalidAccessTokenError):
            security.get_user_id(f"{token.value}tampered")


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.security = create_security_service()
        self.repository = Mock(spec=UserRepository)
        self.service = AuthService(self.repository, self.security)

    def test_register_hashes_password(self) -> None:
        self.repository.get_by_username.return_value = None
        self.repository.get_by_email.return_value = None
        self.repository.create.side_effect = lambda user: create_user(
            self.security,
            user_id=7,
            password="new-password",
        )

        user = self.service.register(
            username="student_01",
            email="student@example.com",
            password="new-password",
        )

        self.assertEqual(user.id, 7)
        submitted_user = self.repository.create.call_args.args[0]
        self.assertNotEqual(submitted_user.password_hash, "new-password")
        self.assertTrue(
            self.security.verify_password("new-password", submitted_user.password_hash)
        )

    def test_duplicate_registration_is_conflict(self) -> None:
        self.repository.get_by_username.return_value = create_user(self.security)
        with self.assertRaises(ConflictError):
            self.service.register(
                username="student_01",
                email="student@example.com",
                password="new-password",
            )
        self.repository.create.assert_not_called()

    def test_duplicate_email_is_conflict(self) -> None:
        self.repository.get_by_username.return_value = None
        self.repository.get_by_email.return_value = create_user(self.security)
        with self.assertRaises(ConflictError):
            self.service.register(
                username="another_student",
                email="student@example.com",
                password="new-password",
            )
        self.repository.create.assert_not_called()

    def test_unknown_user_and_wrong_password_share_error(self) -> None:
        self.repository.get_by_identifier.return_value = None
        with self.assertRaises(AuthenticationRequiredError) as unknown_error:
            self.service.login(identifier="missing", password="wrong-password")

        self.repository.get_by_identifier.return_value = create_user(self.security)
        with self.assertRaises(AuthenticationRequiredError) as password_error:
            self.service.login(identifier="student_01", password="wrong-password")

        self.assertEqual(str(unknown_error.exception), str(password_error.exception))

    def test_inactive_user_is_forbidden(self) -> None:
        self.repository.get_by_identifier.return_value = create_user(
            self.security, is_active=False
        )
        with self.assertRaises(PermissionDeniedError):
            self.service.login(
                identifier="student_01", password="correct-password"
            )


class AuthAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()

    def test_missing_and_invalid_token_return_401_without_database(self) -> None:
        missing = request(self.app, "GET", "/api/v1/users/me")
        invalid = request(
            self.app,
            "GET",
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        for response in (missing, invalid):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(
                response.json()["error"]["code"], "authentication_required"
            )
            self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_invalid_registration_payload_returns_422(self) -> None:
        self.app.dependency_overrides[get_auth_service] = lambda: Mock()
        response = request(
            self.app,
            "POST",
            "/api/v1/auth/register",
            body={"username": "x", "email": "invalid", "password": "short"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()
