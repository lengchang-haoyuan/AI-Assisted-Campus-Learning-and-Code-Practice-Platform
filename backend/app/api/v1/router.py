from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.community import router as community_router
from app.api.v1.health import router as health_router
from app.api.v1.projects import router as projects_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(projects_router)
api_router.include_router(community_router)
