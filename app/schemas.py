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
    result_url: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    database: str
