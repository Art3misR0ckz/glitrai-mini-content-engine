from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    max_upload_mb: int = Field(default=5, ge=1, le=25)
    environment: str = "development"
    image_provider: Literal["mock"] = "mock"

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "openrouter/free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_name: str = "GlitrAI Mini Content Engine"
    openrouter_site_url: str = ""
    openrouter_timeout_seconds: float = Field(default=25, gt=0, le=120)
    openrouter_max_retries: int = Field(default=2, ge=0, le=5)
    render_external_url: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_url(cls, value: object) -> object:
        return normalize_database_url(value) if isinstance(value, str) else value

    @field_validator(
        "environment",
        "openrouter_model",
        "openrouter_base_url",
        "openrouter_app_name",
        "openrouter_site_url",
        "render_external_url",
        mode="before",
    )
    @classmethod
    def strip_text_settings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("openrouter_api_key", mode="before")
    @classmethod
    def strip_secret(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            return SecretStr(value.get_secret_value().strip())
        return value.strip() if isinstance(value, str) else value

    @field_validator("openrouter_base_url")
    @classmethod
    def normalize_openrouter_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("OPENROUTER_BASE_URL must be an HTTP(S) URL")
        return value.rstrip("/")

    @model_validator(mode="after")
    def require_postgres_in_production(self) -> "Settings":
        if (
            self.environment.lower() == "production"
            and not self.database_url.startswith("postgresql+psycopg://")
        ):
            raise ValueError("Production requires a PostgreSQL DATABASE_URL")
        return self

    @property
    def openrouter_referer(self) -> str:
        return self.openrouter_site_url or self.render_external_url

    @property
    def openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value())

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
