import uuid


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
