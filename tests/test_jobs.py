import uuid
from io import BytesIO

from PIL import Image

from app.database import SessionLocal
from app.models import Job, JobStatus
from app.services.image_service import MockImageGenerator
from app.services.job_service import process_job
from app.services.prompt_service import PromptGenerationResult
from tests.helpers import png_bytes


def valid_form():
    return {
        "data": {"product_name": "Wooden Bowl", "description": "Hand-painted bowl"},
        "files": {"product_image": ("bowl.png", png_bytes(), "image/png")},
    }


def test_create_and_retrieve_job(client):
    response = client.post("/generate", **valid_form())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"

    job_response = client.get(f"/jobs/{body['id']}")
    assert job_response.status_code == 200
    assert job_response.json()["product_name"] == "Wooden Bowl"
    assert job_response.json()["status"] == "completed"


def test_jobs_are_newest_first(client):
    client.post("/generate", **valid_form())
    second = valid_form()
    second["data"]["product_name"] = "Second Product"
    client.post("/generate", **second)

    response = client.get("/jobs")

    assert response.status_code == 200
    assert response.json()[0]["product_name"] == "Second Product"


def test_unknown_job_returns_404(client):
    response = client.get(f"/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


def test_rejects_unsupported_file_type(client):
    form = valid_form()
    form["files"] = {"product_image": ("notes.txt", b"text", "text/plain")}

    response = client.post("/generate", **form)

    assert response.status_code == 415


def test_rejects_blank_product_name(client):
    form = valid_form()
    form["data"]["product_name"] = " "

    response = client.post("/generate", **form)

    assert response.status_code == 422


def test_completed_lifecycle_and_result_image(client):
    form = valid_form()
    form["files"] = {"product_image": ("bowl.png", png_bytes(), "image/png")}

    created = client.post("/generate", **form)

    assert created.status_code == 202
    assert created.json()["status"] == "pending"

    job_id = created.json()["id"]
    job = client.get(f"/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "completed"
    assert job.json()["generated_prompt"]
    assert job.json()["prompt_provider"] == "fallback"
    assert job.json()["prompt_model"] == "deterministic-fallback"
    assert job.json()["prompt_used_fallback"] is True
    assert job.json()["prompt_error_type"] == "MissingAPIKey"
    assert job.json()["error_message"] is None
    assert job.json()["result_url"] == f"/jobs/{job_id}/image"

    result = client.get(job.json()["result_url"])
    assert result.status_code == 200
    assert result.headers["content-type"] == "image/png"
    assert result.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_image_endpoint_rejects_unavailable_result(client, monkeypatch):
    monkeypatch.setattr("app.routers.jobs.process_job", lambda _job_id: None)
    response = client.post("/generate", **valid_form())
    job_id = response.json()["id"]

    result = client.get(f"/jobs/{job_id}/image")

    assert result.status_code == 409


def test_generation_failure_is_recorded(client, monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("mock generation failed")

    monkeypatch.setattr(MockImageGenerator, "generate", fail)
    form = valid_form()
    form["files"] = {"product_image": ("bowl.png", png_bytes(), "image/png")}

    created = client.post("/generate", **form)
    job = client.get(f"/jobs/{created.json()['id']}")

    assert job.json()["status"] == "failed"
    assert job.json()["result_url"] is None
    assert job.json()["error_message"] == "Generation failed. Please try again."


def test_rejects_corrupted_image(client):
    form = valid_form()
    form["files"] = {
        "product_image": ("broken.png", b"not-a-real-png", "image/png")
    }

    response = client.post("/generate", **form)

    assert response.status_code == 422
    assert "corrupted or unreadable" in response.json()["detail"]


def test_rejects_mismatched_image_type(client):
    form = valid_form()
    form["files"] = {
        "product_image": ("bowl.jpg", png_bytes(), "image/jpeg")
    }

    response = client.post("/generate", **form)

    assert response.status_code == 422
    assert "do not match" in response.json()["detail"]


def test_accepts_jpeg_and_webp(client):
    for image_format, mime, extension in [
        ("JPEG", "image/jpeg", "jpg"),
        ("WEBP", "image/webp", "webp"),
    ]:
        image = Image.new("RGB", (48, 48), (100, 120, 140))
        output = BytesIO()
        image.save(output, format=image_format)
        form = valid_form()
        form["files"] = {
            "product_image": (
                f"product.{extension}",
                output.getvalue(),
                mime,
            )
        }

        response = client.post("/generate", **form)

        assert response.status_code == 202


def test_rejects_upload_over_size_limit(client):
    form = valid_form()
    form["files"] = {
        "product_image": (
            "large.png",
            b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024),
            "image/png",
        )
    }

    response = client.post("/generate", **form)

    assert response.status_code == 413


def test_rejects_excessive_image_dimensions(client):
    image = Image.new("1", (5001, 5001), 1)
    output = BytesIO()
    image.save(output, format="PNG")
    form = valid_form()
    form["files"] = {
        "product_image": ("huge-dimensions.png", output.getvalue(), "image/png")
    }

    response = client.post("/generate", **form)

    assert response.status_code == 422
    assert "dimensions are too large" in response.json()["detail"]


def test_completed_job_can_be_deleted(client):
    created = client.post("/generate", **valid_form())
    job_id = created.json()["id"]

    deleted = client.delete(f"/jobs/{job_id}")

    assert deleted.status_code == 204
    assert client.get(f"/jobs/{job_id}").status_code == 404
    assert client.get(f"/jobs/{job_id}/image").status_code == 404


def test_unfinished_job_cannot_be_deleted(client, monkeypatch):
    monkeypatch.setattr("app.routers.jobs.process_job", lambda _job_id: None)
    created = client.post("/generate", **valid_form())

    deleted = client.delete(f"/jobs/{created.json()['id']}")

    assert deleted.status_code == 409
    assert deleted.json()["detail"] == "Only completed jobs can be deleted"


def test_openrouter_metadata_is_persisted_by_background_processor(client):
    with SessionLocal() as db:
        job = Job(
            product_name="Provider Test Bowl",
            description="Hand-painted mango wood.",
            input_image=png_bytes(),
            input_image_mime="image/png",
            status=JobStatus.pending,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    class SuccessfulPromptService:
        def generate(self, product_name, description, job_id=None):
            with SessionLocal() as checking_db:
                assert checking_db.get(Job, job_id).status == JobStatus.processing
            return PromptGenerationResult(
                prompt=(
                    "Premium commercial product photograph preserving exact shape, "
                    "material, colours, pattern, texture, branding, and proportions "
                    "in a refined lifestyle setting with natural light and shadows."
                ),
                provider="openrouter",
                model="provider/actual-free-model",
                used_fallback=False,
            )

    process_job(
        job_id,
        prompt_service=SuccessfulPromptService(),
        image_generator=MockImageGenerator(),
    )

    with SessionLocal() as db:
        completed = db.get(Job, job_id)
        assert completed.status == JobStatus.completed
        assert completed.prompt_provider == "openrouter"
        assert completed.prompt_model == "provider/actual-free-model"
        assert completed.prompt_used_fallback is False
        assert completed.prompt_error_type is None
        assert completed.result_image_mime == "image/png"
