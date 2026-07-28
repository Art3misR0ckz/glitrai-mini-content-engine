import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, LargeBinary, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    input_image_mime: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_prompt: Mapped[str | None] = mapped_column(Text)
    prompt_provider: Mapped[str | None] = mapped_column(String(32))
    prompt_model: Mapped[str | None] = mapped_column(String(255))
    prompt_used_fallback: Mapped[bool] = mapped_column(default=False, nullable=False)
    prompt_error_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.pending, nullable=False
    )
    result_image: Mapped[bytes | None] = mapped_column(LargeBinary)
    result_image_mime: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
