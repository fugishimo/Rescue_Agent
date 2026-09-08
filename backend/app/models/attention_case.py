from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.models.common import DomainModel


class AttentionStatus(StrEnum):
    NEEDS_ATTENTION = "needs_attention"
    AWAITING_APPROVAL = "awaiting_approval"
    HUMAN_HANDLING = "human_handling"
    RESOLVED = "resolved"


class HumanDecision(StrEnum):
    APPROVE_AI = "approve_ai"
    HUMAN_RESCUE = "human_rescue"


class AttentionCase(DomainModel):
    id: str
    booking_id: str
    reason: str = Field(min_length=1, max_length=280)
    priority: str = Field(min_length=1, max_length=40)
    high_value: bool
    status: AttentionStatus
    created_at: datetime
    first_sms_action_id: str | None = None
    latest_reply: str | None = Field(default=None, max_length=500)
    drafted_response: str | None = Field(default=None, max_length=240)
    ai_recommendation: str = Field(min_length=1, max_length=280)
    human_decision: HumanDecision | None = None
    resolved_at: datetime | None = None
