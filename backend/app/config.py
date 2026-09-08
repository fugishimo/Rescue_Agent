from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv


logger = logging.getLogger("uvicorn.error")

BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def load_backend_environment(env_path: Path = BACKEND_ENV_PATH) -> None:
    """Load private local configuration without overriding deployment variables."""

    load_dotenv(dotenv_path=env_path, override=False)
    model = " ".join(os.getenv("ANTHROPIC_MODEL", "").split())
    logger.info(
        "Anthropic configuration: api_key_configured=%s model=%s",
        str(bool(os.getenv("ANTHROPIC_API_KEY", "").strip())).lower(),
        model[:200] if model else "not-configured",
    )
