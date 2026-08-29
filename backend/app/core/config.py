from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _read_cors_origins(raw_value: str) -> tuple[str, ...]:
    origins = tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())
    return origins or ("http://localhost:5173",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_name: str = Field(default="ScholarHub API", min_length=1)
    app_version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    debug: bool = False
    api_v1_prefix: str = Field(
        default="/api/v1", pattern=r"^/[a-zA-Z0-9/_-]+$"
    )
    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
        repr=False,
    )
    database_url: str | None = Field(default=None, repr=False)

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if not normalized.startswith("mysql+pymysql://"):
            raise ValueError("DATABASE_URL 必须使用 mysql+pymysql 驱动")
        return normalized

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return _read_cors_origins(self.cors_origins_raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()
