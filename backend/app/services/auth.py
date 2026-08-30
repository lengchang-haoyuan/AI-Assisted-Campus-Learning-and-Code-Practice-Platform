from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import (
    AuthenticationRequiredError,
    ConflictError,
    PermissionDeniedError,
)
from app.core.security import AccessToken, SecurityService
from app.models.user import User
from app.repositories.user import DuplicateUserError, UserRepository


@dataclass(frozen=True, slots=True)
class UserIdentity:
    id: int
    username: str
    email: str
    avatar_url: str | None
    bio: str | None
    is_active: bool
    created_at: datetime


class AuthService:
    def __init__(
        self, repository: UserRepository, security: SecurityService
    ) -> None:
        self._repository = repository
        self._security = security

    def register(self, *, username: str, email: str, password: str) -> UserIdentity:
        if (
            self._repository.get_by_username(username) is not None
            or self._repository.get_by_email(email) is not None
        ):
            raise ConflictError("用户名或邮箱已被使用")

        user = User(
            username=username,
            email=email,
            password_hash=self._security.hash_password(password),
        )
        try:
            created_user = self._repository.create(user)
        except DuplicateUserError as exc:
            raise ConflictError("用户名或邮箱已被使用") from exc
        return self._to_identity(created_user)

    def login(self, *, identifier: str, password: str) -> AccessToken:
        user = self._repository.get_by_identifier(identifier)
        if user is None:
            self._security.perform_dummy_password_check(password)
            raise AuthenticationRequiredError("用户名/邮箱或密码错误")
        if not self._security.verify_password(password, user.password_hash):
            raise AuthenticationRequiredError("用户名/邮箱或密码错误")
        if not user.is_active:
            raise PermissionDeniedError("账号当前不可用")
        return self._security.create_access_token(user.id)

    def get_current_user(self, user_id: int) -> UserIdentity:
        user = self._repository.get_by_id(user_id)
        if user is None:
            raise AuthenticationRequiredError("登录状态无效或已过期")
        if not user.is_active:
            raise PermissionDeniedError("账号当前不可用")
        return self._to_identity(user)

    @staticmethod
    def _to_identity(user: User) -> UserIdentity:
        return UserIdentity(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            bio=user.bio,
            is_active=user.is_active,
            created_at=user.created_at,
        )
