import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Job, JobStatus
from app.schemas import JobCreated, JobResponse

router = APIRouter(tags=["jobs"])
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def to_response(job: Job) -> JobResponse:
    result_url = f"/jobs/{job.id}/image" if job.status == JobStatus.completed else None
    return JobResponse(
        id=job.id,
        product_name=job.product_name,
        description=job.description,
        status=job.status,
        generated_prompt=job.generated_prompt,
        result_url=result_url,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post(
    "/generate", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED
)
async def generate(
    product_name: str = Form(...),
    description: str = Form(...),
    product_image: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> JobCreated:
    name = product_name.strip()
    details = description.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Product name is required")
    if not details:
        raise HTTPException(status_code=422, detail="Description is required")
    if product_image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415, detail="Image must be PNG, JPEG, or WebP"
        )

    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    image_bytes = await product_image.read(max_bytes + 1)
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image must not exceed {get_settings().max_upload_mb} MB",
        )
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Image file is empty")

    job = Job(
        product_name=name,
        description=details,
        input_image=image_bytes,
        input_image_mime=product_image.content_type,
        status=JobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobCreated(id=job.id, status=job.status)


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db)) -> list[JobResponse]:
    jobs = db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all()
    return [to_response(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> JobResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return to_response(job)
