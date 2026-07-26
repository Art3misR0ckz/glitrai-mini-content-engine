import json
import logging
import uuid

from google import genai
from google.genai import types

from app.config import Settings, get_settings

# Uvicorn configures this logger for deployed application output, including
# Render's captured stdout/stderr stream.
logger = logging.getLogger("uvicorn.error")


class PromptService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def generate(
        self,
        product_name: str,
        description: str,
        job_id: uuid.UUID | str | None = None,
    ) -> str:
        if not self.settings.gemini_api_key:
            self._log_provider("fallback", job_id, "success")
            return self.fallback_prompt(product_name, description)

        try:
            client = self._client or genai.Client(
                api_key=self.settings.gemini_api_key,
                http_options=types.HttpOptions(timeout=15_000),
            )
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=self._request(product_name, description),
            )
            prompt = (response.text or "").strip()
            if not prompt:
                raise ValueError("Gemini returned an empty prompt")
            self._log_provider("gemini", job_id, "success")
            return prompt
        except Exception as exc:
            # Prompt generation must remain available when the external provider
            # is unavailable. Provider details are deliberately not exposed.
            self._log_provider(
                "gemini",
                job_id,
                "failure",
                error_type=type(exc).__name__,
                error_description="Gemini request failed; using fallback.",
            )
            self._log_provider("fallback", job_id, "success")
            return self.fallback_prompt(product_name, description)

    @staticmethod
    def _log_provider(
        provider: str,
        job_id: uuid.UUID | str | None,
        status: str,
        *,
        error_type: str | None = None,
        error_description: str | None = None,
    ) -> None:
        event = {
            "event": "prompt_generation",
            "provider": provider,
            "status": status,
            "job_id": str(job_id) if job_id is not None else None,
        }
        if error_type is not None:
            event["error_type"] = error_type
        if error_description is not None:
            event["error_description"] = error_description
        logger.info(json.dumps(event, separators=(",", ":")))

    @staticmethod
    def _request(product_name: str, description: str) -> str:
        return f"""You are an expert commercial product-photography prompt writer.
Create one detailed, realistic lifestyle image prompt for this product.

Product name: {product_name}
Description: {description}

Preserve the product's exact shape, material, colours, patterns, proportions,
and visible branding from the reference image. Describe a premium setting,
composition, lighting, camera angle, background, mood, and realistic shadows.
Do not invent unsupported product features. Request one product only, with no
distortion, duplicated objects, added text, or watermark. Return only the final
prompt in 80-120 words."""

    @staticmethod
    def fallback_prompt(product_name: str, description: str) -> str:
        return (
            f"Premium commercial lifestyle photograph of {product_name}. "
            "Use the supplied reference image and preserve the product's exact "
            "shape, material, colours, patterns, visible details, and proportions. "
            f"{description.strip()} Place the product naturally in a refined, "
            "realistic setting with soft directional window light, gentle shadows, "
            "balanced composition, true-to-life textures, and shallow depth of "
            "field. Keep the product centred, fully visible, and sharply focused. "
            "High-end editorial product photography, natural colour grading, one "
            "product only, no altered branding, added text, watermark, distortion, "
            "cropping, or duplicated objects."
        )
