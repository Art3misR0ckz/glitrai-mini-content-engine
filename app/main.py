from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.database import Base, engine
from app.routers import health, jobs


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.include_router(health.router)
app.include_router(jobs.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(
        "<h1>Mini Content Engine</h1>"
        "<p>The frontend will be implemented in the next stage.</p>"
        '<p><a href="/docs">Open API documentation</a></p>'
    )
