import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    AIActionType,
    InterventionType,
    MessageSource,
    RescueAction,
    RescueActionStatus,
    RescueOutcome,
    RescueTarget,
)
from app.services.ai_tools import (
    AIToolDeniedError,
    AIToolValidationError,
    UnknownAIToolError,
    approved_ai_tool_definitions,
)
from app.services.simulation import SIMULATION_ENGINE, SimulationEngine, SimulationStatus


APPROVED_TOOLS = {
    "get_marketplace_summary",
    "get_active_bookings",
    "get_at_risk_bookings",
    "get_booking_details",
    "get_recent_rescue_actions",
    "get_high_value_cases",
    "get_lister_performance",
    "get_renter_history",
    "get_lister_history",
    "get_attention_cases",
    "send_rescue_sms",
    "escalate_to_operator",
    "set_autopilot",
}


def _wait_for_completion(engine: SimulationEngine) -> None:
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if engine.snapshot().status is SimulationStatus.COMPLETED:
            return
        time.sleep(0.005)
    raise AssertionError("accelerated simulation did not complete")


def test_registry_contains_only_approved_tools() -> None:
    definitions = approved_ai_tool_definitions()
    names = {str(definition["name"]) for definition in definitions}

    assert names == APPROVED_TOOLS
    assert not names.intersection(
        {
            "change_rescue_score",
            "change_booking_value",
            "mark_booking_completed",
            "mark_booking_rescued",
            "mark_booking_lost",
            "delete_booking",
            "edit_marketplace_event",
        }
    )
    assert all("input_schema" in definition for definition in definitions)


def test_read_tools_inspect_backend_marketplace_state() -> None:
    engine = SimulationEngine(duration_seconds=0.15)
    started = engine.start(seed=42)
    booking_id = started.bookings[0].id

    summary = engine.dispatch_ai_tool("get_marketplace_summary")
    details = engine.dispatch_ai_tool(
        "get_booking_details",
        {"booking_id": booking_id},
    )

    assert summary.data["run_id"] == started.run_id
    assert summary.data["bookings"] == 3
    assert details.data["booking"]["id"] == booking_id
    assert details.data["rescue_score"] == started.scores[booking_id].model_dump(
        mode="json"
    )
    assert engine.ai_logs()[0].action_type is AIActionType.CASE_REVIEWED
    engine.reset()


def test_unregistered_and_invalid_tool_requests_fail_and_are_logged() -> None:
    engine = SimulationEngine(duration_seconds=0.1)

    with pytest.raises(UnknownAIToolError):
        engine.dispatch_ai_tool("change_rescue_score", {"score": 0})
    with pytest.raises(AIToolValidationError):
        engine.dispatch_ai_tool(
            "set_autopilot",
            {"enabled": True, "bypass_policy": True},
        )

    logs = engine.ai_logs()
    assert len(logs) == 2
    assert all(log.action_type is AIActionType.ACTION_DENIED for log in logs)
    assert all(log.result == "denied" for log in logs)


def test_unregistered_tools_cannot_change_scores_or_booking_outcomes() -> None:
    engine = SimulationEngine(duration_seconds=90)
    before = engine.start(seed=42)
    scores_before = {
        booking_id: score.model_dump(mode="json")
        for booking_id, score in before.scores.items()
    }
    statuses_before = {booking.id: booking.status for booking in before.bookings}

    with pytest.raises(UnknownAIToolError):
        engine.dispatch_ai_tool("change_rescue_score", {"score": 0})
    with pytest.raises(UnknownAIToolError):
        engine.dispatch_ai_tool(
            "mark_booking_rescued",
            {"booking_id": before.bookings[0].id},
        )

    after = engine.snapshot()
    assert {
        booking_id: score.model_dump(mode="json")
        for booking_id, score in after.scores.items()
    } == scores_before
    assert {booking.id: booking.status for booking in after.bookings} == statuses_before
    engine.reset()


def test_write_tools_use_backend_validation_and_audit_results() -> None:
    engine = SimulationEngine(duration_seconds=0.15)
    engine.set_autopilot(False)
    started = engine.start(seed=42)
    _wait_for_completion(engine)
    completed = engine.snapshot()
    booking = next(
        booking for booking in completed.bookings if completed.scores[booking.id].score >= 70
    )
    score = completed.scores[booking.id]

    with pytest.raises(AIToolDeniedError, match="Autopilot is off"):
        engine.dispatch_ai_tool(
            "send_rescue_sms",
            {
                "booking_id": booking.id,
                "intervention_type": score.recommended_intervention.value,
                "message": "Backend policy must evaluate this message.",
            },
        )

    escalation = engine.dispatch_ai_tool(
        "escalate_to_operator",
        {"booking_id": started.bookings[0].id, "reason": "Operator review requested."},
    )
    autopilot = engine.dispatch_ai_tool("set_autopilot", {"enabled": False})

    assert escalation.data["status"] == "escalated"
    assert autopilot.data == {"autopilot_enabled": False}
    action_types = {log.action_type for log in engine.ai_logs()}
    assert AIActionType.ACTION_DENIED in action_types
    assert AIActionType.ESCALATED_TO_OPERATOR in action_types
    assert AIActionType.AUTOPILOT_CHANGED in action_types
    engine.reset()


def test_normal_value_ai_messages_are_capped_at_two_without_operator_action() -> None:
    engine = SimulationEngine(duration_seconds=90)
    engine.set_autopilot(False)
    started = engine.start(seed=1)
    booking = next(item for item in started.bookings if item.booking_value < 4_000)
    existing_actions = [
        RescueAction(
            id=f"action_existing_{index}",
            run_id=started.run_id,
            booking_id=booking.id,
            score_at_trigger=80,
            intervention_type=InterventionType.RENTER_FOLLOW_UP,
            target_type=RescueTarget.RENTER,
            target_id=booking.renter_id,
            reason_summary="Previously approved autonomous follow-up.",
            message_text="Can you share an update?",
            message_source=MessageSource.OPENAI,
            status=RescueActionStatus.SENT,
            outcome=RescueOutcome.STILL_AT_RISK,
        )
        for index in range(2)
    ]
    with engine._lock:
        engine._rescue_actions.extend(existing_actions)

    with pytest.raises(AIToolDeniedError, match="message limit"):
        engine.dispatch_ai_tool(
            "send_rescue_sms",
            {
                "booking_id": booking.id,
                "intervention_type": InterventionType.RENTER_FOLLOW_UP.value,
                "message": "Can you share another update?",
            },
        )

    assert len(engine.snapshot().rescue_actions) == 2
    engine.reset()


def test_simulation_records_agent_actions_and_api_returns_newest_first() -> None:
    engine = SimulationEngine(duration_seconds=0.15)
    engine.start(seed=42)
    _wait_for_completion(engine)

    logs = engine.ai_logs()
    action_types = {log.action_type for log in logs}
    assert AIActionType.CASE_REVIEWED in action_types
    assert AIActionType.INTERVENTION_SELECTED in action_types
    assert AIActionType.SMS_REQUESTED in action_types
    assert AIActionType.SMS_SENT in action_types
    assert [log.timestamp for log in logs] == sorted(
        (log.timestamp for log in logs),
        reverse=True,
    )

    SIMULATION_ENGINE.reset()
    entry = SIMULATION_ENGINE.record_ai_log(
        action_type=AIActionType.CASE_REVIEWED,
        reason_summary="Backend facts reviewed.",
        result="success",
        booking_id="booking_test",
        tool_name="get_booking_details",
    )
    with TestClient(app) as client:
        response = client.get("/ops/ai-log")
    SIMULATION_ENGINE.reset()

    assert response.status_code == 200
    assert response.json()[0]["id"] == entry.id
    assert response.json()[0]["reason_summary"] == "Backend facts reviewed."
