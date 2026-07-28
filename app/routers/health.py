from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas import HealthResponse, LLMHealth

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()
    llm = LLMHealth(
        provider="openrouter",
        configured=settings.openrouter_configured,
        model=settings.openrouter_model,
    )
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            database="unavailable",
            llm=llm,
            image_provider=settings.image_provider,
        )
    return HealthResponse(
        status="ok",
        database="ok",
        llm=llm,
        image_provider=settings.image_provider,
    )
