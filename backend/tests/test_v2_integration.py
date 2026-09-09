import time

from app.models import AIActionType, AttentionStatus, RescueActionStatus
from app.services.attention import is_high_value
from app.services.messaging import MessagingService, RescueMessageContext
from app.services.simulation import SimulationEngine, SimulationStatus


class DeterministicQAGenerator:
    def generate(self, context: RescueMessageContext) -> str:
        if context.is_follow_up:
            return (
                f"Hi {context.recipient_name} — would you like help continuing "
                f"with {context.listing_name}?"
            )
        return f"Hi {context.recipient_name} — can you share an update on {context.listing_name}?"


def _complete(engine: SimulationEngine) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if engine.snapshot().status is SimulationStatus.COMPLETED:
            return
        time.sleep(0.005)
    raise AssertionError("accelerated V2 QA run did not complete")


def test_phase_16_deterministic_high_value_demo_path() -> None:
    engine = SimulationEngine(
        duration_seconds=0.15,
        messaging_service=MessagingService(DeterministicQAGenerator()),
    )
    started = engine.start(seed=0)
    _complete(engine)
    completed = engine.snapshot()

    high_value_booking = next(
        booking for booking in completed.bookings if is_high_value(booking)
    )
    case = next(
        item
        for item in engine.attention_cases()
        if item.booking_id == high_value_booking.id
    )
    first_actions = [
        action
        for action in completed.rescue_actions
        if action.booking_id == high_value_booking.id
    ]

    assert started.run_id == completed.run_id
    assert first_actions[0].status is RescueActionStatus.SENT
    assert case.status is AttentionStatus.AWAITING_APPROVAL
    assert case.drafted_response
    assert len(first_actions) == 1
    assert engine.ops_brief_state().brief is not None
    assert {
        AIActionType.SMS_SENT,
        AIActionType.HIGH_VALUE_FLAGGED,
        AIActionType.FOLLOWUP_DRAFTED,
        AIActionType.OPS_BRIEF_GENERATED,
    }.issubset({entry.action_type for entry in engine.ai_logs()})

    chat = engine.ops_chat("What needs my attention?")
    assert chat.run_id == completed.run_id
    assert chat.message.tool_calls[0].tool_name == "get_attention_cases"
    assert chat.message.tool_calls[0].data[0]["booking_id"] == high_value_booking.id

    scores_before = {
        booking_id: score.model_dump(mode="json")
        for booking_id, score in completed.scores.items()
    }
    statuses_before = {booking.id: booking.status for booking in completed.bookings}
    approved = engine.approve_attention_case(case.id)
    after = engine.snapshot()

    assert approved.status is AttentionStatus.RESOLVED
    assert len(
        [
            action
            for action in after.rescue_actions
            if action.booking_id == high_value_booking.id
        ]
    ) == 2
    assert {
        booking_id: score.model_dump(mode="json")
        for booking_id, score in after.scores.items()
    } == scores_before
    assert {booking.id: booking.status for booking in after.bookings} == statuses_before
    engine.reset()
