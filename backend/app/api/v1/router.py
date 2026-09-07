from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.agents import router as agents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.campus import router as campus_router
from app.api.v1.community import router as community_router
from app.api.v1.courses import router as courses_router
from app.api.v1.health import router as health_router
from app.api.v1.learning import router as learning_router
from app.api.v1.learning_reports import router as learning_reports_router
from app.api.v1.projects import router as projects_router
from app.api.v1.project_context import router as project_context_router
from app.api.v1.statistics import router as statistics_router
from app.api.v1.teaching import router as teaching_router
from app.api.v1.users import router as users_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.workspace import router as workspace_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(campus_router)
api_router.include_router(teaching_router)
api_router.include_router(users_router)
api_router.include_router(projects_router)
api_router.include_router(project_context_router)
api_router.include_router(statistics_router)
api_router.include_router(community_router)
api_router.include_router(workspace_router)
api_router.include_router(courses_router)
api_router.include_router(learning_router)
api_router.include_router(learning_reports_router)
api_router.include_router(workflows_router)
api_router.include_router(ai_router)
api_router.include_router(agents_router)
