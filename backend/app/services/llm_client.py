from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

import httpx


logger = logging.getLogger("uvicorn.error")

_MAX_LOG_DETAIL_CHARACTERS = 2_000
_SECRET_VALUE_PATTERN = re.compile(
    r"(?i)((?:x-api-key|api[_-]?key|authorization|token|secret|password|credential)"
    r"\s*[:=]\s*)"
    r"(?:bearer\s+)?[^\s,}\]]+"
)
_OPENAI_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+", re.IGNORECASE)
_SENSITIVE_FIELD_NAMES = {
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "x_api_key",
}


class LLMClient(Protocol):
    """Provider-neutral text generation boundary used by product services."""

    def generate_text(
        self,
        *,
        system: str,
        prompt: str,
        output_schema: dict[str, object],
        max_tokens: int,
    ) -> str: ...


class OpenAIResponsesClient:
    """OpenAI Responses API adapter behind the provider-neutral LLM boundary."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 20,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_seconds)

    def generate_text(
        self,
        *,
        system: str,
        prompt: str,
        output_schema: dict[str, object],
        max_tokens: int,
    ) -> str:
        try:
            response = self._client.post(
                f"{self._base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": system,
                    "input": prompt,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "rescue_sms",
                            "strict": True,
                            "schema": output_schema,
                        }
                    },
                    "max_output_tokens": max_tokens,
                    "store": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            error_response = getattr(error, "response", None)
            status_code = getattr(error_response, "status_code", None)
            if status_code is None:
                status_code = getattr(error, "status_code", None)
            response_body = getattr(error_response, "text", None)
            if response_body is None:
                response_body = getattr(error, "body", None)
            logger.warning(
                "LLM provider request failed: provider=openai error_type=%s "
                "status_code=%s message=%s body=%s",
                type(error).__name__,
                status_code if isinstance(status_code, int) else "unavailable",
                _safe_log_detail(str(error), self._api_key),
                _safe_log_detail(response_body, self._api_key),
            )
            raise

        output_text = _extract_output_text(payload)
        if not output_text:
            raise ValueError("LLM provider returned no text content")
        return output_text


def _extract_output_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    direct_text = payload.get("output_text")
    if isinstance(direct_text, str):
        return direct_text

    text_blocks: list[str] = []
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if block.get("type") in {"output_text", "text"} and isinstance(text, str):
                text_blocks.append(text)
    return "".join(text_blocks)


def _safe_log_detail(value: object, api_key: str) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, (dict, list, tuple)):
        detail = json.dumps(
            _redact_sensitive_fields(value),
            default=str,
            ensure_ascii=True,
        )
    else:
        detail = str(value)
    if api_key:
        detail = detail.replace(api_key, "[REDACTED]")
    detail = _OPENAI_KEY_PATTERN.sub("[REDACTED]", detail)
    detail = _SECRET_VALUE_PATTERN.sub(r"\1[REDACTED]", detail)
    detail = " ".join(detail.split())
    if len(detail) > _MAX_LOG_DETAIL_CHARACTERS:
        return f"{detail[:_MAX_LOG_DETAIL_CHARACTERS]}...[truncated]"
    return detail


def _redact_sensitive_fields(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if str(key).casefold().replace("-", "_") in _SENSITIVE_FIELD_NAMES
                else _redact_sensitive_fields(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_sensitive_fields(item) for item in value]
    return value
