from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    Booking,
    Event,
    EventType,
    InterventionType,
    Lister,
    RescueTarget,
)


class RiskLevel(StrEnum):
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"


class ScoreReasonCode(StrEnum):
    LISTER_RESPONSE_DELAY = "LISTER_RESPONSE_DELAY"
    RESPONSE_ANOMALY = "RESPONSE_ANOMALY"
    LISTING_VIEWS = "LISTING_VIEWS"
    INQUIRY_SENT = "INQUIRY_SENT"
    BOOKING_STARTED = "BOOKING_STARTED"
    MOVE_IN_URGENCY = "MOVE_IN_URGENCY"
    BOOKING_VALUE = "BOOKING_VALUE"
    CHECKOUT_ABANDONED = "CHECKOUT_ABANDONED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    AVAILABILITY_UNCONFIRMED = "AVAILABILITY_UNCONFIRMED"


class ScoreReason(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: ScoreReasonCode
    points: int = Field(gt=0)
    label: str


class RescueScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: int = Field(ge=0, le=100)
    raw_score: int = Field(ge=0)
    risk_level: RiskLevel
    target: RescueTarget | None
    reasons: tuple[ScoreReason, ...]
    recommended_intervention: InterventionType | None
    trigger_code: str | None
    explanation: str


def calculate_rescue_score(
    booking: Booking,
    events: tuple[Event, ...] | list[Event],
    lister: Lister,
    *,
    as_of: date | None = None,
) -> RescueScore:
    """Calculate the canonical deterministic rescue score for one booking."""
    booking_events = sorted(
        (event for event in events if event.booking_id == booking.id),
        key=lambda event: event.timestamp,
    )
    reasons: list[ScoreReason] = []

    listing_views = max(
        (
            int(event.metadata.get("view_count", 1))
            for event in booking_events
            if event.event_type is EventType.LISTING_VIEWED
        ),
        default=0,
    )
    if listing_views >= 5:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.LISTING_VIEWS,
                points=10,
                label=f"Renter viewed the listing {listing_views} times",
            )
        )
    elif listing_views >= 3:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.LISTING_VIEWS,
                points=5,
                label=f"Renter viewed the listing {listing_views} times",
            )
        )

    if _has_event(booking_events, EventType.INQUIRY_SENT):
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.INQUIRY_SENT,
                points=10,
                label="Renter sent an inquiry",
            )
        )

    booking_started = _has_event(booking_events, EventType.BOOKING_STARTED)
    if booking_started:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.BOOKING_STARTED,
                points=15,
                label="Renter started booking",
            )
        )

    score_date = as_of or booking.last_activity_at.date()
    days_until_move_in = (booking.move_in - score_date).days
    if days_until_move_in < 0:
        urgency_points = 0
    elif days_until_move_in <= 3:
        urgency_points = 15
    elif days_until_move_in <= 7:
        urgency_points = 10
    elif days_until_move_in <= 14:
        urgency_points = 5
    else:
        urgency_points = 0
    if urgency_points:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.MOVE_IN_URGENCY,
                points=urgency_points,
                label=f"Move-in is in {max(0, days_until_move_in)} days",
            )
        )

    if booking.booking_value > 4000:
        value_points = 15
    elif booking.booking_value > 2500:
        value_points = 10
    elif booking.booking_value > 1500:
        value_points = 5
    else:
        value_points = 0
    if value_points:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.BOOKING_VALUE,
                points=value_points,
                label=f"Booking value is ${booking.booking_value:,}",
            )
        )

    delay_event = _latest_event(booking_events, EventType.LISTER_RESPONSE_DELAYED)
    minutes_waiting = _metadata_number(delay_event, "minutes_waiting")
    if minutes_waiting > 30:
        delay_points = 50
    elif minutes_waiting > 20:
        delay_points = 35
    elif minutes_waiting > 10:
        delay_points = 20
    elif minutes_waiting > 5:
        delay_points = 10
    else:
        delay_points = 0
    if delay_points:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.LISTER_RESPONSE_DELAY,
                points=delay_points,
                label=f"Lister has not responded for {minutes_waiting:g} minutes",
            )
        )

    response_ratio = (
        minutes_waiting / lister.average_response_minutes
        if minutes_waiting and lister.average_response_minutes
        else 0
    )
    if response_ratio > 4:
        anomaly_points = 25
    elif response_ratio > 2:
        anomaly_points = 15
    else:
        anomaly_points = 0
    if anomaly_points:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.RESPONSE_ANOMALY,
                points=anomaly_points,
                label=(
                    f"Current delay is {response_ratio:.1f}× the lister's "
                    "historical average"
                ),
            )
        )

    checkout_abandoned = booking_started and _has_event(
        booking_events, EventType.CHECKOUT_ABANDONED
    )
    if checkout_abandoned:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.CHECKOUT_ABANDONED,
                points=30,
                label="Booking checkout was abandoned",
            )
        )

    payment_failed = _has_event(booking_events, EventType.PAYMENT_FAILED)
    if payment_failed:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.PAYMENT_FAILED,
                points=35,
                label="Payment attempt failed",
            )
        )

    availability_requested_at = _latest_timestamp(
        booking_events, EventType.AVAILABILITY_REQUESTED
    )
    availability_confirmed_at = _latest_timestamp(
        booking_events, EventType.AVAILABILITY_CONFIRMED
    )
    availability_unconfirmed = availability_requested_at is not None and (
        availability_confirmed_at is None
        or availability_confirmed_at < availability_requested_at
    )
    if availability_unconfirmed:
        reasons.append(
            ScoreReason(
                code=ScoreReasonCode.AVAILABILITY_UNCONFIRMED,
                points=20,
                label="Requested dates remain unconfirmed",
            )
        )

    renter_inactive_at = _latest_timestamp(booking_events, EventType.RENTER_INACTIVE)
    renter_inactive_after_confirmation = (
        availability_confirmed_at is not None
        and renter_inactive_at is not None
        and renter_inactive_at > availability_confirmed_at
    )

    target, intervention, trigger_code = _recommended_action(
        booking_events=booking_events,
        payment_failed=payment_failed,
        checkout_abandoned=checkout_abandoned,
        renter_inactive_after_confirmation=renter_inactive_after_confirmation,
        availability_unconfirmed=availability_unconfirmed,
        delay_event=delay_event,
    )
    raw_score = sum(reason.points for reason in reasons)
    score = min(100, raw_score)
    risk_level = _risk_level(score)
    explanation = _explanation(reasons, intervention)

    return RescueScore(
        score=score,
        raw_score=raw_score,
        risk_level=risk_level,
        target=target,
        reasons=tuple(reasons),
        recommended_intervention=intervention,
        trigger_code=trigger_code,
        explanation=explanation,
    )


def _recommended_action(
    *,
    booking_events: list[Event],
    payment_failed: bool,
    checkout_abandoned: bool,
    renter_inactive_after_confirmation: bool,
    availability_unconfirmed: bool,
    delay_event: Event | None,
) -> tuple[RescueTarget | None, InterventionType | None, str | None]:
    if payment_failed:
        return (
            RescueTarget.RENTER,
            InterventionType.PAYMENT_ASSISTANCE,
            "payment_failure",
        )
    if checkout_abandoned:
        return (
            RescueTarget.RENTER,
            InterventionType.CHECKOUT_ASSISTANCE,
            "checkout_abandonment",
        )
    if renter_inactive_after_confirmation:
        return (
            RescueTarget.RENTER,
            InterventionType.RENTER_FOLLOW_UP,
            "post_confirmation_inactivity",
        )
    if availability_unconfirmed:
        return (
            RescueTarget.LISTER,
            InterventionType.REQUEST_AVAILABILITY,
            "availability_unconfirmed",
        )
    if delay_event is not None and _has_event(
        booking_events, EventType.BOOKING_REQUESTED
    ):
        return (
            RescueTarget.LISTER,
            InterventionType.LISTER_REMINDER,
            "lister_response_delay",
        )
    return None, None, None


def _risk_level(score: int) -> RiskLevel:
    if score >= 85:
        return RiskLevel.CRITICAL
    if score >= 70:
        return RiskLevel.HIGH_RISK
    if score >= 50:
        return RiskLevel.AT_RISK
    return RiskLevel.HEALTHY


def _explanation(
    reasons: list[ScoreReason], intervention: InterventionType | None
) -> str:
    if not reasons:
        return "No active risk factors. Continue monitoring."
    strongest = sorted(reasons, key=lambda reason: reason.points, reverse=True)[:2]
    factors = " + ".join(reason.label for reason in strongest)
    if intervention is None:
        return f"{factors}. Continue monitoring."
    action = intervention.value.replace("_", " ").lower()
    return f"{factors}. Recommended action: {action}."


def _has_event(events: list[Event], event_type: EventType) -> bool:
    return any(event.event_type is event_type for event in events)


def _latest_event(events: list[Event], event_type: EventType) -> Event | None:
    return next(
        (event for event in reversed(events) if event.event_type is event_type),
        None,
    )


def _latest_timestamp(events: list[Event], event_type: EventType) -> datetime | None:
    event = _latest_event(events, event_type)
    return event.timestamp if event else None


def _metadata_number(event: Event | None, key: str) -> float:
    if event is None:
        return 0
    value = event.metadata.get(key, 0)
    return float(value) if isinstance(value, (int, float)) else 0
