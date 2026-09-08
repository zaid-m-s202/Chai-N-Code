"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration.

    Every value can be overridden via an environment variable of the same
    (upper-case) name, or via a `.env` file placed next to ``manage.py``.
    """

    # --- Database -----------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg://cadastral:cadastral_dev_only@localhost:5432/cadastral"

    # --- Redis / task queue -------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- GIS ----------------------------------------------------------------
    WORKING_CRS: str = "EPSG:4326"

    # --- Auth (MVP JWT) -----------------------------------------------------
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # --- Object storage (MinIO / S3) ----------------------------------------
    OBJECT_STORE_ENDPOINT: str = ""
    OBJECT_STORE_BUCKET: str = "cadastral-evidence"

    # --- Misc ---------------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
