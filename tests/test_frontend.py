def test_homepage_returns_frontend_html(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Mini Content Engine" in response.text
    assert 'id="generation-form"' in response.text
    assert 'id="jobs-list"' in response.text


def test_static_stylesheet_is_accessible(client):
    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert ".status-completed" in response.text


def test_static_javascript_is_accessible(client):
    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "setInterval(loadJobs, 3000)" in response.text


def test_docs_remain_accessible(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
