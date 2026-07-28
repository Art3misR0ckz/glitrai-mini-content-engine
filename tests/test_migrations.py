import uuid

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.schema_migrations import (
    PROVIDER_COLUMN_DEFINITIONS,
    ensure_job_provider_columns,
)


def memory_engine():
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_fresh_schema_contains_provider_metadata():
    engine = memory_engine()
    Base.metadata.create_all(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}

    assert set(PROVIDER_COLUMN_DEFINITIONS).issubset(columns)


def test_existing_schema_gains_columns_and_preserves_rows():
    engine = memory_engine()
    job_id = str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE jobs (
                    id VARCHAR(36) PRIMARY KEY,
                    product_name TEXT NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO jobs (id, product_name) "
                "VALUES (:id, :product_name)"
            ),
            {"id": job_id, "product_name": "Existing product"},
        )

    ensure_job_provider_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, product_name FROM jobs WHERE id = :id"),
            {"id": job_id},
        ).one()
    assert set(PROVIDER_COLUMN_DEFINITIONS).issubset(columns)
    assert row == (job_id, "Existing product")


def test_schema_migration_is_idempotent():
    engine = memory_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE jobs "
                "(id VARCHAR(36) PRIMARY KEY, product_name TEXT NOT NULL)"
            )
        )

    ensure_job_provider_columns(engine)
    ensure_job_provider_columns(engine)

    columns = [column["name"] for column in inspect(engine).get_columns("jobs")]
    assert len(columns) == len(set(columns))
