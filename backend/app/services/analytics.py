from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.data.profiles import LISTERS, RENTERS
from app.data.seed_data import LISTINGS
from app.models import Booking, BookingStatus, Event, EventType, RescueAction, RescueOutcome


BASELINE_MONTHLY_GMV = 48_250
BASELINE_MONTHLY_RESCUES = 30
BASELINE_MONTHLY_RESOLVED_ACTIONS = 44


class RescueAnalytics(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_gmv_rescued: int = Field(ge=0)
    baseline_bookings_rescued: int = Field(ge=0)
    run_gmv_rescued: int = Field(ge=0)
    run_bookings_rescued: int = Field(ge=0)
    monthly_gmv_rescued: int = Field(ge=0)
    monthly_bookings_rescued: int = Field(ge=0)
    rescue_success_rate: float = Field(ge=0, le=100)
    active_rescue_cases: int = Field(ge=0)
    total_demo_sms_sent: int = Field(ge=0)


class ActivityScoreReason(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    label: str
    points: int


class ActivityRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    action_id: str
    timestamp: datetime
    booking_id: str
    booking_label: str
    renter_name: str
    listing_name: str
    target_type: str
    target_name: str
    trigger: str
    triggering_events: tuple[str, ...]
    score: int = Field(ge=0, le=100)
    score_reasons: tuple[ActivityScoreReason, ...]
    agent_explanation: str
    intervention: str
    message_text: str | None
    message_source: str | None
    message_status: str
    sent_at: datetime | None
    response_text: str | None
    response_at: datetime | None
    outcome: str
    resulting_booking_state: str
    gmv_attributed: int = Field(ge=0)


class ActivityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    analytics: RescueAnalytics
    records: tuple[ActivityRecord, ...]


def rescued_booking_ids(
    bookings: tuple[Booking, ...] | list[Booking],
    actions: tuple[RescueAction, ...] | list[RescueAction],
) -> set[str]:
    bookings_by_id = {booking.id: booking for booking in bookings}
    return {
        action.booking_id
        for action in actions
        if action.sent_at is not None
        and action.outcome is RescueOutcome.RESCUED
        and (booking := bookings_by_id.get(action.booking_id)) is not None
        and booking.at_risk_at is not None
        and booking.status is BookingStatus.COMPLETED
    }


def calculate_analytics(
    bookings: tuple[Booking, ...] | list[Booking],
    actions: tuple[RescueAction, ...] | list[RescueAction],
) -> RescueAnalytics:
    bookings_by_id = {booking.id: booking for booking in bookings}
    rescued_ids = rescued_booking_ids(bookings, actions)
    run_gmv = sum(bookings_by_id[booking_id].booking_value for booking_id in rescued_ids)
    resolved_actions = sum(
        action.outcome is not RescueOutcome.PENDING for action in actions
    )
    monthly_rescues = BASELINE_MONTHLY_RESCUES + len(rescued_ids)
    monthly_resolved = BASELINE_MONTHLY_RESOLVED_ACTIONS + resolved_actions

    return RescueAnalytics(
        baseline_gmv_rescued=BASELINE_MONTHLY_GMV,
        baseline_bookings_rescued=BASELINE_MONTHLY_RESCUES,
        run_gmv_rescued=run_gmv,
        run_bookings_rescued=len(rescued_ids),
        monthly_gmv_rescued=BASELINE_MONTHLY_GMV + run_gmv,
        monthly_bookings_rescued=monthly_rescues,
        rescue_success_rate=round((monthly_rescues / monthly_resolved) * 100, 1),
        active_rescue_cases=sum(
            booking.status in {BookingStatus.AT_RISK, BookingStatus.RESCUED}
            for booking in bookings
        ),
        total_demo_sms_sent=sum(action.sent_at is not None for action in actions),
    )


def build_activity_response(
    bookings: tuple[Booking, ...] | list[Booking],
    events: tuple[Event, ...] | list[Event],
    actions: tuple[RescueAction, ...] | list[RescueAction],
) -> ActivityResponse:
    bookings_by_id = {booking.id: booking for booking in bookings}
    renters_by_id = {renter.id: renter for renter in RENTERS}
    listers_by_id = {lister.id: lister for lister in LISTERS}
    listings_by_id = {listing.id: listing for listing in LISTINGS}
    triggers_by_action = {
        str(event.metadata.get("action_id")): event
        for event in events
        if event.event_type is EventType.RESCUE_TRIGGERED
        and event.metadata.get("action_id")
    }
    rescued_ids = rescued_booking_ids(bookings, actions)
    records: list[ActivityRecord] = []

    for action in actions:
        booking = bookings_by_id[action.booking_id]
        renter = renters_by_id[booking.renter_id]
        listing = listings_by_id[booking.listing_id]
        trigger_event = triggers_by_action.get(action.id)
        trigger_metadata = trigger_event.metadata if trigger_event else {}
        raw_reasons = trigger_metadata.get("score_reasons", [])
        score_reasons = tuple(
            ActivityScoreReason.model_validate(reason)
            for reason in raw_reasons
            if isinstance(reason, dict)
        )
        target_name = (
            renter.name
            if action.target_type.value == "renter"
            else listers_by_id[booking.lister_id].name
        )
        trigger_time = trigger_event.timestamp if trigger_event else action.sent_at
        triggering_events = tuple(
            str(event.metadata.get("description", event.event_type.value))
            for event in sorted(
                (
                    event
                    for event in events
                    if event.booking_id == booking.id
                    and event.event_type
                    not in {
                        EventType.RESCUE_SCORE_CHANGED,
                        EventType.RESCUE_TRIGGERED,
                        EventType.SMS_GENERATED,
                        EventType.SMS_SENT,
                        EventType.SMS_RECEIVED,
                        EventType.BOOKING_RESCUED,
                        EventType.RESCUE_FAILED,
                    }
                    and (trigger_time is None or event.timestamp <= trigger_time)
                ),
                key=lambda event: event.timestamp,
            )[-4:]
        )
        records.append(
            ActivityRecord(
                id=f"activity_{action.id}",
                action_id=action.id,
                timestamp=(
                    trigger_event.timestamp
                    if trigger_event
                    else action.sent_at or booking.last_activity_at
                ),
                booking_id=booking.id,
                booking_label=f"{renter.name} → {listing.name}",
                renter_name=renter.name,
                listing_name=listing.name,
                target_type=action.target_type.value,
                target_name=target_name,
                trigger=str(trigger_metadata.get("trigger_code") or "RESCUE_THRESHOLD"),
                triggering_events=triggering_events,
                score=action.score_at_trigger,
                score_reasons=score_reasons,
                agent_explanation=action.reason_summary,
                intervention=action.intervention_type.value,
                message_text=action.message_text,
                message_source=(
                    action.message_source.value if action.message_source else None
                ),
                message_status=action.status.value,
                sent_at=action.sent_at,
                response_text=action.response_text,
                response_at=action.response_at,
                outcome=action.outcome.value,
                resulting_booking_state=booking.status.value,
                gmv_attributed=(
                    booking.booking_value if booking.id in rescued_ids else 0
                ),
            )
        )

    records.sort(key=lambda record: record.timestamp, reverse=True)
    return ActivityResponse(
        analytics=calculate_analytics(bookings, actions),
        records=tuple(records),
    )
