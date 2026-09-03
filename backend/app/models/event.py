from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.models.common import DomainModel


class EventType(StrEnum):
    LISTING_VIEWED = "listing_viewed"
    INQUIRY_SENT = "inquiry_sent"
    BOOKING_STARTED = "booking_started"
    BOOKING_REQUESTED = "booking_requested"
    LISTER_NOTIFIED = "lister_notified"
    LISTER_RESPONSE_DELAYED = "lister_response_delayed"
    AVAILABILITY_REQUESTED = "availability_requested"
    AVAILABILITY_CONFIRMED = "availability_confirmed"
    CHECKOUT_ABANDONED = "checkout_abandoned"
    PAYMENT_FAILED = "payment_failed"
    RENTER_INACTIVE = "renter_inactive"
    RESCUE_SCORE_CHANGED = "rescue_score_changed"
    RESCUE_TRIGGERED = "rescue_triggered"
    SMS_GENERATED = "sms_generated"
    SMS_SENT = "sms_sent"
    SMS_RECEIVED = "sms_received"
    BOOKING_COMPLETED = "booking_completed"
    BOOKING_CANCELED = "booking_canceled"
    RESCUE_FAILED = "rescue_failed"


class Event(DomainModel):
    id: str
    booking_id: str
    event_type: EventType
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
