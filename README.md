# GlitrAI Mini Content Engine

Content-generation service for the GlitrAI SDE Intern assignment. It accepts
product details and an image, creates a photography prompt, produces a polished
mock preview, and persists the complete asynchronous job lifecycle.

## Stack

- Python 3.12 and FastAPI
- SQLAlchemy 2
- PostgreSQL via psycopg
- Pydantic Settings
- Google Gen AI SDK with a deterministic offline fallback
- Pillow mock image generation
- Pytest

## Local setup

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and update `DATABASE_URL`.
4. Create the configured PostgreSQL database.
5. Start the API with `uvicorn app.main:app --reload`.
6. Open `http://127.0.0.1:8000` for the dashboard.

The frontend and API are served by the same FastAPI application, so no Node.js
installation or separate frontend process is required. API documentation
remains available at `http://127.0.0.1:8000/docs`.

Tables are created during application startup for this assignment foundation.
A production service should use migrations such as Alembic.

## API

- `GET /health` checks application and database availability.
- `POST /generate` accepts `product_name`, `description`, and `product_image`
  as multipart form data and returns a pending job with HTTP 202.
- `GET /jobs` returns up to 100 recent jobs, newest first.
- `GET /jobs/{id}` returns a job and its result URL when completed.
- `GET /jobs/{id}/image` streams the completed PNG from the database.

Accepted image formats are PNG, JPEG, and WebP. Uploads are limited to 5 MB by
default.

## Frontend

The responsive dashboard provides:

- A product name, description, and reference-image submission form.
- Local image preview and client-side type and size validation.
- Clear upload, success, and error states.
- Recent job cards refreshed every three seconds.
- Status badges for pending, processing, completed, and failed jobs.
- Generated prompt inspection and inline or full-size result viewing.

### Screenshot

> Add a screenshot of the deployed dashboard here before submission.

<!-- Example: ![Mini Content Engine dashboard](docs/dashboard.png) -->

## Tests

Run `pytest`. Tests use an isolated in-memory SQLite database, while the
application itself is configured for PostgreSQL.

## Generation workflow

`POST /generate` persists a pending job and schedules processing with FastAPI
`BackgroundTasks`. Processing moves the job to `processing`, generates a prompt
with Gemini (or the deterministic fallback), renders a 1024×1024 PNG, and marks
the job `completed`. Errors are stored and mark the job `failed`.

`BackgroundTasks` keeps this assignment compact. A production deployment should
use a durable queue and worker so jobs survive application restarts.
