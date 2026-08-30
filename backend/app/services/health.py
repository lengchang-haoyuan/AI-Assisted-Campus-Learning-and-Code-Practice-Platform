from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class HealthStatus:
    status: str
    service: str
    version: str


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_status(self) -> HealthStatus:
        return HealthStatus(
            status="ok",
            service=self._settings.app_name,
            version=self._settings.app_version,
        )
