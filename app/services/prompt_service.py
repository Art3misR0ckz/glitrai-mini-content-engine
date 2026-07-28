import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("uvicorn.error")

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
MINIMUM_PROMPT_CHARACTERS = 60


@dataclass(frozen=True, slots=True)
class PromptGenerationResult:
    prompt: str
    provider: str
    model: str
    used_fallback: bool
    error_type: str | None = None


class PromptService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._sleep = sleep

    def generate(
        self,
        product_name: str,
        description: str,
        job_id: uuid.UUID | str | None = None,
    ) -> PromptGenerationResult:
        if not self.settings.openrouter_configured:
            result = self._fallback_result(
                product_name, description, "MissingAPIKey"
            )
            self._log_provider(result, job_id, "success")
            return result

        client = self._client or httpx.Client(
            timeout=self.settings.openrouter_timeout_seconds
        )
        owns_client = self._client is None
        last_error = "ProviderError"

        try:
            for attempt in range(self.settings.openrouter_max_retries + 1):
                try:
                    response = client.post(
                        f"{self.settings.openrouter_base_url}/chat/completions",
                        headers=self._headers(),
                        json=self._request_body(product_name, description),
                    )
                except httpx.TimeoutException:
                    last_error = "TimeoutError"
                    if self._should_retry(attempt):
                        self._backoff(attempt)
                        continue
                    break
                except httpx.NetworkError:
                    last_error = "ConnectionError"
                    if self._should_retry(attempt):
                        self._backoff(attempt)
                        continue
                    break

                if response.status_code >= 400:
                    last_error = self._http_error_type(response.status_code)
                    if (
                        response.status_code in TRANSIENT_STATUS_CODES
                        and self._should_retry(attempt)
                    ):
                        self._backoff(attempt)
                        continue
                    break

                try:
                    result = self._parse_response(response)
                except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                    last_error = type(exc).__name__
                    break

                self._log_provider(result, job_id, "success")
                return result
        finally:
            if owns_client:
                client.close()

        self._log_failure(job_id, last_error)
        result = self._fallback_result(product_name, description, last_error)
        self._log_provider(result, job_id, "success")
        return result

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": (
                f"Bearer {self.settings.openrouter_api_key.get_secret_value()}"
            ),
            "Content-Type": "application/json",
            "X-OpenRouter-Title": self.settings.openrouter_app_name,
        }
        if self.settings.openrouter_referer:
            headers["HTTP-Referer"] = self.settings.openrouter_referer
        return headers

    def _request_body(
        self, product_name: str, description: str
    ) -> dict[str, Any]:
        return {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": self._system_instruction()},
                {
                    "role": "user",
                    "content": (
                        f"Product name: {product_name.strip()}\n"
                        f"Product description: {description.strip()}"
                    ),
                },
            ],
            "temperature": 0.4,
            "max_tokens": 260,
        }

    def _parse_response(self, response: httpx.Response) -> PromptGenerationResult:
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("Unexpected provider response shape")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Missing provider choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise TypeError("Unexpected provider choice shape")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise TypeError("Unexpected provider message shape")

        prompt = self._extract_content(message.get("content"))
        prompt = re.sub(r"\s+", " ", prompt).strip()
        if len(prompt) < MINIMUM_PROMPT_CHARACTERS:
            raise ValueError("Provider prompt was empty or unreasonably short")

        model = payload.get("model")
        if not isinstance(model, str) or not model.strip():
            model = self.settings.openrouter_model
        return PromptGenerationResult(
            prompt=prompt,
            provider="openrouter",
            model=model.strip(),
            used_fallback=False,
        )

    @staticmethod
    def _extract_content(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return " ".join(parts)
        raise TypeError("Unexpected provider content shape")

    def _should_retry(self, attempt: int) -> bool:
        return attempt < self.settings.openrouter_max_retries

    def _backoff(self, attempt: int) -> None:
        self._sleep(min(0.5 * (2**attempt), 2.0))

    @staticmethod
    def _http_error_type(status_code: int) -> str:
        return {
            400: "InvalidRequestError",
            401: "AuthenticationError",
            403: "PermissionError",
            404: "ModelUnavailableError",
            429: "RateLimitError",
            500: "ProviderServerError",
            502: "ProviderServerError",
            503: "ProviderUnavailableError",
            504: "ProviderTimeoutError",
        }.get(status_code, "ProviderHTTPError")

    @staticmethod
    def _system_instruction() -> str:
        return (
            "Act as an expert commercial product-photography prompt writer. "
            "Return only one concise but detailed lifestyle image-generation "
            "prompt of approximately 80-140 words. Preserve the exact product "
            "shape, proportions, colours, material, patterns, texture, and visible "
            "branding from the reference image. Describe the environment, "
            "composition, camera angle, lighting, shadows, background, depth of "
            "field, and mood. Do not invent unsupported features. Avoid additional "
            "products, duplicate objects, distorted geometry, altered branding, "
            "added text, and watermarks."
        )

    @classmethod
    def _fallback_result(
        cls, product_name: str, description: str, error_type: str
    ) -> PromptGenerationResult:
        return PromptGenerationResult(
            prompt=cls.fallback_prompt(product_name, description),
            provider="fallback",
            model="deterministic-fallback",
            used_fallback=True,
            error_type=error_type,
        )

    @staticmethod
    def fallback_prompt(product_name: str, description: str) -> str:
        return (
            f"Premium commercial lifestyle photograph of {product_name.strip()}. "
            "Use the supplied reference image and preserve the product's exact "
            "shape, proportions, colours, material, patterns, texture, visible "
            f"details, and branding. {description.strip()} Place the product "
            "naturally in a refined, realistic setting with soft directional "
            "window light, gentle shadows, balanced composition, true-to-life "
            "textures, and shallow depth of field. Keep one product fully visible, "
            "centred, and sharply focused. High-end editorial photography with "
            "natural colour grading; no unsupported features, altered branding, "
            "added text, watermark, distortion, cropping, or duplicated products."
        )

    @staticmethod
    def _log_failure(
        job_id: uuid.UUID | str | None, error_type: str
    ) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "prompt_generation",
                    "provider": "openrouter",
                    "status": "failure",
                    "job_id": str(job_id) if job_id is not None else None,
                    "error_type": error_type,
                },
                separators=(",", ":"),
            )
        )

    @staticmethod
    def _log_provider(
        result: PromptGenerationResult,
        job_id: uuid.UUID | str | None,
        status: str,
    ) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "prompt_generation",
                    "provider": result.provider,
                    "status": status,
                    "job_id": str(job_id) if job_id is not None else None,
                    "model": result.model,
                },
                separators=(",", ":"),
            )
        )
