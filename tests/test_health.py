def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "llm": {
            "provider": "openrouter",
            "configured": False,
            "model": "openrouter/free",
        },
        "image_provider": "mock",
    }
