import time

from fastapi.testclient import TestClient

from app.main import app
from app.models import AIActionType, PriorityAlertType
from app.services.attention import is_high_value
from app.services.messaging import MessagingService
from app.services.simulation import SimulationEngine, SimulationStatus


def _wait_for_completion(engine: SimulationEngine) -> None:
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if engine.snapshot().status is SimulationStatus.COMPLETED:
            return
        time.sleep(0.005)
    raise AssertionError("accelerated simulation did not complete")


def test_completed_run_generates_one_factual_ops_brief() -> None:
    engine = SimulationEngine(
        duration_seconds=0.15,
        messaging_service=MessagingService(),
    )
    started = engine.start(seed=0)

    assert engine.ops_brief_state().brief is None

    _wait_for_completion(engine)
    snapshot = engine.snapshot()
    first_response = engine.ops_brief_state()
    second_response = engine.ops_brief_state()
    brief = first_response.brief

    assert brief is not None
    assert first_response.run_status == SimulationStatus.COMPLETED.value
    assert brief == second_response.brief
    assert brief.run_id == started.run_id
    assert brief.journeys_monitored == len(snapshot.selected_journeys)
    assert brief.interventions_sent == sum(
        action.sent_at is not None for action in snapshot.rescue_actions
    )
    assert brief.bookings_rescued == snapshot.analytics.run_bookings_rescued
    assert brief.gmv_rescued == snapshot.analytics.run_gmv_rescued
    assert brief.high_value_cases == sum(
        is_high_value(booking) for booking in snapshot.bookings
    )
    assert brief.needs_attention_count == len(engine.attention_cases())
    assert brief.attention_case_ids == tuple(
        reversed(tuple(case.id for case in engine.attention_cases()))
    )
    assert f"${brief.gmv_rescued:,}" in brief.summary
    assert sum(
        log.action_type is AIActionType.OPS_BRIEF_GENERATED
        for log in engine.ai_logs()
    ) == 1


def test_live_alerts_are_deduplicated_and_high_value_only() -> None:
    engine = SimulationEngine(
        duration_seconds=0.15,
        messaging_service=MessagingService(),
    )
    engine.start(seed=0)
    _wait_for_completion(engine)

    snapshot = engine.snapshot()
    high_value_ids = {
        booking.id for booking in snapshot.bookings if is_high_value(booking)
    }
    alerts = engine.ops_brief_state().priority_alerts

    assert alerts
    assert {alert.booking_id for alert in alerts} <= high_value_ids
    assert len({(alert.alert_type, alert.booking_id) for alert in alerts}) == len(alerts)
    assert PriorityAlertType.HIGH_VALUE_RISK in {alert.alert_type for alert in alerts}
    assert PriorityAlertType.HIGH_VALUE_OUTREACH in {
        alert.alert_type for alert in alerts
    }
    assert PriorityAlertType.HUMAN_REVIEW_REQUIRED in {
        alert.alert_type for alert in alerts
    }


def test_provider_outage_still_produces_brief_and_reset_clears_it() -> None:
    engine = SimulationEngine(
        duration_seconds=0.15,
        messaging_service=MessagingService(),
    )
    engine.start(seed=42)
    _wait_for_completion(engine)

    assert engine.ops_brief_state().brief is not None
    reset = engine.reset()
    response = engine.ops_brief_state()

    assert reset.status is SimulationStatus.IDLE
    assert response.brief is None
    assert response.priority_alerts == ()


def test_ops_brief_api_returns_idle_state_before_a_run() -> None:
    with TestClient(app) as client:
        response = client.get("/ops/brief")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"run_id", "run_status", "brief", "priority_alerts"}
