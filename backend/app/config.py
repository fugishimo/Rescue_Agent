from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv


logger = logging.getLogger("uvicorn.error")

BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_TIMEOUT_SECONDS = "20"


def load_backend_environment(env_path: Path = BACKEND_ENV_PATH) -> None:
    """Load private local configuration without overriding deployment variables."""

    load_dotenv(dotenv_path=env_path, override=False)
    model = " ".join(os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).split())
    timeout_seconds = " ".join(
        os.getenv("OPENAI_TIMEOUT_SECONDS", DEFAULT_OPENAI_TIMEOUT_SECONDS).split()
    )
    logger.info(
        "AI provider configuration: provider=openai api_key_configured=%s "
        "model=%s timeout_seconds=%s",
        str(bool(os.getenv("OPENAI_API_KEY", "").strip())).lower(),
        model[:200] if model else DEFAULT_OPENAI_MODEL,
        timeout_seconds[:40] if timeout_seconds else DEFAULT_OPENAI_TIMEOUT_SECONDS,
    )
