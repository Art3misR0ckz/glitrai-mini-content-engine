import json
import logging
import uuid
from io import BytesIO

import httpx
from PIL import Image

from app.config import Settings
from app.services.image_service import MockImageGenerator
from app.services.prompt_service import PromptService
from tests.helpers import png_bytes

VALID_PROMPT = (
    "Premium lifestyle photograph of the reference product, preserving its exact "
    "shape, proportions, material, colours, pattern, texture, and visible branding. "
    "Place it on a refined natural-stone surface beside soft linen in warm window "
    "light. Use an eye-level three-quarter camera angle, realistic contact shadows, "
    "a quiet neutral background, shallow depth of field, and elegant editorial mood. "
    "One product only, with no distortion, duplicate objects, text, or watermark."
)


def service_settings(**overrides):
    values = {
        "_env_file": None,
        "database_url": "sqlite+pysqlite:///:memory:",
        "environment": "development",
        "openrouter_api_key": "test-secret-key",
        "openrouter_model": "openrouter/free",
        "openrouter_max_retries": 2,
    }
    values.update(overrides)
    return Settings(**values)


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def success_response(request, *, model="provider/actual-model", content=VALID_PROMPT):
    return httpx.Response(
        200,
        request=request,
        json={
            "model": model,
            "choices": [{"message": {"content": content}}],
        },
    )


def test_missing_api_key_uses_fallback():
    service = PromptService(
        settings=service_settings(openrouter_api_key="")
    )

    result = service.generate(
        "Florentine Wooden Bowl", "Hand-painted mango wood."
    )

    assert result.provider == "fallback"
    assert result.model == "deterministic-fallback"
    assert result.used_fallback is True
    assert result.error_type == "MissingAPIKey"
    assert "Florentine Wooden Bowl" in result.prompt
    assert "Hand-painted mango wood." in result.prompt


def test_success_returns_openrouter_and_actual_model():
    client = mock_client(lambda request: success_response(request))
    service = PromptService(settings=service_settings(), client=client)

    result = service.generate("Bowl", "Wooden")

    assert result.prompt == VALID_PROMPT
    assert result.provider == "openrouter"
    assert result.model == "provider/actual-model"
    assert result.used_fallback is False
    assert result.error_type is None


def test_outgoing_headers_and_body_are_correct():
    captured = {}

    def handler(request):
        captured["authorization"] = request.headers["Authorization"]
        captured["referer"] = request.headers["HTTP-Referer"]
        captured["title"] = request.headers["X-OpenRouter-Title"]
        captured["body"] = json.loads(request.content)
        return success_response(request)

    settings = service_settings(
        openrouter_site_url="https://example.test/app",
        openrouter_app_name="GlitrAI Mini Content Engine",
    )
    result = PromptService(
        settings=settings, client=mock_client(handler)
    ).generate("Wooden Bowl", "Hand-painted mango wood")

    assert result.provider == "openrouter"
    assert captured["authorization"] == "Bearer test-secret-key"
    assert captured["referer"] == "https://example.test/app"
    assert captured["title"] == "GlitrAI Mini Content Engine"
    assert captured["body"]["model"] == "openrouter/free"
    assert captured["body"]["temperature"] == 0.4
    assert captured["body"]["max_tokens"] == 260
    assert "Product name: Wooden Bowl" in captured["body"]["messages"][1]["content"]


def test_render_external_url_is_referer_fallback():
    def handler(request):
        assert request.headers["HTTP-Referer"] == "https://deployed.example"
        return success_response(request)

    service = PromptService(
        settings=service_settings(
            openrouter_site_url="",
            render_external_url="https://deployed.example",
        ),
        client=mock_client(handler),
    )

    assert service.generate("Bowl", "Wood").provider == "openrouter"


def test_empty_or_short_output_uses_fallback():
    client = mock_client(lambda request: success_response(request, content="Too short"))

    result = PromptService(
        settings=service_settings(), client=client
    ).generate("Reliable Bowl", "Mango wood")

    assert result.provider == "fallback"
    assert result.error_type == "ValueError"


def test_malformed_json_uses_fallback():
    def handler(request):
        return httpx.Response(
            200,
            request=request,
            content=b"{not-json",
            headers={"content-type": "application/json"},
        )

    result = PromptService(
        settings=service_settings(), client=mock_client(handler)
    ).generate("Bowl", "Wood")

    assert result.provider == "fallback"
    assert result.error_type == "JSONDecodeError"


def test_missing_choices_uses_fallback():
    client = mock_client(
        lambda request: httpx.Response(200, request=request, json={"choices": []})
    )

    result = PromptService(
        settings=service_settings(), client=client
    ).generate("Bowl", "Wood")

    assert result.provider == "fallback"
    assert result.error_type == "ValueError"


def test_list_shaped_content_is_handled():
    content = [
        {"type": "text", "text": VALID_PROMPT[:210]},
        {"type": "text", "text": VALID_PROMPT[210:]},
    ]
    client = mock_client(
        lambda request: success_response(request, content=content)
    )

    result = PromptService(
        settings=service_settings(), client=client
    ).generate("Bowl", "Wood")

    assert result.provider == "openrouter"
    assert len(result.prompt) >= 60


def test_401_does_not_retry():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, request=request)

    result = PromptService(
        settings=service_settings(), client=mock_client(handler), sleep=lambda _: None
    ).generate("Bowl", "Wood")

    assert attempts == 1
    assert result.error_type == "AuthenticationError"
    assert result.provider == "fallback"


def test_429_retries_then_succeeds():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, request=request)
        return success_response(request)

    result = PromptService(
        settings=service_settings(), client=mock_client(handler), sleep=lambda _: None
    ).generate("Bowl", "Wood")

    assert attempts == 2
    assert result.provider == "openrouter"


def test_timeout_retries_then_uses_fallback():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    result = PromptService(
        settings=service_settings(), client=mock_client(handler), sleep=lambda _: None
    ).generate("Bowl", "Wood")

    assert attempts == 3
    assert result.provider == "fallback"
    assert result.error_type == "TimeoutError"


def test_500_retries_then_uses_fallback():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(500, request=request)

    result = PromptService(
        settings=service_settings(), client=mock_client(handler), sleep=lambda _: None
    ).generate("Bowl", "Wood")

    assert attempts == 3
    assert result.error_type == "ProviderServerError"


def test_network_error_retries_then_uses_fallback():
    def handler(request):
        raise httpx.ConnectError("unreachable", request=request)

    result = PromptService(
        settings=service_settings(), client=mock_client(handler), sleep=lambda _: None
    ).generate("Bowl", "Wood")

    assert result.provider == "fallback"
    assert result.error_type == "ConnectionError"


def test_structured_logs_are_safe_for_success(caplog):
    job_id = uuid.uuid4()
    secret = "test-secret-key"
    client = mock_client(lambda request: success_response(request))
    service = PromptService(settings=service_settings(), client=client)

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        service.generate("Private product", "Private description", job_id=job_id)

    event = json.loads(caplog.records[-1].message)
    assert event == {
        "event": "prompt_generation",
        "provider": "openrouter",
        "status": "success",
        "job_id": str(job_id),
        "model": "provider/actual-model",
    }
    assert secret not in caplog.text
    assert "Private product" not in caplog.text
    assert VALID_PROMPT not in caplog.text


def test_structured_failure_and_fallback_logs_are_safe(caplog):
    job_id = uuid.uuid4()
    client = mock_client(
        lambda request: httpx.Response(401, request=request, text="secret response")
    )
    service = PromptService(settings=service_settings(), client=client)

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        service.generate("Private product", "Private description", job_id=job_id)

    events = [json.loads(record.message) for record in caplog.records]
    assert events == [
        {
            "event": "prompt_generation",
            "provider": "openrouter",
            "status": "failure",
            "job_id": str(job_id),
            "error_type": "AuthenticationError",
        },
        {
            "event": "prompt_generation",
            "provider": "fallback",
            "status": "success",
            "job_id": str(job_id),
            "model": "deterministic-fallback",
        },
    ]
    assert "test-secret-key" not in caplog.text
    assert "secret response" not in caplog.text


def test_mock_generator_returns_labeled_1024_png():
    generated = MockImageGenerator().generate(
        "Product prompt", png_bytes((640, 360)), "Wooden Bowl"
    )

    assert generated.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(generated)) as image:
        assert image.format == "PNG"
        assert image.size == (1024, 1024)
