import uuid
from io import BytesIO

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Job, JobStatus
from app.schemas import JobCreated, JobResponse
from app.services.job_service import process_job
from app.services.image_service import validate_uploaded_image

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
        prompt_provider=job.prompt_provider,
        prompt_model=job.prompt_model,
        prompt_used_fallback=job.prompt_used_fallback,
        prompt_error_type=job.prompt_error_type,
        result_url=result_url,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post(
    "/generate", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED
)
async def generate(
    background_tasks: BackgroundTasks,
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
    try:
        detected_mime = validate_uploaded_image(
            image_bytes, product_image.content_type
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = Job(
        product_name=name,
        description=details,
        input_image=image_bytes,
        input_image_mime=detected_mime,
        status=JobStatus.pending,
    )
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Unable to create the generation job"
        ) from exc
    response = JobCreated(id=job.id, status=job.status)
    background_tasks.add_task(process_job, job.id)
    return response


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


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_completed_job(
    job_id: uuid.UUID, db: Session = Depends(get_db)
) -> Response:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.completed:
        raise HTTPException(
            status_code=409, detail="Only completed jobs can be deleted"
        )
    try:
        db.delete(job)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Unable to delete the completed job"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jobs/{job_id}/image", response_class=StreamingResponse)
def get_job_image(
    job_id: uuid.UUID, db: Session = Depends(get_db)
) -> StreamingResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if (
        job.status != JobStatus.completed
        or job.result_image is None
        or job.result_image_mime is None
    ):
        raise HTTPException(status_code=409, detail="Job image is not available")
    return StreamingResponse(
        BytesIO(job.result_image),
        media_type=job.result_image_mime,
        headers={"Content-Disposition": f'inline; filename="{job.id}.png"'},
    )
