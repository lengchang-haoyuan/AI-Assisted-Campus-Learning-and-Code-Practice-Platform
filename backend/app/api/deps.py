from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_security_settings, get_settings
from app.core.database import get_session_factory
from app.core.exceptions import AuthenticationRequiredError
from app.core.security import InvalidAccessTokenError, SecurityService
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService, UserIdentity
from app.services.health import HealthService
from app.services.project import ProjectService

bearer_scheme = HTTPBearer(auto_error=False)


def get_db_session() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_health_service() -> HealthService:
    return HealthService(get_settings())


DatabaseSession = Annotated[Session, Depends(get_db_session)]
HealthServiceDependency = Annotated[HealthService, Depends(get_health_service)]


def get_security_service() -> SecurityService:
    return SecurityService(get_security_settings())


SecurityDependency = Annotated[SecurityService, Depends(get_security_service)]


def get_auth_service(
    session: DatabaseSession, security: SecurityDependency
) -> AuthService:
    return AuthService(UserRepository(session), security)


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


def get_token_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    security: SecurityDependency,
) -> int:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationRequiredError("缺少有效的访问令牌")
    try:
        return security.get_user_id(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise AuthenticationRequiredError("访问令牌无效或已过期") from exc


TokenUserId = Annotated[int, Depends(get_token_user_id)]


def get_current_user(
    user_id: TokenUserId,
    session: DatabaseSession,
    security: SecurityDependency,
) -> UserIdentity:
    return AuthService(UserRepository(session), security).get_current_user(user_id)

CurrentUser = Annotated[UserIdentity, Depends(get_current_user)]


def get_project_service(session: DatabaseSession) -> ProjectService:
    return ProjectService(ProjectRepository(session))


ProjectServiceDependency = Annotated[ProjectService, Depends(get_project_service)]
