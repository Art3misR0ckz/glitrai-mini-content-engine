# GlitrAI Mini Content Engine

A publicly deployable implementation of Assignment 1 for the GlitrAI SDE
Intern assignment. A user submits product information and a reference image;
the application creates a tracked database job, asks OpenRouter for a commercial
product-photography prompt, renders an assignment-approved mock preview, and
serves the completed result through a responsive dashboard.

**Hosted application:** [glitrai-mini-content-engine-r1gz.onrender.com](https://glitrai-mini-content-engine-r1gz.onrender.com/)

## Assignment requirements covered

- Product name, description, and validated reference-image upload
- PostgreSQL-backed pending, processing, completed, and failed jobs
- OpenRouter prompt generation with retry and deterministic fallback
- Assignment-approved mock image provider returning a 1024×1024 PNG
- Job status, provider metadata, prompt, result-image, and health APIs
- Server-rendered frontend with preview, polling, results, and safe deletion
- Local SQLite development and production PostgreSQL enforcement
- Render Blueprint and Python version pin
- Automated API, provider, migration, security, and frontend tests

## Architecture

```mermaid
flowchart LR
    U["Browser"] -->|"multipart POST /generate"| API["FastAPI"]
    API -->|"pending job"| DB[("PostgreSQL")]
    API --> BG["BackgroundTasks worker"]
    BG -->|"product metadata"| OR["OpenRouter"]
    OR -->|"prompt or provider failure"| BG
    BG -->|"provider unavailable"| FB["Deterministic fallback"]
    FB --> BG
    BG -->|"prompt + reference"| MOCK["MockImageGenerator"]
    MOCK -->|"1024×1024 PNG"| DB
    U -->|"poll GET /jobs"| API
    API -->|"status, metadata, result URL"| U
```

The HTTP request and background processor use separate SQLAlchemy sessions.
The API returns HTTP 202 after the pending job is committed.

## Job lifecycle

```text
pending → processing → completed
                     ↘ failed
```

The worker commits `processing`, persists the prompt and provider metadata,
renders the preview, and commits `completed`. On an unrecoverable image or
database error it rolls back and stores a sanitized failure message.

## Technology choices

- Python 3.12, FastAPI, Uvicorn
- SQLAlchemy 2, PostgreSQL/psycopg, SQLite for local tests
- Synchronous `httpx` client for OpenRouter
- Pillow for content validation and mock rendering
- Jinja2, vanilla JavaScript, and CSS
- Pytest

## OpenRouter integration

`PromptService` sends a system instruction and structured product details to:

```text
POST https://openrouter.ai/api/v1/chat/completions
```

The request preserves product identity and asks for one 80–140 word commercial
lifestyle-photography prompt. It sends `X-OpenRouter-Title` and an optional
`HTTP-Referer`; on Render, `RENDER_EXTERNAL_URL` supplies the referer when
`OPENROUTER_SITE_URL` is empty.

Timeouts, network failures, HTTP 429, and HTTP 500/502/503/504 are retried with
small exponential backoff. Authentication, permission, and validation failures
are not retried. Missing keys, exhausted retries, malformed responses, empty
content, and unavailable models use the deterministic fallback so jobs still
complete.

Safe JSON logs make the provider observable without exposing request data:

```json
{"event":"prompt_generation","provider":"openrouter","status":"success","job_id":"...","model":"..."}
```

No API keys, authorization headers, prompts, response bodies, images, or
database URLs are logged.

## Mock image provider

The image step is intentionally mocked, as Assignment 1 explicitly permits.
`MockImageGenerator` corrects EXIF orientation, creates a blurred background
from the reference, centres the reference without distortion, adds a shadow and
product label, and returns an in-memory PNG.

It does **not** claim to synthesize a new AI lifestyle scene. The UI labels it
“Mock Preview.” Assignment 2 can add `IMAGE_PROVIDER=comfyui` using ComfyUI
Img2Img plus an upscaler without changing the public job API.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/` | Dashboard |
| `POST` | `/generate` | Create a job from multipart product fields and image |
| `GET` | `/jobs` | Return the 100 newest jobs |
| `GET` | `/jobs/{job_id}` | Return status, prompt, provider metadata, and result URL |
| `GET` | `/jobs/{job_id}/image` | Stream the stored result image |
| `DELETE` | `/jobs/{job_id}` | Delete a completed job and stored image |
| `GET` | `/health` | Check database and report safe provider configuration |
| `GET` | `/docs` | OpenAPI documentation |

`POST /generate` accepts `product_name`, `description`, and `product_image`.
PNG, JPEG, and WebP are supported up to 5 MB. Pillow verifies actual file
content, MIME agreement, corruption, decompression bombs, and pixel dimensions.

Provider metadata returned by job endpoints:

```json
{
  "prompt_provider": "openrouter",
  "prompt_model": "openrouter/free",
  "prompt_used_fallback": false,
  "prompt_error_type": null
}
```

Existing consumers remain compatible because these fields are additive.

## Local setup

1. Install Python 3.12.
2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # PowerShell
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`.
5. Start the application:

   ```bash
   uvicorn app.main:app --reload
   ```

6. Open `http://127.0.0.1:8000`.

No Node.js process or separate frontend deployment is required.

## Environment variables

| Variable | Default / purpose |
| --- | --- |
| `DATABASE_URL` | `sqlite+pysqlite:///./glitrai.db` locally; PostgreSQL required in production |
| `MAX_UPLOAD_MB` | `5` |
| `ENVIRONMENT` | `development`; set `production` on Render |
| `IMAGE_PROVIDER` | `mock` |
| `OPENROUTER_API_KEY` | Optional locally; secret in Render |
| `OPENROUTER_MODEL` | `openrouter/free` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `OPENROUTER_APP_NAME` | `GlitrAI Mini Content Engine` |
| `OPENROUTER_SITE_URL` | Optional explicit referer |
| `OPENROUTER_TIMEOUT_SECONDS` | `25` |
| `OPENROUTER_MAX_RETRIES` | `2` |
| `RENDER_EXTERNAL_URL` | Provided automatically by Render |

The API key uses Pydantic `SecretStr`, is whitespace-normalized, and is optional
for local fallback mode.

## SQLite development and PostgreSQL production

Local configuration:

```env
ENVIRONMENT=development
DATABASE_URL=sqlite+pysqlite:///./glitrai.db
```

Production configuration:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql://user:password@host/database
```

`postgres://` and `postgresql://` URLs normalize to
`postgresql+psycopg://`. Production refuses SQLite. Connections use
`pool_pre_ping`, and `/health` executes `SELECT 1`.

Startup runs `create_all` for fresh databases and a small idempotent additive
schema migration for existing databases. It inspects `jobs` and adds only
missing provider-metadata columns; it never drops tables or existing rows.

## Render deployment

`render.yaml` defines one Python web service:

```text
Build: pip install -r requirements.txt
Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health: /health
```

Required Render variables:

```env
DATABASE_URL=<existing Neon PostgreSQL URL>
ENVIRONMENT=production
MAX_UPLOAD_MB=5
IMAGE_PROVIDER=mock
OPENROUTER_API_KEY=<set only in Render dashboard>
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_APP_NAME=GlitrAI Mini Content Engine
OPENROUTER_TIMEOUT_SECONDS=25
OPENROUTER_MAX_RETRIES=2
```

`OPENROUTER_SITE_URL` can be omitted because Render supplies
`RENDER_EXTERNAL_URL`. Never place secret values in `render.yaml`.

## Testing

```bash
python -m pytest -q
python -m compileall app tests
```

The suite uses in-memory SQLite and mocked OpenRouter transports. It covers
successful calls, headers, model capture, list content, retries, failures,
fallback, safe logs, lifecycle, provider persistence, migrations, formats,
corruption, MIME mismatch, size/dimension limits, static assets, and production
configuration.

## Security decisions

- Secrets are excluded by `.gitignore` and represented with `SecretStr`.
- Provider logs contain only event, provider, status, job ID, model, and safe
  error category.
- API errors never expose stack traces or raw provider responses.
- Uploaded bytes are never logged and are validated before persistence.
- User content is HTML-escaped before JavaScript inserts job cards.
- Result files are streamed from PostgreSQL; filesystem paths are not exposed.
- Database writes commit explicit transitions and roll back on errors.

## Tradeoffs and known limitations

- FastAPI `BackgroundTasks` is sufficient for this assignment but is not
  durable across restarts. At scale use Celery, RQ, Dramatiq, or a managed task
  service.
- Images are stored as PostgreSQL `BYTEA` for deployment simplicity. Object
  storage plus persisted URLs is preferable at scale.
- Free OpenRouter models can have variable availability, latency, and limits.
  The fallback prevents those outages from breaking the application.
- Startup schema upgrades are intentionally small and additive. A larger
  product should use versioned Alembic migrations.
- Authentication, rate limiting, moderation, retention, tracing, and
  idempotency keys are future production work.

## Submission

- **Public application:** https://glitrai-mini-content-engine-r1gz.onrender.com/
- **Public repository:** https://github.com/Art3misR0ckz/glitrai-mini-content-engine
- **Loom video:** `<add Loom URL>`
- **Google Drive folder:** `<add submission folder URL>`
- **Assignment 2 workflow/screenshots:** `<add ComfyUI deliverable links>`
