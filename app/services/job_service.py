import uuid

from app.database import SessionLocal
from app.models import Job, JobStatus
from app.services.image_service import ImageGenerator, MockImageGenerator
from app.services.prompt_service import PromptService


def process_job(
    job_id: uuid.UUID,
    prompt_service: PromptService | None = None,
    image_generator: ImageGenerator | None = None,
) -> None:
    prompt_service = prompt_service or PromptService()
    image_generator = image_generator or MockImageGenerator()

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        try:
            job.status = JobStatus.processing
            job.error_message = None
            db.commit()

            prompt = prompt_service.generate(job.product_name, job.description)
            result = image_generator.generate(
                prompt, job.input_image, job.product_name
            )

            job.generated_prompt = prompt
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
                failed_job.error_message = str(exc)[:1000] or "Generation failed"
                db.commit()
