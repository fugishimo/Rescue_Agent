from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.models.common import DomainModel


class PriorityAlertType(StrEnum):
    HIGH_VALUE_RISK = "high_value_risk"
    HIGH_VALUE_OUTREACH = "high_value_outreach"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class PriorityAlert(DomainModel):
    id: str
    run_id: str
    timestamp: datetime
    booking_id: str
    alert_type: PriorityAlertType
    priority: str = "urgent"
    message: str = Field(min_length=1, max_length=280)


class OpsBrief(DomainModel):
    run_id: str
    generated_at: datetime
    journeys_monitored: int = Field(ge=0)
    interventions_sent: int = Field(ge=0)
    bookings_rescued: int = Field(ge=0)
    gmv_rescued: int = Field(ge=0)
    high_value_cases: int = Field(ge=0)
    unresolved_cases: int = Field(ge=0)
    needs_attention_count: int = Field(ge=0)
    attention_case_ids: tuple[str, ...]
    summary: str = Field(min_length=1, max_length=600)


class OpsBriefResponse(DomainModel):
    run_id: str | None
    run_status: str
    brief: OpsBrief | None
    priority_alerts: tuple[PriorityAlert, ...]
