import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import JobStatus


class JobCreated(BaseModel):
    id: uuid.UUID
    status: JobStatus


class JobResponse(BaseModel):
    id: uuid.UUID
    product_name: str
    description: str
    status: JobStatus
    generated_prompt: str | None
    prompt_provider: str | None = None
    prompt_model: str | None = None
    prompt_used_fallback: bool = False
    prompt_error_type: str | None = None
    result_url: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LLMHealth(BaseModel):
    provider: str
    configured: bool
    model: str


class HealthResponse(BaseModel):
    status: str
    database: str
    llm: LLMHealth
    image_provider: str
