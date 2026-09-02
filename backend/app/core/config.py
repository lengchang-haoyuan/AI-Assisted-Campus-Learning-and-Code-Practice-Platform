from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
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


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=5, le=1440)


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    ai_provider: Literal["deepseek"] = "deepseek"
    deepseek_api_key: SecretStr | None = Field(default=None, repr=False)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = Field(
        default="deepseek-v4-flash",
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    ai_connect_timeout_seconds: float = Field(default=5.0, ge=0.1, le=30.0)
    ai_total_timeout_seconds: float = Field(default=30.0, ge=1.0, le=180.0)
    ai_max_retries: int = Field(default=1, ge=0, le=2)
    ai_retry_base_delay_seconds: float = Field(default=0.25, ge=0.05, le=2.0)
    ai_max_retry_delay_seconds: float = Field(default=2.0, ge=0.1, le=10.0)
    ai_agent_max_tokens: int = Field(default=3000, ge=256, le=4096)
    ai_agent_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    workflow_max_nodes: int = Field(default=12, ge=1, le=100)
    workflow_max_rounds: int = Field(default=12, ge=1, le=100)
    workflow_max_completion_tokens: int = Field(
        default=9000, ge=256, le=32768
    )
    workflow_total_timeout_seconds: float = Field(default=90.0, ge=5.0, le=600.0)
    workflow_recovery_timeout_seconds: float = Field(
        default=120.0, ge=5.0, le=900.0
    )
    workflow_max_concurrency: Literal[1] = 1

    @field_validator("deepseek_api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: object) -> object | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("deepseek_base_url")
    @classmethod
    def validate_deepseek_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if normalized != "https://api.deepseek.com":
            raise ValueError("DEEPSEEK_BASE_URL 必须是 https://api.deepseek.com")
        return normalized

    @model_validator(mode="after")
    def validate_timeout_and_retry_bounds(self) -> "AISettings":
        if self.ai_connect_timeout_seconds > self.ai_total_timeout_seconds:
            raise ValueError("AI_CONNECT_TIMEOUT_SECONDS 不能大于总超时")
        if self.ai_retry_base_delay_seconds > self.ai_max_retry_delay_seconds:
            raise ValueError("AI_RETRY_BASE_DELAY_SECONDS 不能大于最大重试延迟")
        if self.workflow_max_rounds > self.workflow_max_nodes:
            raise ValueError("WORKFLOW_MAX_ROUNDS 不能大于 WORKFLOW_MAX_NODES")
        if (
            self.workflow_recovery_timeout_seconds
            < self.workflow_total_timeout_seconds
        ):
            raise ValueError("Workflow 恢复超时不能小于运行总超时")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_security_settings() -> SecuritySettings:
    return SecuritySettings()


@lru_cache
def get_ai_settings() -> AISettings:
    return AISettings()
