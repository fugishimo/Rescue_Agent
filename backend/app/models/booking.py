from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from app.models.common import DomainModel


class BookingStatus(StrEnum):
    BROWSING = "browsing"
    INQUIRY = "inquiry"
    CHECKOUT_STARTED = "checkout_started"
    BOOKING_REQUESTED = "booking_requested"
    AWAITING_LISTER = "awaiting_lister"
    AWAITING_AVAILABILITY = "awaiting_availability"
    PAYMENT_ISSUE = "payment_issue"
    AT_RISK = "at_risk"
    RESCUED = "rescued"
    COMPLETED = "completed"
    CANCELED = "canceled"
    LOST = "lost"


class RescueTarget(StrEnum):
    RENTER = "renter"
    LISTER = "lister"


class Booking(DomainModel):
    id: str
    renter_id: str
    lister_id: str
    listing_id: str
    move_in: date
    move_out: date
    booking_value: int = Field(gt=0)
    status: BookingStatus
    rescue_score: int = Field(default=0, ge=0, le=100)
    risk_level: str = "healthy"
    rescue_target: RescueTarget | None = None
    created_at: datetime
    last_activity_at: datetime
    at_risk_at: datetime | None = None
    rescued_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "Booking":
        if self.move_out <= self.move_in:
            raise ValueError("move_out must be after move_in")
        if self.last_activity_at < self.created_at:
            raise ValueError("last_activity_at must not precede created_at")
        return self
