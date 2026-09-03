import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.data.seed_data import (
    BOOKINGS,
    EVENTS,
    LISTINGS,
    MARKETPLACE_SEED,
    PROFILE_CATALOG,
    MarketplaceSeed,
    ProfileCatalog,
)
from app.models import Booking, Event, Listing


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


@app.get("/profiles", response_model=ProfileCatalog, tags=["marketplace"])
async def profiles() -> ProfileCatalog:
    """Return the exact simulation profile catalog."""
    return PROFILE_CATALOG


@app.get("/listings", response_model=tuple[Listing, ...], tags=["marketplace"])
async def listings() -> tuple[Listing, ...]:
    """Return seeded listing inventory."""
    return LISTINGS


@app.get("/bookings", response_model=tuple[Booking, ...], tags=["marketplace"])
async def bookings() -> tuple[Booking, ...]:
    """Return the Phase 2 seeded booking journeys."""
    return BOOKINGS


@app.get("/events", response_model=tuple[Event, ...], tags=["marketplace"])
async def events() -> tuple[Event, ...]:
    """Return the seeded booking event history."""
    return EVENTS


@app.get(
    "/marketplace/seed",
    response_model=MarketplaceSeed,
    tags=["marketplace"],
)
async def marketplace_seed() -> MarketplaceSeed:
    """Return all seeded marketplace data in one inspectable payload."""
    return MARKETPLACE_SEED
