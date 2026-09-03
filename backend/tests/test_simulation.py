import time

import pytest
from fastapi.testclient import TestClient

from app.data.profiles import RENTERS
from app.main import app
from app.models import BookingStatus, EventType
from app.services.simulation import (
    SIMULATION_ENGINE,
    ScenarioType,
    SimulationAlreadyRunningError,
    SimulationEngine,
    SimulationSnapshot,
    SimulationStatus,
)


def wait_for_completion(
    engine: SimulationEngine, timeout_seconds: float = 1
) -> SimulationSnapshot:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        snapshot = engine.snapshot()
        if snapshot.status is SimulationStatus.COMPLETED:
            return snapshot
        time.sleep(0.005)
    raise AssertionError("accelerated simulation did not complete in time")


def test_accelerated_run_generates_events_and_valid_mixed_outcomes() -> None:
    engine = SimulationEngine(duration_seconds=0.15, speed_multiplier=30)

    started = engine.start(seed=42)
    completed = wait_for_completion(engine)

    assert started.status is SimulationStatus.RUNNING
    assert started.duration_seconds == 0.15
    assert len(started.selected_journeys) == 3
    assert {journey.scenario for journey in started.selected_journeys} >= {
        ScenarioType.LISTER_DELAY,
        ScenarioType.HEALTHY_COMPLETION,
    }
    assert completed.status is SimulationStatus.COMPLETED
    assert completed.progress_percent == 100
    assert len(completed.events) == completed.total_planned_events
    assert len(completed.events) >= 14
    assert [event.timestamp for event in completed.events] == sorted(
        event.timestamp for event in completed.events
    )
    assert sum(
        booking.status is BookingStatus.AT_RISK for booking in completed.bookings
    ) == 2
    assert sum(
        booking.status is BookingStatus.COMPLETED for booking in completed.bookings
    ) == 1


def test_generated_booking_values_and_dates_follow_profile_ranges() -> None:
    engine = SimulationEngine(duration_seconds=0.05)
    renters = {renter.id: renter for renter in RENTERS}

    snapshot = engine.start(seed=101)

    for booking in snapshot.bookings:
        renter = renters[booking.renter_id]
        move_in_days = (booking.move_in - booking.created_at.date()).days
        assert renter.booking_value_range.minimum <= booking.booking_value
        assert booking.booking_value <= renter.booking_value_range.maximum
        assert renter.move_in_days_range.minimum <= move_in_days
        assert move_in_days <= renter.move_in_days_range.maximum

    for event in wait_for_completion(engine).events:
        if event.event_type is EventType.LISTING_VIEWED:
            booking = next(
                booking for booking in snapshot.bookings if booking.id == event.booking_id
            )
            renter = renters[booking.renter_id]
            assert renter.views_before_action.minimum <= event.metadata["view_count"]
            assert event.metadata["view_count"] <= renter.views_before_action.maximum

    engine.reset()


def test_duplicate_start_is_rejected_and_reset_allows_clean_second_run() -> None:
    engine = SimulationEngine(duration_seconds=0.1)

    first = engine.start(seed=1)
    with pytest.raises(SimulationAlreadyRunningError):
        engine.start(seed=2)

    reset = engine.reset()
    second = engine.start(seed=2)

    assert reset.status is SimulationStatus.IDLE
    assert reset.run_id is None
    assert reset.bookings == ()
    assert reset.events == ()
    assert second.status is SimulationStatus.RUNNING
    assert second.run_id != first.run_id
    assert second.seed == 2
    assert (
        second.selected_journeys != first.selected_journeys
        or second.bookings != first.bookings
    )

    engine.reset()


def test_simulation_api_start_conflict_dashboard_and_reset() -> None:
    SIMULATION_ENGINE.reset()
    with TestClient(app) as client:
        idle_response = client.get("/simulation")
        start_response = client.post("/simulation/start", json={"seed": 73})
        conflict_response = client.post("/simulation/start")
        dashboard_response = client.get("/dashboard")
        reset_response = client.post("/simulation/reset")

    assert idle_response.status_code == 200
    assert idle_response.json()["status"] == "idle"
    assert start_response.status_code == 202
    assert start_response.json()["status"] == "running"
    assert start_response.json()["duration_seconds"] == 90
    assert start_response.json()["speed_multiplier"] == 30
    assert conflict_response.status_code == 409
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["run_id"] == start_response.json()["run_id"]
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "idle"
    assert reset_response.json()["events"] == []
