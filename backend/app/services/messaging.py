from __future__ import annotations

import json
import os
import re
from datetime import date
from enum import StrEnum
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    Booking,
    Event,
    EventType,
    InterventionType,
    Lister,
    Listing,
    MessageSource,
    Renter,
    RescueTarget,
)
from app.services.rescue_scoring import RescueScore


MAX_SMS_CHARACTERS = 240
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

SYSTEM_INSTRUCTIONS = """You write one booking-rescue SMS using only the supplied JSON facts.
The deterministic rescue system has already selected the recipient and intervention; do not
change either. Write naturally, identify the relevant booking, and ask for one clear next
action. Keep the message at or below 240 characters. Never invent dates, pricing,
availability, causes, policies, or urgency. Never offer a discount, promise availability,
pressure the recipient, or make a manipulative claim. Return only the required JSON."""

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "minLength": 1,
            "maxLength": MAX_SMS_CHARACTERS,
        }
    },
    "required": ["message"],
    "additionalProperties": False,
}


class GenerationFailureCode(StrEnum):
    MISSING_API_KEY = "missing_api_key"
    PROVIDER_ERROR = "provider_error"
    INVALID_OUTPUT = "invalid_output"


class RescueMessageContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    recipient_type: RescueTarget
    recipient_name: str
    renter_name: str
    listing_name: str
    move_in: date
    move_out: date
    booking_value: int = Field(gt=0)
    problem: str
    intervention_type: InterventionType
    minutes_waiting: float | None = Field(default=None, ge=0)
    rescue_score: int = Field(ge=0, le=100)
    score_reasons: tuple[str, ...]


class MessageGenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_text: str
    message_source: MessageSource
    failure_code: GenerationFailureCode | None = None


class MessageGenerator(Protocol):
    def generate(self, context: RescueMessageContext) -> str: ...


class OpenAIResponsesMessageGenerator:
    """Generate tightly structured copy through the OpenAI Responses API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
        timeout_seconds: float = 5,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, context: RescueMessageContext) -> str:
        response = httpx.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "instructions": SYSTEM_INSTRUCTIONS,
                "input": context.model_dump_json(),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "rescue_sms",
                        "strict": True,
                        "schema": _OUTPUT_SCHEMA,
                    }
                },
                "max_output_tokens": 120,
                "store": False,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        output_text = response.json().get("output_text")
        if not isinstance(output_text, str):
            raise ValueError("Responses API returned no output text")
        parsed = json.loads(output_text)
        message = parsed.get("message") if isinstance(parsed, dict) else None
        if not isinstance(message, str):
            raise ValueError("Responses API returned no message")
        return message


class MessagingService:
    def __init__(
        self,
        generator: MessageGenerator | None = None,
        *,
        unavailable_code: GenerationFailureCode = GenerationFailureCode.MISSING_API_KEY,
    ) -> None:
        self.generator = generator
        self.unavailable_code = unavailable_code

    @classmethod
    def from_environment(cls) -> "MessagingService":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return cls()
        return cls(
            OpenAIResponsesMessageGenerator(
                api_key=api_key,
                model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
                base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
            )
        )

    def generate(self, context: RescueMessageContext) -> MessageGenerationResult:
        if self.generator is None:
            return _fallback_result(context, self.unavailable_code)
        try:
            candidate = self.generator.generate(context)
        except Exception:
            return _fallback_result(context, GenerationFailureCode.PROVIDER_ERROR)

        validated = validate_message(candidate, context)
        if validated is None:
            return _fallback_result(context, GenerationFailureCode.INVALID_OUTPUT)
        return MessageGenerationResult(
            message_text=validated,
            message_source=MessageSource.OPENAI,
        )


def build_rescue_message_context(
    *,
    booking: Booking,
    score: RescueScore,
    renter: Renter,
    lister: Lister,
    listing: Listing,
    events: list[Event] | tuple[Event, ...],
) -> RescueMessageContext:
    if score.target is None or score.recommended_intervention is None:
        raise ValueError("rescue score does not contain a messageable intervention")
    recipient_name = renter.name if score.target is RescueTarget.RENTER else lister.name
    delay_event = next(
        (
            event
            for event in reversed(events)
            if event.event_type is EventType.LISTER_RESPONSE_DELAYED
        ),
        None,
    )
    waiting = delay_event.metadata.get("minutes_waiting") if delay_event else None
    minutes_waiting = (
        float(waiting) if isinstance(waiting, (int, float)) else None
    )
    return RescueMessageContext(
        recipient_type=score.target,
        recipient_name=recipient_name,
        renter_name=renter.name,
        listing_name=listing.name,
        move_in=booking.move_in,
        move_out=booking.move_out,
        booking_value=booking.booking_value,
        problem=score.trigger_code or "booking_risk",
        intervention_type=score.recommended_intervention,
        minutes_waiting=minutes_waiting,
        rescue_score=score.score,
        score_reasons=tuple(reason.label for reason in score.reasons),
    )


def validate_message(
    candidate: str,
    context: RescueMessageContext,
) -> str | None:
    message = " ".join(candidate.split()) if isinstance(candidate, str) else ""
    if not message or len(message) > MAX_SMS_CHARACTERS:
        return None

    lowered = message.casefold()
    prohibited = (
        "discount",
        "promo code",
        "coupon",
        "free month",
        "act now",
        "last chance",
        "urgent",
        "immediately",
        "asap",
        "right away",
        "guaranteed",
        "definitely available",
        "dates are available",
        "is available",
        "http://",
        "https://",
        "www.",
    )
    if any(term in lowered for term in prohibited) or re.search(r"\b\d+(?:\.\d+)?%", message):
        return None

    required_facts = (
        context.recipient_name.split()[0].casefold(),
        context.listing_name.casefold(),
    )
    if not all(fact in lowered for fact in required_facts):
        return None

    allowed_numbers = {
        context.booking_value,
        context.move_in.day,
        context.move_in.month,
        context.move_in.year,
        context.move_out.day,
        context.move_out.month,
        context.move_out.year,
        context.rescue_score,
    }
    if context.minutes_waiting is not None:
        allowed_numbers.add(int(context.minutes_waiting))
    for numeric_text in re.findall(r"\b\d[\d,]*\b", message):
        if int(numeric_text.replace(",", "")) not in allowed_numbers:
            return None

    month_numbers = {
        month.casefold(): index
        for index, month in enumerate(
            (
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ),
            start=1,
        )
    }
    allowed_dates = {
        (context.move_in.month, context.move_in.day),
        (context.move_out.month, context.move_out.day),
    }
    for month, day in re.findall(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})\b",
        message,
        flags=re.IGNORECASE,
    ):
        if (month_numbers[month[:3].casefold()], int(day)) not in allowed_dates:
            return None

    action_language = (
        "?",
        "reply",
        "confirm",
        "check",
        "continue",
        "finish",
        "complete",
        "try again",
        "review",
    )
    if not any(term in lowered for term in action_language):
        return None
    return message


def fallback_message(context: RescueMessageContext) -> str:
    move_in = _friendly_date(context.move_in)
    move_out = _friendly_date(context.move_out)
    values = {
        InterventionType.LISTER_REMINDER: (
            f"Hi {context.recipient_name} — {context.renter_name} is interested in "
            f"{context.listing_name} for {move_in}–{move_out}. Can you check the "
            "request and confirm the dates?"
        ),
        InterventionType.REQUEST_AVAILABILITY: (
            f"Hi {context.recipient_name} — can you confirm whether "
            f"{context.listing_name} can accommodate {context.renter_name} from "
            f"{move_in}–{move_out}?"
        ),
        InterventionType.CHECKOUT_ASSISTANCE: (
            f"Hi {context.recipient_name} — your booking for {context.listing_name} "
            "wasn’t completed. Would you like to continue or get help with the next step?"
        ),
        InterventionType.PAYMENT_ASSISTANCE: (
            f"Hi {context.recipient_name} — your booking for {context.listing_name} "
            "needs another payment attempt. Please try again when ready, or reply if "
            "you need help."
        ),
        InterventionType.RENTER_FOLLOW_UP: (
            f"Hi {context.recipient_name} — are you still interested in continuing "
            f"your booking for {context.listing_name}, {move_in}–{move_out}?"
        ),
    }
    message = values[context.intervention_type]
    if len(message) > MAX_SMS_CHARACTERS:
        raise ValueError("deterministic fallback exceeds SMS character limit")
    return message


def _fallback_result(
    context: RescueMessageContext,
    failure_code: GenerationFailureCode,
) -> MessageGenerationResult:
    return MessageGenerationResult(
        message_text=fallback_message(context),
        message_source=MessageSource.FALLBACK_TEMPLATE,
        failure_code=failure_code,
    )


def _friendly_date(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}"
