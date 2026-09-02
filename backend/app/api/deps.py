from collections.abc import AsyncGenerator, Generator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
from sqlalchemy.orm import Session

from app.ai.client import AIClient
from app.ai.deepseek import DeepSeekProvider
from app.agents.project_analysis import ProjectAnalysisAgent
from app.agents.project_review import ProjectReviewAgent
from app.agents.prompt_agent import PromptAgent
from app.agents.learning_report import LearningReportAgent
from app.agents.schemas import AgentType
from app.context.context_manager import ContextManager
from app.core.config import (
    AISettings,
    get_ai_settings,
    get_security_settings,
    get_settings,
)
from app.core.database import get_session_factory
from app.core.exceptions import AuthenticationRequiredError
from app.core.security import InvalidAccessTokenError, SecurityService
from app.repositories.project import ProjectRepository
from app.repositories.statistics import StatisticsRepository
from app.repositories.agent import AgentRepository
from app.repositories.project_context import ProjectContextRepository
from app.repositories.community import CommunityRepository
from app.repositories.course import CourseRepository
from app.repositories.learning import LearningRepository
from app.repositories.learning_report import LearningReportRepository
from app.repositories.user import UserRepository
from app.repositories.workflow import WorkflowRepository
from app.repositories.workflow_execution import WorkflowExecutionRepository
from app.repositories.workspace import WorkspaceRepository
from app.services.auth import AuthService, UserIdentity
from app.services.ai import AIService
from app.services.agent import AgentService
from app.services.community import CommunityService
from app.services.course import CourseService
from app.services.health import HealthService
from app.services.learning import LearningService
from app.services.learning_report import LearningReportService
from app.services.project import ProjectService
from app.services.statistics import StatisticsService
from app.services.project_context import ProjectContextService
from app.services.workflow import WorkflowService
from app.services.workspace import WorkspaceService
from app.workflow.agents import (
    ArchitectureDesignWorkflowAgent,
    RequirementsAnalysisWorkflowAgent,
    TechStackAnalysisWorkflowAgent,
)
from app.workflow.engine import WorkflowEngine, WorkflowEngineLimits
from app.workflow.registry import WorkflowAgentRegistry

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


def get_statistics_service(session: DatabaseSession) -> StatisticsService:
    return StatisticsService(StatisticsRepository(session))


StatisticsServiceDependency = Annotated[
    StatisticsService, Depends(get_statistics_service)
]


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


def build_ai_client(
    settings: AISettings, http_client: httpx.AsyncClient
) -> AIClient:
    provider = DeepSeekProvider(
        http_client,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        connect_timeout_seconds=settings.ai_connect_timeout_seconds,
        request_timeout_seconds=settings.ai_total_timeout_seconds,
    )
    return AIClient(
        provider,
        total_timeout_seconds=settings.ai_total_timeout_seconds,
        max_retries=settings.ai_max_retries,
        retry_base_delay_seconds=settings.ai_retry_base_delay_seconds,
        max_retry_delay_seconds=settings.ai_max_retry_delay_seconds,
    )


def build_workflow_registry(
    client: AIClient, settings: AISettings
) -> WorkflowAgentRegistry:
    registry = WorkflowAgentRegistry()
    shared_options = {
        "model": settings.deepseek_model,
        "temperature": settings.ai_agent_temperature,
    }
    registry.register(
        "requirements_analysis",
        lambda max_tokens: RequirementsAnalysisWorkflowAgent(
            client, max_tokens=max_tokens, **shared_options
        ),
    )
    registry.register(
        "tech_stack_analysis",
        lambda max_tokens: TechStackAnalysisWorkflowAgent(
            client, max_tokens=max_tokens, **shared_options
        ),
    )
    registry.register(
        "architecture_design",
        lambda max_tokens: ArchitectureDesignWorkflowAgent(
            client, max_tokens=max_tokens, **shared_options
        ),
    )
    return registry


async def get_workflow_execution_service(
    session: DatabaseSession,
) -> AsyncGenerator[WorkflowService, None]:
    settings = get_ai_settings()
    async with httpx.AsyncClient(follow_redirects=False) as http_client:
        client = build_ai_client(settings, http_client)
        execution_repository = WorkflowExecutionRepository(session)
        engine = WorkflowEngine(
            execution_repository,
            build_workflow_registry(client, settings),
            ContextManager(),
            WorkflowEngineLimits(
                max_nodes=settings.workflow_max_nodes,
                max_rounds=settings.workflow_max_rounds,
                max_node_tokens=settings.ai_agent_max_tokens,
                max_completion_tokens=settings.workflow_max_completion_tokens,
                total_timeout_seconds=settings.workflow_total_timeout_seconds,
                recovery_timeout_seconds=(
                    settings.workflow_recovery_timeout_seconds
                ),
                max_concurrency=settings.workflow_max_concurrency,
            ),
        )
        yield WorkflowService(
            WorkflowRepository(session),
            execution_repository,
            engine,
        )


WorkflowExecutionServiceDependency = Annotated[
    WorkflowService, Depends(get_workflow_execution_service)
]


async def get_ai_service() -> AsyncGenerator[AIService, None]:
    settings = get_ai_settings()
    async with httpx.AsyncClient(follow_redirects=False) as http_client:
        client = build_ai_client(settings, http_client)
        yield AIService(
            client,
            default_model=settings.deepseek_model,
            api_key_env_name="DEEPSEEK_API_KEY",
        )


AIServiceDependency = Annotated[AIService, Depends(get_ai_service)]


async def get_agent_service(
    session: DatabaseSession,
) -> AsyncGenerator[AgentService, None]:
    settings = get_ai_settings()
    async with httpx.AsyncClient(follow_redirects=False) as http_client:
        client = build_ai_client(settings, http_client)
        agent_options = {
            "model": settings.deepseek_model,
            "max_tokens": settings.ai_agent_max_tokens,
            "temperature": settings.ai_agent_temperature,
        }
        agents = {
            AgentType.PROJECT_ANALYSIS: ProjectAnalysisAgent(client, **agent_options),
            AgentType.PROMPT: PromptAgent(client, **agent_options),
            AgentType.PROJECT_REVIEW: ProjectReviewAgent(client, **agent_options),
        }
        yield AgentService(
            AgentRepository(session),
            agents,
            api_key_env_name="DEEPSEEK_API_KEY",
        )


AgentServiceDependency = Annotated[AgentService, Depends(get_agent_service)]


async def get_learning_report_service(
    session: DatabaseSession,
) -> AsyncGenerator[LearningReportService, None]:
    settings = get_ai_settings()
    async with httpx.AsyncClient(follow_redirects=False) as http_client:
        client = build_ai_client(settings, http_client)
        agent = LearningReportAgent(
            client,
            model=settings.deepseek_model,
            max_tokens=settings.ai_agent_max_tokens,
            temperature=settings.ai_agent_temperature,
        )
        yield LearningReportService(LearningReportRepository(session), agent)


LearningReportServiceDependency = Annotated[
    LearningReportService, Depends(get_learning_report_service)
]
