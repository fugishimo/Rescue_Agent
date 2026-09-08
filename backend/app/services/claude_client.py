from __future__ import annotations

import json
import logging
import re
from typing import Any

from anthropic import Anthropic


logger = logging.getLogger("uvicorn.error")

_MAX_LOG_DETAIL_CHARACTERS = 2_000
_SECRET_VALUE_PATTERN = re.compile(
    r"(?i)((?:x-api-key|api[_-]?key|authorization|token|secret|password|credential)"
    r"\s*[:=]\s*)"
    r"(?:bearer\s+)?[^\s,}\]]+"
)
_ANTHROPIC_KEY_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_-]+", re.IGNORECASE)
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


class ClaudeClient:
    """Small server-side wrapper around Anthropic's Messages API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 5,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._client = client or Anthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    def generate_text(
        self,
        *,
        system: str,
        prompt: str,
        output_schema: dict[str, object],
        max_tokens: int,
    ) -> str:
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": output_schema,
                    }
                },
            )
        except Exception as error:
            status_code = getattr(error, "status_code", None)
            logger.warning(
                "Anthropic request failed: error_type=%s status_code=%s "
                "message=%s body=%s",
                type(error).__name__,
                status_code if isinstance(status_code, int) else "unavailable",
                _safe_log_detail(str(error), self._api_key),
                _safe_log_detail(getattr(error, "body", None), self._api_key),
            )
            raise
        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
            and isinstance(getattr(block, "text", None), str)
        ]
        if not text_blocks:
            raise ValueError("Claude returned no text content")
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
    detail = _ANTHROPIC_KEY_PATTERN.sub("[REDACTED]", detail)
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
