from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mini Content Engine"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/glitrai"
    max_upload_mb: int = Field(default=5, ge=1)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
