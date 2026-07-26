import uuid

from app.services.image_service import MockImageGenerator
from tests.helpers import png_bytes


def valid_form():
    return {
        "data": {"product_name": "Wooden Bowl", "description": "Hand-painted bowl"},
        "files": {"product_image": ("bowl.png", b"small-image", "image/png")},
    }


def test_create_and_retrieve_job(client):
    response = client.post("/generate", **valid_form())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"

    job_response = client.get(f"/jobs/{body['id']}")
    assert job_response.status_code == 200
    assert job_response.json()["product_name"] == "Wooden Bowl"
    assert job_response.json()["result_url"] is None


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
    assert job.json()["error_message"] is None
    assert job.json()["result_url"] == f"/jobs/{job_id}/image"

    result = client.get(job.json()["result_url"])
    assert result.status_code == 200
    assert result.headers["content-type"] == "image/png"
    assert result.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_image_endpoint_rejects_unavailable_result(client):
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
    assert job.json()["error_message"] == "mock generation failed"
