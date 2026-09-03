import time

import pytest
from fastapi.testclient import TestClient

from app.data.profiles import RENTERS
from app.main import app
from app.models import (
    BookingStatus,
    EventType,
    MessageSource,
    RescueActionStatus,
    RescueOutcome,
)
from app.services.simulation import (
    SIMULATION_ENGINE,
    ScenarioType,
    SimulationAlreadyRunningError,
    SimulationEngine,
    SimulationSnapshot,
    SimulationStatus,
)
from app.services.analytics import build_activity_response, calculate_analytics


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
    assert completed.processed_planned_events == completed.total_planned_events
    assert len(completed.events) > completed.total_planned_events
    assert [event.timestamp for event in completed.events] == sorted(
        event.timestamp for event in completed.events
    )
    assert sum(booking.status is BookingStatus.LOST for booking in completed.bookings) == 1
    assert sum(
        booking.status is BookingStatus.COMPLETED for booking in completed.bookings
    ) == 2
    assert len(completed.scores) == 3
    assert completed.rescue_actions
    assert all(
        action.status is RescueActionStatus.SENT
        for action in completed.rescue_actions
    )
    assert all(action.sent_at for action in completed.rescue_actions)
    assert all(action.message_text for action in completed.rescue_actions)
    assert all(
        action.message_source is MessageSource.FALLBACK_TEMPLATE
        for action in completed.rescue_actions
    )
    assert len(
        {
            (action.booking_id, action.intervention_type)
            for action in completed.rescue_actions
        }
    ) == len(completed.rescue_actions)
    assert any(
        action.outcome is RescueOutcome.RESCUED
        for action in completed.rescue_actions
    )
    assert any(
        action.outcome in {RescueOutcome.NO_RESPONSE, RescueOutcome.LOST}
        for action in completed.rescue_actions
    )
    assert any(
        event.event_type is EventType.RESCUE_SCORE_CHANGED
        for event in completed.events
    )
    assert any(
        event.event_type is EventType.RESCUE_TRIGGERED for event in completed.events
    )
    assert any(event.event_type is EventType.SMS_GENERATED for event in completed.events)
    assert sum(
        event.event_type is EventType.SMS_SENT for event in completed.events
    ) == len(completed.rescue_actions)
    assert any(event.event_type is EventType.SMS_RECEIVED for event in completed.events)
    assert any(
        event.event_type is EventType.BOOKING_RESCUED for event in completed.events
    )
    assert any(event.event_type is EventType.RESCUE_FAILED for event in completed.events)
    generation_events = [
        event for event in completed.events if event.event_type is EventType.SMS_GENERATED
    ]
    assert all(
        event.metadata["message_source"] == MessageSource.FALLBACK_TEMPLATE.value
        for event in generation_events
    )
    assert all(
        score.raw_score == sum(reason.points for reason in score.reasons)
        for score in completed.scores.values()
    )


def test_reset_cancels_pending_demo_sms_delivery() -> None:
    engine = SimulationEngine(duration_seconds=1)
    engine.start(seed=42)

    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and not engine.snapshot().rescue_actions:
        time.sleep(0.005)
    assert engine.snapshot().rescue_actions

    reset = engine.reset()
    time.sleep(0.02)

    assert reset.status is SimulationStatus.IDLE
    assert engine.snapshot().events == ()
    assert engine.snapshot().rescue_actions == ()


def test_activity_log_and_gmv_attribution_stay_coherent() -> None:
    engine = SimulationEngine(duration_seconds=0.15, speed_multiplier=30)
    engine.start(seed=42)
    completed = wait_for_completion(engine)

    activity = build_activity_response(
        list(completed.bookings),
        list(completed.events),
        list(completed.rescue_actions),
    )
    rescued_action = next(
        action
        for action in completed.rescue_actions
        if action.outcome is RescueOutcome.RESCUED
    )
    rescued_booking = next(
        booking
        for booking in completed.bookings
        if booking.id == rescued_action.booking_id
    )

    assert len(activity.records) == len(completed.rescue_actions)
    assert activity.analytics == completed.analytics
    assert activity.analytics.run_bookings_rescued == 1
    assert activity.analytics.run_gmv_rescued == rescued_booking.booking_value
    assert activity.analytics.monthly_gmv_rescued == 48_250 + rescued_booking.booking_value
    assert activity.analytics.monthly_bookings_rescued == 31
    assert activity.analytics.rescue_success_rate == 67.4
    assert all(record.score_reasons for record in activity.records)
    assert all(record.triggering_events for record in activity.records)
    assert all(record.agent_explanation for record in activity.records)
    assert sum(record.gmv_attributed for record in activity.records) == rescued_booking.booking_value
    assert all(
        record.gmv_attributed == 0
        for record in activity.records
        if record.outcome != RescueOutcome.RESCUED.value
    )

    duplicate = rescued_action.model_copy(update={"id": "duplicate_action"})
    duplicate_safe = calculate_analytics(
        list(completed.bookings), [*completed.rescue_actions, duplicate]
    )
    assert duplicate_safe.run_bookings_rescued == 1
    assert duplicate_safe.run_gmv_rescued == rescued_booking.booking_value


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


@pytest.mark.parametrize("seed", range(10))
def test_randomized_runs_preserve_the_demo_story_constraints(seed: int) -> None:
    engine = SimulationEngine(duration_seconds=0.08, speed_multiplier=30)
    engine.start(seed=seed)
    completed = wait_for_completion(engine)
    actions = completed.rescue_actions
    healthy_booking_id = next(
        journey.booking_id
        for journey in completed.selected_journeys
        if journey.scenario is ScenarioType.HEALTHY_COMPLETION
    )
    score_changes_by_booking = {
        booking.id: sum(
            event.booking_id == booking.id
            and event.event_type is EventType.RESCUE_SCORE_CHANGED
            for event in completed.events
        )
        for booking in completed.bookings
    }

    assert len(completed.selected_journeys) == 3
    assert actions
    assert all(action.status is RescueActionStatus.SENT for action in actions)
    assert any(action.outcome is RescueOutcome.RESCUED for action in actions)
    assert any(
        booking.status in {BookingStatus.AT_RISK, BookingStatus.LOST}
        for booking in completed.bookings
    )
    assert all(action.booking_id != healthy_booking_id for action in actions)
    assert max(score_changes_by_booking.values()) >= 2
    assert completed.analytics.run_bookings_rescued == 1
    assert completed.analytics.run_gmv_rescued > 0


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


def test_autopilot_off_holds_actions_but_keeps_scoring() -> None:
    engine = SimulationEngine(duration_seconds=0.1)
    engine.set_autopilot(False)

    engine.start(seed=42)
    completed = wait_for_completion(engine)

    assert completed.autopilot_enabled is False
    assert completed.rescue_actions == ()
    assert any(score.score >= 70 for score in completed.scores.values())
    assert any(
        event.event_type is EventType.AUTOPILOT_ACTION_HELD
        for event in completed.events
    )

    enabled = engine.set_autopilot(True)
    assert enabled.autopilot_enabled is True
    assert enabled.rescue_actions
    engine.reset()


def test_simulation_api_start_conflict_dashboard_and_reset() -> None:
    SIMULATION_ENGINE.reset()
    SIMULATION_ENGINE.set_autopilot(True)
    with TestClient(app) as client:
        idle_response = client.get("/simulation")
        autopilot_off_response = client.post("/autopilot", json={"enabled": False})
        autopilot_on_response = client.post("/autopilot", json={"enabled": True})
        start_response = client.post("/simulation/start", json={"seed": 73})
        conflict_response = client.post("/simulation/start")
        dashboard_response = client.get("/dashboard")
        activity_response = client.get("/activity")
        reset_response = client.post("/simulation/reset")

    assert idle_response.status_code == 200
    assert idle_response.json()["status"] == "idle"
    assert autopilot_off_response.status_code == 200
    assert autopilot_off_response.json()["autopilot_enabled"] is False
    assert autopilot_on_response.status_code == 200
    assert autopilot_on_response.json()["autopilot_enabled"] is True
    assert start_response.status_code == 202
    assert start_response.json()["status"] == "running"
    assert start_response.json()["duration_seconds"] == 90
    assert start_response.json()["speed_multiplier"] == 30
    assert conflict_response.status_code == 409
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["run_id"] == start_response.json()["run_id"]
    assert activity_response.status_code == 200
    assert activity_response.json()["analytics"] == dashboard_response.json()["analytics"]
    assert activity_response.json()["records"] == []
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "idle"
    assert reset_response.json()["events"] == []
