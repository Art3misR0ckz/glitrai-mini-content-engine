from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import Base, engine
from app.routers import health, jobs
from app.schema_migrations import ensure_job_provider_columns


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    ensure_job_provider_columns(engine)
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
base_dir = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=base_dir / "static"), name="static")
templates = Jinja2Templates(directory=base_dir / "templates")
app.include_router(health.router)
app.include_router(jobs.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": get_settings().app_name,
            "max_upload_mb": get_settings().max_upload_mb,
        },
    )
