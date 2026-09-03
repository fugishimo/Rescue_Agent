from datetime import date, datetime, timedelta, timezone

import pytest

from app.data.profiles import LISTERS
from app.models import (
    Booking,
    BookingStatus,
    Event,
    EventType,
    InterventionType,
    RescueAction,
    RescueTarget,
)
from app.services.rescue_rules import GuardrailCode, evaluate_rescue_rules
from app.services.rescue_scoring import (
    RescueScore,
    RiskLevel,
    ScoreReasonCode,
    calculate_rescue_score,
)


NOW = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)
SARAH = next(lister for lister in LISTERS if lister.id == "lister_sarah")


def make_booking(
    *,
    status: BookingStatus = BookingStatus.AT_RISK,
    booking_value: int = 2400,
    move_in_days: int = 10,
) -> Booking:
    return Booking(
        id="booking_test",
        renter_id="renter_maya",
        lister_id="lister_sarah",
        listing_id="listing_williamsburg_loft",
        move_in=date(2026, 9, 2) + timedelta(days=move_in_days),
        move_out=date(2026, 10, 2) + timedelta(days=move_in_days),
        booking_value=booking_value,
        status=status,
        created_at=NOW,
        last_activity_at=NOW,
    )


def make_events(
    *items: tuple[EventType, dict[str, object]],
) -> list[Event]:
    return [
        Event(
            id=f"event_{index}",
            booking_id="booking_test",
            event_type=event_type,
            timestamp=NOW + timedelta(seconds=index),
            metadata=metadata,
        )
        for index, (event_type, metadata) in enumerate(items, start=1)
    ]


def critical_lister_score() -> RescueScore:
    return calculate_rescue_score(
        make_booking(booking_value=4501, move_in_days=2),
        make_events(
            (EventType.LISTING_VIEWED, {"view_count": 6}),
            (EventType.INQUIRY_SENT, {}),
            (EventType.BOOKING_STARTED, {}),
            (EventType.BOOKING_REQUESTED, {}),
            (EventType.LISTER_RESPONSE_DELAYED, {"minutes_waiting": 31}),
        ),
        SARAH,
        as_of=date(2026, 9, 2),
    )


def test_score_tiers_do_not_double_count_and_total_caps_at_100() -> None:
    score = critical_lister_score()
    reason_codes = [reason.code for reason in score.reasons]

    assert score.score == 100
    assert score.raw_score == sum(reason.points for reason in score.reasons)
    assert score.raw_score == 140
    assert score.risk_level is RiskLevel.CRITICAL
    assert reason_codes.count(ScoreReasonCode.LISTER_RESPONSE_DELAY) == 1
    assert reason_codes.count(ScoreReasonCode.RESPONSE_ANOMALY) == 1
    assert reason_codes.count(ScoreReasonCode.LISTING_VIEWS) == 1
    assert next(
        reason.points
        for reason in score.reasons
        if reason.code is ScoreReasonCode.LISTER_RESPONSE_DELAY
    ) == 50
    assert next(
        reason.points
        for reason in score.reasons
        if reason.code is ScoreReasonCode.RESPONSE_ANOMALY
    ) == 25


def test_empty_activity_is_healthy_and_requires_no_intervention() -> None:
    score = calculate_rescue_score(
        make_booking(booking_value=1500, move_in_days=30),
        [],
        SARAH,
        as_of=date(2026, 9, 2),
    )

    assert score.score == 0
    assert score.risk_level is RiskLevel.HEALTHY
    assert score.target is None
    assert score.recommended_intervention is None
    assert score.explanation == "No active risk factors. Continue monitoring."


@pytest.mark.parametrize(
    ("events", "move_in_days", "expected_score", "expected_level"),
    [
        (
            make_events(
                (EventType.BOOKING_STARTED, {}),
                (EventType.PAYMENT_FAILED, {}),
            ),
            30,
            50,
            RiskLevel.AT_RISK,
        ),
        (
            make_events(
                (EventType.LISTING_VIEWED, {"view_count": 5}),
                (EventType.INQUIRY_SENT, {}),
                (EventType.BOOKING_STARTED, {}),
                (EventType.PAYMENT_FAILED, {}),
            ),
            30,
            70,
            RiskLevel.HIGH_RISK,
        ),
        (
            make_events(
                (EventType.LISTING_VIEWED, {"view_count": 5}),
                (EventType.INQUIRY_SENT, {}),
                (EventType.BOOKING_STARTED, {}),
                (EventType.PAYMENT_FAILED, {}),
            ),
            2,
            85,
            RiskLevel.CRITICAL,
        ),
    ],
)
def test_risk_level_boundaries(
    events: list[Event],
    move_in_days: int,
    expected_score: int,
    expected_level: RiskLevel,
) -> None:
    score = calculate_rescue_score(
        make_booking(booking_value=1500, move_in_days=move_in_days),
        events,
        SARAH,
        as_of=date(2026, 9, 2),
    )

    assert score.score == expected_score
    assert score.risk_level is expected_level


@pytest.mark.parametrize(
    ("events", "target", "intervention"),
    [
        (
            make_events(
                (EventType.BOOKING_REQUESTED, {}),
                (EventType.LISTER_RESPONSE_DELAYED, {"minutes_waiting": 12}),
            ),
            RescueTarget.LISTER,
            InterventionType.LISTER_REMINDER,
        ),
        (
            make_events((EventType.AVAILABILITY_REQUESTED, {})),
            RescueTarget.LISTER,
            InterventionType.REQUEST_AVAILABILITY,
        ),
        (
            make_events(
                (EventType.BOOKING_STARTED, {}),
                (EventType.CHECKOUT_ABANDONED, {}),
            ),
            RescueTarget.RENTER,
            InterventionType.CHECKOUT_ASSISTANCE,
        ),
        (
            make_events((EventType.PAYMENT_FAILED, {})),
            RescueTarget.RENTER,
            InterventionType.PAYMENT_ASSISTANCE,
        ),
        (
            make_events(
                (EventType.AVAILABILITY_CONFIRMED, {}),
                (EventType.RENTER_INACTIVE, {}),
            ),
            RescueTarget.RENTER,
            InterventionType.RENTER_FOLLOW_UP,
        ),
    ],
)
def test_risk_conditions_map_to_known_interventions(
    events: list[Event],
    target: RescueTarget,
    intervention: InterventionType,
) -> None:
    score = calculate_rescue_score(
        make_booking(),
        events,
        SARAH,
        as_of=date(2026, 9, 2),
    )

    assert score.target is target
    assert score.recommended_intervention is intervention


def test_autopilot_allows_a_valid_high_risk_action() -> None:
    booking = make_booking()
    score = critical_lister_score()

    decision = evaluate_rescue_rules(
        booking=booking,
        score=score,
        autopilot_enabled=True,
        target_id=booking.lister_id,
        recipient_phone_available=True,
        recipient_opted_out=False,
        existing_actions=[],
    )

    assert decision.should_create_action is True
    assert decision.blocked_by is None


@pytest.mark.parametrize(
    ("override", "blocked_by"),
    [
        ({"autopilot_enabled": False}, GuardrailCode.AUTOPILOT_OFF),
        ({"recipient_opted_out": True}, GuardrailCode.RECIPIENT_OPTED_OUT),
        ({"recipient_phone_available": False}, GuardrailCode.PHONE_UNAVAILABLE),
        ({"target_id": None}, GuardrailCode.MISSING_CONTEXT),
    ],
)
def test_recipient_and_autopilot_guardrails(
    override: dict[str, object], blocked_by: GuardrailCode
) -> None:
    booking = make_booking()
    arguments: dict[str, object] = {
        "booking": booking,
        "score": critical_lister_score(),
        "autopilot_enabled": True,
        "target_id": booking.lister_id,
        "recipient_phone_available": True,
        "recipient_opted_out": False,
        "existing_actions": [],
    }
    arguments.update(override)

    decision = evaluate_rescue_rules(**arguments)

    assert decision.should_create_action is False
    assert decision.blocked_by is blocked_by


@pytest.mark.parametrize(
    ("status", "blocked_by"),
    [
        (BookingStatus.CANCELED, GuardrailCode.BOOKING_CANCELED),
        (BookingStatus.COMPLETED, GuardrailCode.BOOKING_COMPLETED),
    ],
)
def test_terminal_booking_guardrails(
    status: BookingStatus, blocked_by: GuardrailCode
) -> None:
    booking = make_booking(status=status)
    decision = evaluate_rescue_rules(
        booking=booking,
        score=critical_lister_score(),
        autopilot_enabled=True,
        target_id=booking.lister_id,
        recipient_phone_available=True,
        recipient_opted_out=False,
        existing_actions=[],
    )

    assert decision.should_create_action is False
    assert decision.blocked_by is blocked_by


def test_duplicate_trigger_and_low_score_guardrails() -> None:
    booking = make_booking()
    score = critical_lister_score()
    existing_action = RescueAction(
        id="action_existing",
        booking_id=booking.id,
        score_at_trigger=score.score,
        intervention_type=InterventionType.LISTER_REMINDER,
        target_type=RescueTarget.LISTER,
        target_id=booking.lister_id,
        reason_summary="Existing lister reminder",
    )

    duplicate = evaluate_rescue_rules(
        booking=booking,
        score=score,
        autopilot_enabled=True,
        target_id=booking.lister_id,
        recipient_phone_available=True,
        recipient_opted_out=False,
        existing_actions=[existing_action],
    )
    low_score = evaluate_rescue_rules(
        booking=booking,
        score=score.model_copy(update={"score": 69, "raw_score": 69}),
        autopilot_enabled=True,
        target_id=booking.lister_id,
        recipient_phone_available=True,
        recipient_opted_out=False,
        existing_actions=[],
    )

    assert duplicate.blocked_by is GuardrailCode.DUPLICATE_TRIGGER
    assert low_score.blocked_by is GuardrailCode.SCORE_BELOW_THRESHOLD
