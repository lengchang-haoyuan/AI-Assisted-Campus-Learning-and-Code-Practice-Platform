from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()

