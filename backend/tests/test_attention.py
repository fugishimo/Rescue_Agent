import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    AIActionType,
    AttentionStatus,
    HumanDecision,
    RescueActionStatus,
)
from app.services.ai_tools import AIToolDeniedError
from app.services.attention import is_high_value
from app.services.messaging import MessagingService, RescueMessageContext
from app.services.simulation import (
    SIMULATION_ENGINE,
    ScenarioType,
    SimulationEngine,
    SimulationStatus,
)


class ContextAwareGenerator:
    def generate(self, context: RescueMessageContext) -> str:
        return (
            f"Hi {context.recipient_name} — can you reply with an update on "
            f"{context.listing_name}?"
        )


def _completed_high_value_engine(
    *,
    messaging_service: MessagingService | None = None,
) -> SimulationEngine:
    engine = SimulationEngine(
        duration_seconds=0.15,
        messaging_service=messaging_service,
    )
    engine.start(seed=0)
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if engine.snapshot().status is SimulationStatus.COMPLETED:
            return engine
        time.sleep(0.005)
    raise AssertionError("high-value simulation did not complete")


def test_high_value_classifier_includes_exact_threshold() -> None:
    assert is_high_value(3_999) is False
    assert is_high_value(4_000) is True


def test_high_value_first_message_is_autonomous_and_follow_up_is_gated() -> None:
    engine = _completed_high_value_engine(
        messaging_service=MessagingService(ContextAwareGenerator())
    )
    case = next(case for case in engine.attention_cases() if case.high_value)
    first_actions = [
        action
        for action in engine.snapshot().rescue_actions
        if action.booking_id == case.booking_id
    ]

    assert len(first_actions) == 1
    assert first_actions[0].status is RescueActionStatus.SENT
    assert case.first_sms_action_id == first_actions[0].id
    assert case.status is AttentionStatus.AWAITING_APPROVAL
    assert case.latest_reply
    assert case.drafted_response

    score = engine.snapshot().scores[case.booking_id]
    with pytest.raises(AIToolDeniedError, match="requires explicit Approve AI"):
        engine.dispatch_ai_tool(
            "send_rescue_sms",
            {
                "booking_id": case.booking_id,
                "intervention_type": score.recommended_intervention.value,
                "message": case.drafted_response,
            },
        )

    approved = engine.approve_attention_case(case.id)
    actions = [
        action
        for action in engine.snapshot().rescue_actions
        if action.booking_id == case.booking_id
    ]

    assert approved.status is AttentionStatus.RESOLVED
    assert approved.human_decision is HumanDecision.APPROVE_AI
    assert len(actions) == 2
    assert actions[-1].status is RescueActionStatus.SENT
    assert actions[-1].message_text == case.drafted_response
    assert any(
        log.action_type is AIActionType.HUMAN_APPROVED for log in engine.ai_logs()
    )


def test_human_rescue_blocks_all_further_ai_sends() -> None:
    engine = _completed_high_value_engine(
        messaging_service=MessagingService(ContextAwareGenerator())
    )
    case = next(case for case in engine.attention_cases() if case.high_value)

    human_owned = engine.human_rescue_attention_case(case.id)

    assert human_owned.status is AttentionStatus.HUMAN_HANDLING
    assert human_owned.human_decision is HumanDecision.HUMAN_RESCUE
    score = engine.snapshot().scores[case.booking_id]
    with pytest.raises(AIToolDeniedError, match="Human Rescue owns"):
        engine.dispatch_ai_tool(
            "send_rescue_sms",
            {
                "booking_id": case.booking_id,
                "intervention_type": score.recommended_intervention.value,
                "message": case.drafted_response,
            },
        )


def test_follow_up_provider_failure_escalates_without_sending_fallback() -> None:
    engine = _completed_high_value_engine()
    case = next(case for case in engine.attention_cases() if case.high_value)
    actions = [
        action
        for action in engine.snapshot().rescue_actions
        if action.booking_id == case.booking_id
    ]

    assert case.status is AttentionStatus.NEEDS_ATTENTION
    assert case.drafted_response is None
    assert len(actions) == 1


def test_exception_can_escalate_before_first_outreach_and_api_exposes_case() -> None:
    SIMULATION_ENGINE.reset()
    started = SIMULATION_ENGINE.start(seed=0)
    booking_id = started.bookings[0].id
    escalation = SIMULATION_ENGINE.record_operator_escalation(
        booking_id=booking_id,
        reason="Required marketplace context conflicts.",
    )

    with TestClient(app) as client:
        response = client.get("/ops/attention")
        high_value_response = client.get("/ops/high-value")
        human_response = client.post(
            f"/ops/attention/{escalation['attention_case_id']}/human-rescue"
        )
    SIMULATION_ENGINE.reset()

    assert response.status_code == 200
    assert response.json()[0]["booking_id"] == booking_id
    assert response.json()[0]["first_sms_action_id"] is None
    assert response.json()[0]["status"] == AttentionStatus.NEEDS_ATTENTION.value
    assert human_response.status_code == 200
    assert human_response.json()["status"] == AttentionStatus.HUMAN_HANDLING.value
    assert high_value_response.status_code == 200
    assert high_value_response.json()
    assert all(
        booking["booking_value"] >= 4_000
        for booking in high_value_response.json()
    )


def test_pre_outreach_exception_blocks_autonomous_ai_send() -> None:
    engine = SimulationEngine(duration_seconds=0.15)
    started = engine.start(seed=42)
    booking_id = next(
        journey.booking_id
        for journey in started.selected_journeys
        if journey.scenario is not ScenarioType.HEALTHY_COMPLETION
    )
    engine.record_operator_escalation(
        booking_id=booking_id,
        reason="Required marketplace context conflicts.",
    )

    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if engine.snapshot().status is SimulationStatus.COMPLETED:
            break
        time.sleep(0.005)

    assert engine.snapshot().status is SimulationStatus.COMPLETED
    assert all(
        action.booking_id != booking_id for action in engine.snapshot().rescue_actions
    )
