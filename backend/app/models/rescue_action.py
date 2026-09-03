from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.models.booking import RescueTarget
from app.models.common import DomainModel


class InterventionType(StrEnum):
    LISTER_REMINDER = "LISTER_REMINDER"
    REQUEST_AVAILABILITY = "REQUEST_AVAILABILITY"
    CHECKOUT_ASSISTANCE = "CHECKOUT_ASSISTANCE"
    PAYMENT_ASSISTANCE = "PAYMENT_ASSISTANCE"
    RENTER_FOLLOW_UP = "RENTER_FOLLOW_UP"


class RescueActionStatus(StrEnum):
    PENDING = "pending"
    GENERATED = "generated"
    SENT = "sent"
    HELD = "held"
    FAILED = "failed"


class MessageSource(StrEnum):
    OPENAI = "openai"
    FALLBACK_TEMPLATE = "fallback_template"


class RescueOutcome(StrEnum):
    PENDING = "pending"
    RESCUED = "rescued"
    NO_RESPONSE = "no_response"
    STILL_AT_RISK = "still_at_risk"
    LOST = "lost"


class RescueAction(DomainModel):
    id: str
    booking_id: str
    score_at_trigger: int = Field(ge=0, le=100)
    intervention_type: InterventionType
    target_type: RescueTarget
    target_id: str
    reason_summary: str
    message_text: str | None = None
    message_source: MessageSource | None = None
    status: RescueActionStatus = RescueActionStatus.PENDING
    sent_at: datetime | None = None
    response_text: str | None = None
    response_at: datetime | None = None
    outcome: RescueOutcome = RescueOutcome.PENDING
