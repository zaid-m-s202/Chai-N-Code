"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Central configuration.

    Every value can be overridden via an environment variable of the same
    (upper-case) name, or via a `.env` file placed next to ``manage.py``.
    """

    # --- Database -----------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg://cadastral:cadastral_dev_only@localhost:5432/cadastral"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Automatically normalize Supabase / Render postgres URLs to psycopg3 driver."""
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("postgres://"):
                return v_trimmed.replace("postgres://", "postgresql+psycopg://", 1)
            elif v_trimmed.startswith("postgresql://") and "+psycopg" not in v_trimmed and "+asyncpg" not in v_trimmed:
                return v_trimmed.replace("postgresql://", "postgresql+psycopg://", 1)
            return v_trimmed
        return v

    # --- Server & Deployment ------------------------------------------------
    PORT: int = 8000
    ENVIRONMENT: str = "production"

    # --- CORS ---------------------------------------------------------------
    # Comma-separated list of allowed origins. Standard Vercel domains (*.vercel.app)
    # are additionally matched via regex in CORSMiddleware.
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    # --- Redis / Task Queue (Optional - in-process BackgroundTasks used by default) ---
    REDIS_URL: Optional[str] = None

    # --- GIS ----------------------------------------------------------------
    WORKING_CRS: str = "EPSG:4326"

    # --- Auth (JWT) ---------------------------------------------------------
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def resolve_jwt_secret(cls, v: str) -> str:
        """Allow JWT_SECRET_KEY or JWT_SECRET as alternative environment variables for SECRET_KEY."""
        return os.environ.get("JWT_SECRET_KEY") or os.environ.get("JWT_SECRET") or v

    # --- Object storage (MinIO / S3) ----------------------------------------
    OBJECT_STORE_ENDPOINT: str = ""
    OBJECT_STORE_BUCKET: str = "cadastral-evidence"

    # --- Misc ---------------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=[str(_ENV_FILE), ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
