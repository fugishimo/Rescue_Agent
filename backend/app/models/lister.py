from pydantic import Field

from app.models.common import DomainModel, ValueRange


class Lister(DomainModel):
    id: str
    name: str
    phone_demo_id: str
    archetype: str
    average_response_minutes: int = Field(gt=0)
    average_response_range: ValueRange[int]
    acceptance_rate: float = Field(ge=0, le=1)
    availability_reliability: str
    availability_confirmation_rate: float | None = Field(default=None, ge=0, le=1)
    app_engagement: str
    sms_responsiveness: str
    sms_response_rate: float = Field(ge=0, le=1)
    delayed_response_frequency: str
    delay_probability: float = Field(ge=0, le=1)
    missed_app_notification_rate: float | None = Field(default=None, ge=0, le=1)
    best_rescue_scenario: str
    representative_sms_response: str | None = None
    design_purpose: str
