# GlitrAI Mini Content Engine

A compact product-content workflow built for the GlitrAI SDE Intern assignment.
The service accepts product details and a reference image, creates a commercial
photography prompt, renders a mock preview, stores the asynchronous job in a
database, and exposes its status and result through a responsive dashboard.

## Technology

- Python 3.12, FastAPI, Jinja2, vanilla JavaScript, and CSS
- SQLAlchemy 2 with PostgreSQL/psycopg in production
- Google Gen AI SDK with a deterministic prompt fallback
- Pillow for image validation and mock preview generation
- Pytest

## Local setup

1. Install Python 3.12.
2. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

3. Activate it and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`.
5. For lightweight local development, set:

   ```env
   ENVIRONMENT=development
   DATABASE_URL=sqlite+pysqlite:///./glitrai.db
   ```

6. Start the service:

   ```bash
   uvicorn app.main:app --reload
   ```

7. Open `http://127.0.0.1:8000`. API documentation is available at `/docs`.

SQLite is supported only for local development and automated tests. Production
configuration rejects SQLite.

## PostgreSQL setup

Create a PostgreSQL database locally or use a managed provider, then set:

```env
DATABASE_URL=postgresql://user:password@host:5432/glitrai
```

Provider URLs beginning with either `postgres://` or `postgresql://` are
normalized automatically to SQLAlchemy's `postgresql+psycopg://` driver URL.
Connection liveness is checked with `pool_pre_ping`, tables are created
idempotently during application startup, and `/health` runs `SELECT 1` against
the configured database.

## Gemini setup

Create a Gemini API key and configure:

```env
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash-lite
```

When a key is configured, the prompt service calls Gemini with a bounded
request timeout. Empty responses, timeouts, and provider failures switch to a
deterministic commercial-photography prompt so generation remains available.
Keys and uploaded image bytes are never returned by the API or written to logs.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL in production |
| `GEMINI_API_KEY` | Optional Gemini API credential |
| `GEMINI_MODEL` | Gemini model; defaults to `gemini-2.5-flash-lite` |
| `MAX_UPLOAD_MB` | Upload limit; defaults to `5` |
| `ENVIRONMENT` | Use `production` on Render and `development` locally |

## Render deployment

The included `render.yaml` defines one Python web service with:

```text
Build: pip install -r requirements.txt
Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health check: /health
```

1. Push this repository to GitHub.
2. Create a Render Blueprint from the repository.
3. Set `DATABASE_URL` to a managed PostgreSQL connection string.
4. Set `GEMINI_API_KEY` if Gemini prompting is desired.
5. Deploy and verify `/`, `/health`, `/docs`, and a complete generation.

Static files and templates are resolved relative to the application package, so
they work independently of Render's process working directory.

## API decisions

- `POST /generate` uses multipart form data because product metadata and the
  reference image arrive together. It returns HTTP 202 with a UUID immediately.
- Uploaded files are capped at 5 MB and must declare PNG, JPEG, or WebP.
  Pillow additionally verifies the actual image structure, format, dimensions,
  and corruption state before persistence.
- `GET /jobs` returns the 100 newest jobs for the dashboard.
- `GET /jobs/{id}` exposes status, prompt, safe error details, and a result URL
  only after completion.
- `GET /jobs/{id}/image` streams stored result bytes.
- `GET /health` checks the real database connection.

## Job lifecycle

```text
pending → processing → completed
                     ↘ failed
```

The initial insert is transaction-safe. Background processing commits explicit
state transitions and rolls back before recording a sanitized failure.

## Frontend

The server-rendered dashboard provides local image preview, client-side
validation, readable submission states, three-second status polling, generated
prompt inspection, status badges, inline results, and full-image viewing. It
requires no Node.js build or separate deployment.

### Screenshot

> Add a screenshot of the deployed dashboard here before submission.

<!-- ![Mini Content Engine dashboard](docs/dashboard.png) -->

## Tests

Run:

```bash
pytest
```

Tests use an isolated in-memory SQLite database and mock external Gemini calls.
They cover the API, job lifecycle, result images, frontend assets, prompt
fallback, upload validation, URL normalization, and production configuration.

## Limitations and production tradeoffs

- The current `MockImageGenerator` creates a polished composition from the
  uploaded reference; it does not synthesize a new AI lifestyle scene. The
  provider abstraction is intended to be replaced by ComfyUI.
- FastAPI `BackgroundTasks` is compact but not durable. A production system
  should use a worker queue so jobs survive restarts and can be retried.
- Image bytes are stored in PostgreSQL to avoid ephemeral-disk loss. At scale,
  use object storage and persist URLs instead.
- Automatic table creation is sufficient for this assignment. Production
  schema evolution should use Alembic migrations.
- A production-facing service should add authentication, rate limiting,
  idempotency keys, moderation, observability, and retention policies.
