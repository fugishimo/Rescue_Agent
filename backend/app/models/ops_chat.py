from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.models.common import DomainModel


class OpsChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class OpsChatToolResult(DomainModel):
    tool_name: str = Field(min_length=1, max_length=80)
    result: str = Field(min_length=1, max_length=80)
    data: object


class OpsChatMessage(DomainModel):
    id: str
    timestamp: datetime
    role: OpsChatRole
    content: str = Field(min_length=1, max_length=2_000)
    tool_calls: tuple[OpsChatToolResult, ...] = ()


class OpsChatRequest(DomainModel):
    message: str = Field(min_length=1, max_length=1_000)

    @field_validator("message")
    @classmethod
    def require_visible_message(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("message must contain visible text")
        return normalized


class OpsChatResponse(DomainModel):
    run_id: str | None
    message: OpsChatMessage
