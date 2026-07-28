import uuid

from app.database import SessionLocal
from app.models import Job, JobStatus
from app.services.image_service import ImageGenerator, get_image_generator
from app.services.prompt_service import PromptService


def process_job(
    job_id: uuid.UUID,
    prompt_service: PromptService | None = None,
    image_generator: ImageGenerator | None = None,
) -> None:
    prompt_service = prompt_service or PromptService()
    image_generator = image_generator or get_image_generator()

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        try:
            job.status = JobStatus.processing
            job.error_message = None
            db.commit()

            prompt_result = prompt_service.generate(
                job.product_name, job.description, job_id=job.id
            )
            job.generated_prompt = prompt_result.prompt
            job.prompt_provider = prompt_result.provider
            job.prompt_model = prompt_result.model
            job.prompt_used_fallback = prompt_result.used_fallback
            job.prompt_error_type = prompt_result.error_type
            db.commit()

            result = image_generator.generate(
                prompt_result.prompt, job.input_image, job.product_name
            )

            job.result_image = result
            job.result_image_mime = "image/png"
            job.status = JobStatus.completed
            job.error_message = None
            db.commit()
        except Exception as exc:
            db.rollback()
            failed_job = db.get(Job, job_id)
            if failed_job is not None:
                failed_job.status = JobStatus.failed
                failed_job.result_image = None
                failed_job.result_image_mime = None
                failed_job.error_message = _safe_failure_message(exc)
                db.commit()


def _safe_failure_message(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return "Image generation failed because the reference image was invalid."
    return "Generation failed. Please try again."
