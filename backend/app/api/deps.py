from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.services.health import HealthService


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
