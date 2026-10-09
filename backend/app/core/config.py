"""Centralized configuration settings for OrbitOpt using pydantic-settings."""

from functools import lru_cache
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env."""

    PROJECT_NAME: str = "OrbitOpt"
    PROJECT_TITLE: str = "OrbitOpt - Autonomous Ground Station Scheduling API"
    PROJECT_DESCRIPTION: str = (
        "API for Autonomous Ground Station Scheduling for Multi-Satellite Downlink optimization, "
        "conflict resolution, and schedule validation."
    )
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Database Configuration
    # Uses SQLite in-memory or file by default for local lightweight / test runs,
    # or PostgreSQL when configured via DATABASE_URL.
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./orbitopt.db",
        description="Async database connection string. E.g. postgresql+asyncpg://user:pass@localhost:5432/orbitopt",
    )
    SYNC_DATABASE_URL: str = Field(
        default="sqlite:///./orbitopt.db",
        description="Synchronous database connection string for Alembic migrations. E.g. postgresql://user:pass@localhost:5432/orbitopt",
    )

    # Scheduling Defaults
    DEFAULT_SETUP_TIME_SECONDS: int = 120
    DEFAULT_OPTIMIZER_TIME_LIMIT_SECONDS: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton instance."""
    return Settings()
