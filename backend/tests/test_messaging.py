import json
from datetime import date, datetime, timezone

import pytest

from app.data.profiles import LISTERS, RENTERS
from app.data.seed_data import LISTINGS
from app.models import (
    Booking,
    BookingStatus,
    Event,
    EventType,
    InterventionType,
    MessageSource,
    RescueTarget,
)
from app.services import messaging
from app.services.messaging import (
    GenerationFailureCode,
    MAX_SMS_CHARACTERS,
    MessagingService,
    OpenAIResponsesMessageGenerator,
    RescueMessageContext,
    build_rescue_message_context,
    fallback_message,
    validate_message,
)
from app.services.rescue_scoring import RescueScore, RiskLevel


NOW = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)


def make_context(
    intervention: InterventionType = InterventionType.LISTER_REMINDER,
) -> RescueMessageContext:
    target = (
        RescueTarget.LISTER
        if intervention
        in {InterventionType.LISTER_REMINDER, InterventionType.REQUEST_AVAILABILITY}
        else RescueTarget.RENTER
    )
    return RescueMessageContext(
        recipient_type=target,
        recipient_name="Sarah Chen" if target is RescueTarget.LISTER else "Maya Rodriguez",
        renter_name="Maya Rodriguez",
        listing_name="Williamsburg Loft",
        move_in=date(2026, 9, 8),
        move_out=date(2026, 10, 6),
        booking_value=2400,
        problem="lister_response_delay",
        intervention_type=intervention,
        minutes_waiting=14,
        rescue_score=94,
        score_reasons=("Lister has not responded for 14 minutes",),
    )


class StubGenerator:
    def __init__(
        self,
        output: str = (
            "Hi Sarah — can you check Maya’s Williamsburg Loft request and "
            "confirm the dates?"
        ),
    ):
        self.output = output
        self.contexts: list[RescueMessageContext] = []

    def generate(self, context: RescueMessageContext) -> str:
        self.contexts.append(context)
        return self.output


class FailingGenerator:
    def generate(self, context: RescueMessageContext) -> str:
        raise RuntimeError("provider unavailable")


def test_structured_context_contains_only_approved_booking_facts() -> None:
    renter = next(profile for profile in RENTERS if profile.id == "renter_maya")
    lister = next(profile for profile in LISTERS if profile.id == "lister_sarah")
    listing = next(item for item in LISTINGS if item.id == "listing_williamsburg_loft")
    booking = Booking(
        id="booking_test",
        renter_id=renter.id,
        lister_id=lister.id,
        listing_id=listing.id,
        move_in=date(2026, 9, 8),
        move_out=date(2026, 10, 6),
        booking_value=2400,
        status=BookingStatus.AT_RISK,
        created_at=NOW,
        last_activity_at=NOW,
    )
    score = RescueScore(
        score=94,
        raw_score=94,
        risk_level=RiskLevel.CRITICAL,
        target=RescueTarget.LISTER,
        reasons=(),
        recommended_intervention=InterventionType.LISTER_REMINDER,
        trigger_code="lister_response_delay",
        explanation="Delayed lister response.",
    )
    events = [
        Event(
            id="event_delay",
            booking_id=booking.id,
            event_type=EventType.LISTER_RESPONSE_DELAYED,
            timestamp=NOW,
            metadata={"minutes_waiting": 14},
        )
    ]

    context = build_rescue_message_context(
        booking=booking,
        score=score,
        renter=renter,
        lister=lister,
        listing=listing,
        events=events,
    )

    assert context.recipient_type is RescueTarget.LISTER
    assert context.recipient_name == "Sarah Chen"
    assert context.renter_name == "Maya Rodriguez"
    assert context.listing_name == "Williamsburg Loft"
    assert context.minutes_waiting == 14
    assert context.intervention_type is InterventionType.LISTER_REMINDER


def test_valid_llm_copy_is_normalized_and_marked_openai() -> None:
    generator = StubGenerator(
        "  Hi Sarah — can you check the Williamsburg Loft request\n and confirm?  "
    )
    context = make_context()

    result = MessagingService(generator).generate(context)

    assert generator.contexts == [context]
    assert result.message_source is MessageSource.OPENAI
    assert result.failure_code is None
    assert result.message_text == (
        "Hi Sarah — can you check the Williamsburg Loft request and confirm?"
    )


@pytest.mark.parametrize(
    "candidate",
    [
        "Take 20% off if you act now and finish.",
        "The loft is available — reply to continue.",
        "Pay $500 and reply to continue.",
        "Hi Sarah — confirm the Williamsburg Loft by Sep 9?",
        "Hi Jordan — can you check the Williamsburg Loft request?",
        "Hi Sarah — can you check the SoHo Studio request?",
        "Hi Sarah — urgently check the Williamsburg Loft right away.",
        "A" * (MAX_SMS_CHARACTERS + 1),
        "Here is a booking update.",
    ],
)
def test_invalid_or_unsupported_llm_copy_uses_fallback(candidate: str) -> None:
    result = MessagingService(StubGenerator(candidate)).generate(make_context())

    assert result.message_source is MessageSource.FALLBACK_TEMPLATE
    assert result.failure_code is GenerationFailureCode.INVALID_OUTPUT
    assert result.message_text == fallback_message(make_context())


def test_provider_failure_and_missing_key_use_safe_fallback() -> None:
    unavailable = MessagingService().generate(make_context())
    failed = MessagingService(FailingGenerator()).generate(make_context())

    assert unavailable.failure_code is GenerationFailureCode.MISSING_API_KEY
    assert failed.failure_code is GenerationFailureCode.PROVIDER_ERROR
    assert unavailable.message_source is MessageSource.FALLBACK_TEMPLATE
    assert failed.message_source is MessageSource.FALLBACK_TEMPLATE


@pytest.mark.parametrize("intervention", list(InterventionType))
def test_each_intervention_has_a_valid_deterministic_template(
    intervention: InterventionType,
) -> None:
    context = make_context(intervention)
    message = fallback_message(context)

    assert len(message) <= MAX_SMS_CHARACTERS
    assert validate_message(message, context) == message


def test_openai_generator_uses_responses_structured_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"output_text": json.dumps({"message": "Can you confirm?"})}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(messaging.httpx, "post", fake_post)
    context = make_context()
    generator = OpenAIResponsesMessageGenerator(
        api_key="test-key",
        model="gpt-4o-mini",
    )

    assert generator.generate(context) == "Can you confirm?"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    payload = captured["json"]
    assert payload["input"] == context.model_dump_json()
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
