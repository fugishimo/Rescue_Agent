from pydantic import Field

from app.models.common import DomainModel, ValueRange


class Renter(DomainModel):
    id: str
    name: str
    phone_demo_id: str | None
    opted_out: bool = False
    archetype: str
    intent_level: str
    responsiveness: str
    listing_view_behavior: str
    checkout_abandonment_tendency: str
    payment_failure_tendency: str
    price_sensitivity: str
    move_in_urgency: str
    sms_responsiveness: str
    views_before_action: ValueRange[int]
    move_in_days_range: ValueRange[int]
    booking_value_range: ValueRange[int]
    checkout_abandonment_rate: float = Field(ge=0, le=1)
    payment_failure_rate: float = Field(ge=0, le=1)
    sms_response_rate: float = Field(ge=0, le=1)
    post_confirmation_inactivity_rate: float | None = Field(default=None, ge=0, le=1)
    delay_between_actions: str | None = None
    best_rescue_scenario: str
    successful_sms_response: str | None = None
    likely_failed_outcome: str
