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
from app.repositories.project_context import ProjectContextRepository
from app.repositories.community import CommunityRepository
from app.repositories.course import CourseRepository
from app.repositories.learning import LearningRepository
from app.repositories.user import UserRepository
from app.repositories.workflow import WorkflowRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.auth import AuthService, UserIdentity
from app.services.community import CommunityService
from app.services.course import CourseService
from app.services.health import HealthService
from app.services.learning import LearningService
from app.services.project import ProjectService
from app.services.project_context import ProjectContextService
from app.services.workflow import WorkflowService
from app.services.workspace import WorkspaceService

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


def get_project_context_service(session: DatabaseSession) -> ProjectContextService:
    return ProjectContextService(ProjectContextRepository(session))


ProjectContextServiceDependency = Annotated[
    ProjectContextService, Depends(get_project_context_service)
]


def get_community_service(session: DatabaseSession) -> CommunityService:
    return CommunityService(CommunityRepository(session))


CommunityServiceDependency = Annotated[
    CommunityService, Depends(get_community_service)
]


def get_workspace_service(session: DatabaseSession) -> WorkspaceService:
    return WorkspaceService(WorkspaceRepository(session))


WorkspaceServiceDependency = Annotated[WorkspaceService, Depends(get_workspace_service)]


def get_course_service(session: DatabaseSession) -> CourseService:
    return CourseService(CourseRepository(session))


CourseServiceDependency = Annotated[CourseService, Depends(get_course_service)]


def get_learning_service(session: DatabaseSession) -> LearningService:
    return LearningService(LearningRepository(session))


LearningServiceDependency = Annotated[
    LearningService, Depends(get_learning_service)
]


def get_workflow_service(session: DatabaseSession) -> WorkflowService:
    return WorkflowService(WorkflowRepository(session))


WorkflowServiceDependency = Annotated[
    WorkflowService, Depends(get_workflow_service)
]
