from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.models.common import DomainModel


class AIActionType(StrEnum):
    CASE_REVIEWED = "CASE_REVIEWED"
    INTERVENTION_SELECTED = "INTERVENTION_SELECTED"
    SMS_REQUESTED = "SMS_REQUESTED"
    SMS_SENT = "SMS_SENT"
    ACTION_DENIED = "ACTION_DENIED"
    HIGH_VALUE_FLAGGED = "HIGH_VALUE_FLAGGED"
    ESCALATED_TO_OPERATOR = "ESCALATED_TO_OPERATOR"
    FOLLOWUP_DRAFTED = "FOLLOWUP_DRAFTED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_TAKEOVER = "HUMAN_TAKEOVER"
    OPS_BRIEF_GENERATED = "OPS_BRIEF_GENERATED"
    CHAT_TOOL_CALLED = "CHAT_TOOL_CALLED"
    AUTOPILOT_CHANGED = "AUTOPILOT_CHANGED"


class AIAgentLog(DomainModel):
    id: str
    timestamp: datetime
    booking_id: str | None = None
    action_type: AIActionType
    reason_summary: str = Field(min_length=1, max_length=280)
    tool_name: str | None = Field(default=None, max_length=80)
    tool_arguments_summary: str | None = Field(default=None, max_length=280)
    result: str = Field(min_length=1, max_length=80)
    metadata: dict[str, object] = Field(default_factory=dict)
