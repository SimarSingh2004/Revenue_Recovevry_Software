"""Runtime configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Minimal settings required to run the application."""

    app_name: str = "Revenue Recovery Strategy Optimizer"
    app_environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide application settings."""

    return Settings()
