# GlitrAI Mini Content Engine

Initial backend foundation for the GlitrAI SDE Intern assignment. It accepts
product details and an image, persists a pending generation job in PostgreSQL,
and exposes endpoints for health and job status.

## Stack

- Python 3.12 and FastAPI
- SQLAlchemy 2
- PostgreSQL via psycopg
- Pydantic Settings
- Pytest

## Local setup

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and update `DATABASE_URL`.
4. Create the configured PostgreSQL database.
5. Start the API with `uvicorn app.main:app --reload`.
6. Open `http://127.0.0.1:8000/docs`.

Tables are created during application startup for this assignment foundation.
A production service should use migrations such as Alembic.

## API

- `GET /health` checks application and database availability.
- `POST /generate` accepts `product_name`, `description`, and `product_image`
  as multipart form data and returns a pending job with HTTP 202.
- `GET /jobs` returns up to 100 recent jobs, newest first.
- `GET /jobs/{id}` returns a job and its result URL when completed.

Accepted image formats are PNG, JPEG, and WebP. Uploads are limited to 5 MB by
default.

## Tests

Run `pytest`. Tests use an isolated in-memory SQLite database, while the
application itself is configured for PostgreSQL.

## Current scope

Prompt generation, image generation, background processing, the result-image
endpoint, and the full frontend are intentionally deferred to the next stage.
