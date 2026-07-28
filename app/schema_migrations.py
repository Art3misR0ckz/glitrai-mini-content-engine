from sqlalchemy import Engine, inspect, text


PROVIDER_COLUMN_DEFINITIONS = {
    "prompt_provider": "VARCHAR(32)",
    "prompt_model": "VARCHAR(255)",
    "prompt_used_fallback": "BOOLEAN NOT NULL DEFAULT FALSE",
    "prompt_error_type": "VARCHAR(100)",
}


def ensure_job_provider_columns(engine: Engine) -> None:
    """Add provider metadata columns without replacing the existing jobs table."""
    inspector = inspect(engine)
    if not inspector.has_table("jobs"):
        return

    existing = {column["name"] for column in inspector.get_columns("jobs")}
    missing = [
        (name, definition)
        for name, definition in PROVIDER_COLUMN_DEFINITIONS.items()
        if name not in existing
    ]
    if not missing:
        return

    with engine.begin() as connection:
        for name, definition in missing:
            connection.execute(
                text(f'ALTER TABLE jobs ADD COLUMN "{name}" {definition}')
            )
