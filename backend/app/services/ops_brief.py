from __future__ import annotations

from datetime import datetime

from app.models import AttentionCase, Booking, BookingStatus, RescueAction
from app.models.ops_brief import OpsBrief
from app.services.analytics import calculate_analytics
from app.services.attention import is_high_value


_UNRESOLVED_STATUSES = {
    BookingStatus.AT_RISK,
    BookingStatus.PAYMENT_ISSUE,
    BookingStatus.AWAITING_LISTER,
    BookingStatus.AWAITING_AVAILABILITY,
}


def build_ops_brief(
    *,
    run_id: str,
    generated_at: datetime,
    journeys_monitored: int,
    bookings: tuple[Booking, ...],
    rescue_actions: tuple[RescueAction, ...],
    active_attention_cases: tuple[AttentionCase, ...],
) -> OpsBrief:
    """Build one factual run summary from backend-owned state only."""
    analytics = calculate_analytics(bookings, rescue_actions)
    interventions_sent = sum(action.sent_at is not None for action in rescue_actions)
    high_value_cases = sum(is_high_value(booking) for booking in bookings)
    unresolved_cases = sum(
        booking.status in _UNRESOLVED_STATUSES for booking in bookings
    )
    needs_attention_count = len(active_attention_cases)
    summary = (
        f"Monitored {journeys_monitored} booking journeys and sent "
        f"{interventions_sent} rescue interventions. "
        f"{analytics.run_bookings_rescued} bookings completed after intervention, "
        f"representing ${analytics.run_gmv_rescued:,} in rescued GMV. "
        f"{unresolved_cases} cases remain unresolved, including "
        f"{needs_attention_count} requiring operator attention."
    )
    return OpsBrief(
        run_id=run_id,
        generated_at=generated_at,
        journeys_monitored=journeys_monitored,
        interventions_sent=interventions_sent,
        bookings_rescued=analytics.run_bookings_rescued,
        gmv_rescued=analytics.run_gmv_rescued,
        high_value_cases=high_value_cases,
        unresolved_cases=unresolved_cases,
        needs_attention_count=needs_attention_count,
        attention_case_ids=tuple(case.id for case in active_attention_cases),
        summary=summary,
    )
