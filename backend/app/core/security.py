from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

import jwt
from jwt.exceptions import InvalidTokenError as JWTInvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import SecuritySettings

_password_hash = PasswordHash.recommended()
_dummy_password_hash = _password_hash.hash(token_urlsafe(32))


class InvalidAccessTokenError(ValueError):
    """访问令牌无效、过期或缺少必要声明。"""


@dataclass(frozen=True, slots=True)
class AccessToken:
    value: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class TokenIdentity:
    user_id: int
    auth_version: int


class SecurityService:
    def __init__(self, settings: SecuritySettings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._expire_minutes = settings.jwt_expire_minutes

    def hash_password(self, password: str) -> str:
        return _password_hash.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return _password_hash.verify(password, password_hash)
        except (UnknownHashError, ValueError):
            return False

    def perform_dummy_password_check(self, password: str) -> None:
        _password_hash.verify(password, _dummy_password_hash)

    def create_access_token(self, user_id: int, auth_version: int = 0) -> AccessToken:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(minutes=self._expire_minutes)
        token = jwt.encode(
            {
                "sub": str(user_id),
                "iat": issued_at,
                "exp": expires_at,
                "ver": auth_version,
            },
            self._secret,
            algorithm=self._algorithm,
        )
        return AccessToken(value=token, expires_in=self._expire_minutes * 60)

    def get_user_id(self, token: str) -> int:
        return self.get_identity(token).user_id

    def get_identity(self, token: str) -> TokenIdentity:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["sub", "iat", "exp", "ver"]},
            )
            user_id = int(payload["sub"])
            auth_version = payload["ver"]
            if user_id <= 0 or type(auth_version) is not int or auth_version < 0:
                raise ValueError
            return TokenIdentity(user_id=user_id, auth_version=auth_version)
        except (JWTInvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise InvalidAccessTokenError("访问令牌无效或已过期") from exc
