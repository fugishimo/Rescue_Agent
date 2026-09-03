from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel, ConfigDict

from app.models import Booking, BookingStatus, RescueAction
from app.services.rescue_scoring import RescueScore


AUTOPILOT_THRESHOLD = 70


class GuardrailCode(StrEnum):
    SCORE_BELOW_THRESHOLD = "score_below_threshold"
    NO_INTERVENTION = "no_intervention"
    BOOKING_CANCELED = "booking_canceled"
    BOOKING_COMPLETED = "booking_completed"
    RECIPIENT_OPTED_OUT = "recipient_opted_out"
    DUPLICATE_TRIGGER = "duplicate_trigger"
    MISSING_CONTEXT = "missing_context"
    PHONE_UNAVAILABLE = "phone_unavailable"
    AUTOPILOT_OFF = "autopilot_off"


class RescueRuleDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    should_create_action: bool
    blocked_by: GuardrailCode | None
    explanation: str


def evaluate_rescue_rules(
    *,
    booking: Booking,
    score: RescueScore,
    autopilot_enabled: bool,
    target_id: str | None,
    recipient_phone_available: bool,
    recipient_opted_out: bool,
    existing_actions: Iterable[RescueAction],
) -> RescueRuleDecision:
    """Apply intervention thresholds and guardrails to one score result."""
    if score.score < AUTOPILOT_THRESHOLD:
        return _blocked(
            GuardrailCode.SCORE_BELOW_THRESHOLD,
            f"Score {score.score} is below the Autopilot threshold.",
        )
    if score.recommended_intervention is None or score.target is None:
        return _blocked(
            GuardrailCode.NO_INTERVENTION,
            "No deterministic intervention maps to the active risk factors.",
        )
    if booking.status is BookingStatus.CANCELED:
        return _blocked(GuardrailCode.BOOKING_CANCELED, "Booking is canceled.")
    if booking.status is BookingStatus.COMPLETED:
        return _blocked(GuardrailCode.BOOKING_COMPLETED, "Booking is completed.")
    if recipient_opted_out:
        return _blocked(
            GuardrailCode.RECIPIENT_OPTED_OUT,
            "Recipient has opted out of rescue outreach.",
        )
    if any(
        action.booking_id == booking.id
        and action.intervention_type is score.recommended_intervention
        for action in existing_actions
    ):
        return _blocked(
            GuardrailCode.DUPLICATE_TRIGGER,
            "An action already exists for this booking and trigger.",
        )
    if not target_id or not score.trigger_code:
        return _blocked(
            GuardrailCode.MISSING_CONTEXT,
            "Required rescue context is missing.",
        )
    if not recipient_phone_available:
        return _blocked(
            GuardrailCode.PHONE_UNAVAILABLE,
            "Recipient demo phone contact is unavailable.",
        )
    if not autopilot_enabled:
        return _blocked(
            GuardrailCode.AUTOPILOT_OFF,
            "Action held because Autopilot is off.",
        )
    return RescueRuleDecision(
        should_create_action=True,
        blocked_by=None,
        explanation=score.explanation,
    )


def _blocked(code: GuardrailCode, explanation: str) -> RescueRuleDecision:
    return RescueRuleDecision(
        should_create_action=False,
        blocked_by=code,
        explanation=explanation,
    )
