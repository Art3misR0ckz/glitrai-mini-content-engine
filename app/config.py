from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    """Use psycopg explicitly for common provider PostgreSQL URL formats."""
    url = value.strip()
    if url.startswith("postgres://"):
        return f"postgresql+psycopg://{url.removeprefix('postgres://')}"
    if url.startswith("postgresql://"):
        return f"postgresql+psycopg://{url.removeprefix('postgresql://')}"
    return url


class Settings(BaseSettings):
    app_name: str = "Mini Content Engine"
    database_url: str = "sqlite+pysqlite:///./glitrai.db"
    max_upload_mb: int = Field(default=5, ge=1)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    environment: str = "development"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_url(cls, value: object) -> object:
        return normalize_database_url(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_postgres_in_production(self) -> "Settings":
        if (
            self.environment.lower() == "production"
            and not self.database_url.startswith("postgresql+psycopg://")
        ):
            raise ValueError("Production requires a PostgreSQL DATABASE_URL")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
