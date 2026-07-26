import pytest
from pydantic import ValidationError

from app.config import Settings, normalize_database_url


@pytest.mark.parametrize(
    ("original", "normalized"),
    [
        (
            "postgres://user:pass@db.example.com:5432/app",
            "postgresql+psycopg://user:pass@db.example.com:5432/app",
        ),
        (
            "postgresql://user:pass@db.example.com/app",
            "postgresql+psycopg://user:pass@db.example.com/app",
        ),
        (
            "postgresql+psycopg://user:pass@db.example.com/app",
            "postgresql+psycopg://user:pass@db.example.com/app",
        ),
    ],
)
def test_postgres_url_normalization(original, normalized):
    assert normalize_database_url(original) == normalized


def test_production_accepts_and_normalizes_postgres():
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgres://user:pass@host/app",
    )

    assert settings.environment == "production"
    assert settings.database_url == "postgresql+psycopg://user:pass@host/app"


def test_production_rejects_sqlite():
    with pytest.raises(ValidationError, match="Production requires a PostgreSQL"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="sqlite+pysqlite:///./local.db",
        )


def test_development_supports_sqlite():
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url="sqlite+pysqlite:///:memory:",
    )

    assert settings.database_url.startswith("sqlite")
