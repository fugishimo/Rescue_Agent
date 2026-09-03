import os

from fastapi import FastAPI, HTTPException, status
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
from app.services.analytics import ActivityResponse, build_activity_response
from app.services.simulation import (
    SIMULATION_ENGINE,
    AutopilotRequest,
    SimulationAlreadyRunningError,
    SimulationSnapshot,
    SimulationStartRequest,
)


def _cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS", "").split(",")
    candidates = [
        "http://localhost:3000",
        *configured_origins,
        os.getenv("FRONTEND_ORIGIN", ""),
    ]
    normalized = [origin.strip().rstrip("/") for origin in candidates if origin.strip()]
    return list(dict.fromkeys(normalized))


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
    """Return the seeded booking journeys."""
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


@app.get("/simulation", response_model=SimulationSnapshot, tags=["simulation"])
async def simulation_state() -> SimulationSnapshot:
    """Return the current live simulation snapshot."""
    return SIMULATION_ENGINE.snapshot()


@app.get("/dashboard", response_model=SimulationSnapshot, tags=["simulation"])
async def dashboard_state() -> SimulationSnapshot:
    """Return the live state consumed by the operations dashboard."""
    return SIMULATION_ENGINE.snapshot()


@app.get("/activity", response_model=ActivityResponse, tags=["simulation"])
async def activity_state() -> ActivityResponse:
    """Return the coherent rescue audit trail and monthly impact summary."""
    snapshot = SIMULATION_ENGINE.snapshot()
    return build_activity_response(
        list(snapshot.bookings), list(snapshot.events), list(snapshot.rescue_actions)
    )


@app.post(
    "/simulation/start",
    response_model=SimulationSnapshot,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["simulation"],
)
async def start_simulation(
    request: SimulationStartRequest | None = None,
) -> SimulationSnapshot:
    """Start one randomized 90-second marketplace simulation."""
    try:
        return SIMULATION_ENGINE.start(seed=request.seed if request else None)
    except SimulationAlreadyRunningError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@app.post("/simulation/reset", response_model=SimulationSnapshot, tags=["simulation"])
async def reset_simulation() -> SimulationSnapshot:
    """Stop the current run and restore clean idle state."""
    return SIMULATION_ENGINE.reset()


@app.post("/autopilot", response_model=SimulationSnapshot, tags=["simulation"])
async def set_autopilot(request: AutopilotRequest) -> SimulationSnapshot:
    """Enable or disable deterministic automatic rescue actions."""
    return SIMULATION_ENGINE.set_autopilot(request.enabled)
