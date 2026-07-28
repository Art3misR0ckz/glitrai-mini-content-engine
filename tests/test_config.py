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


def test_openrouter_key_is_optional_and_secret_repr_is_masked():
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url="sqlite+pysqlite:///:memory:",
        openrouter_api_key="  private-test-value  ",
    )

    assert settings.openrouter_configured is True
    assert settings.openrouter_api_key.get_secret_value() == "private-test-value"
    assert "private-test-value" not in repr(settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("openrouter_timeout_seconds", 0),
        ("openrouter_timeout_seconds", -1),
        ("openrouter_max_retries", -1),
        ("openrouter_max_retries", 6),
    ],
)
def test_openrouter_limits_are_validated(field, value):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="development",
            database_url="sqlite+pysqlite:///:memory:",
            **{field: value},
        )


def test_render_url_is_used_only_when_site_url_is_missing():
    render_only = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///:memory:",
        openrouter_site_url="",
        render_external_url=" https://render.example ",
    )
    explicit = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///:memory:",
        openrouter_site_url=" https://app.example ",
        render_external_url="https://render.example",
    )

    assert render_only.openrouter_referer == "https://render.example"
    assert explicit.openrouter_referer == "https://app.example"
