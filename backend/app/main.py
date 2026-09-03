import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


app = FastAPI(
    title="Rescue Agent API",
    description="Backend API for the Rescue Snag Bookings demo.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return a small response used by the frontend connectivity check."""
    return {"status": "ok", "service": "rescue-agent-api"}
