import json
import logging
import uuid
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.config import Settings
from app.services.image_service import MockImageGenerator
from app.services.prompt_service import PromptService
from tests.helpers import png_bytes


def test_fallback_prompt_without_api_key():
    service = PromptService(
        settings=Settings(
            database_url="sqlite+pysqlite:///:memory:",
            gemini_api_key="",
        )
    )

    prompt = service.generate("Florentine Wooden Bowl", "Hand-painted mango wood.")

    assert "Florentine Wooden Bowl" in prompt
    assert "Hand-painted mango wood." in prompt
    assert "shape, material, colours, patterns" in prompt


def test_gemini_response_is_used():
    client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **_: SimpleNamespace(
                text="A detailed commercial photography prompt."
            )
        )
    )
    service = PromptService(
        settings=Settings(
            database_url="sqlite+pysqlite:///:memory:",
            gemini_api_key="test-key",
        ),
        client=client,
    )

    assert service.generate("Bowl", "Wooden") == (
        "A detailed commercial photography prompt."
    )


def test_gemini_failure_uses_fallback():
    def fail(**_):
        raise ConnectionError("provider unavailable")

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=fail)
    )
    service = PromptService(
        settings=Settings(
            database_url="sqlite+pysqlite:///:memory:",
            gemini_api_key="test-key",
        ),
        client=client,
    )

    prompt = service.generate("Reliable Bowl", "Mango wood")

    assert "Reliable Bowl" in prompt
    assert "Mango wood" in prompt


def test_mock_generator_returns_1024_png():
    generated = MockImageGenerator().generate(
        "Product prompt", png_bytes((640, 360)), "Wooden Bowl"
    )

    assert generated.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(generated)) as image:
        assert image.format == "PNG"
        assert image.size == (1024, 1024)


def test_prompt_logging_contains_only_safe_structured_fields(caplog):
    job_id = uuid.uuid4()
    secret = "secret-api-key-that-must-not-be-logged"
    product = "Private Product Name"
    service = PromptService(
        settings=Settings(
            database_url="sqlite+pysqlite:///:memory:",
            gemini_api_key=secret,
        ),
        client=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **_: (_ for _ in ()).throw(
                    TimeoutError("provider timed out")
                )
            )
        ),
    )

    with caplog.at_level(logging.INFO, logger="app.services.prompt_service"):
        service.generate(product, "Private description", job_id=job_id)

    events = [json.loads(record.message) for record in caplog.records]
    assert events == [
        {"provider": "gemini", "category": "failure", "job_id": str(job_id)},
        {"provider": "fallback", "category": "success", "job_id": str(job_id)},
    ]
    assert secret not in caplog.text
    assert product not in caplog.text
