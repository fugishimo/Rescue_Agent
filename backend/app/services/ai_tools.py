from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.data.profiles import LISTERS, RENTERS
from app.data.seed_data import LISTINGS
from app.models import (
    BookingStatus,
    AIActionType,
    AIAgentLog,
    InterventionType,
    RescueActionStatus,
)
from app.services.attention import is_high_value


class AIToolError(RuntimeError):
    pass


class UnknownAIToolError(AIToolError):
    pass


class AIToolValidationError(AIToolError):
    pass


class AIToolDeniedError(AIToolError):
    pass


class AIToolDispatchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: str
    result: str
    data: object


class _StrictArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _NoArguments(_StrictArguments):
    pass


class _BookingArguments(_StrictArguments):
    booking_id: str = Field(min_length=1, max_length=120)


class _RenterArguments(_StrictArguments):
    renter_id: str = Field(min_length=1, max_length=120)


class _ListerArguments(_StrictArguments):
    lister_id: str = Field(min_length=1, max_length=120)


class _SendSMSArguments(_BookingArguments):
    intervention_type: InterventionType
    message: str = Field(min_length=1, max_length=240)


class _EscalateArguments(_BookingArguments):
    reason: str = Field(min_length=1, max_length=280)


class _SetAutopilotArguments(_StrictArguments):
    enabled: bool


class AIToolBackend(Protocol):
    def snapshot(self) -> Any: ...

    def ai_logs(self) -> tuple[AIAgentLog, ...]: ...

    def attention_cases(self) -> tuple[Any, ...]: ...

    def record_ai_log(
        self,
        *,
        action_type: AIActionType,
        reason_summary: str,
        result: str,
        booking_id: str | None = None,
        tool_name: str | None = None,
        tool_arguments_summary: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AIAgentLog: ...

    def send_ai_rescue_sms(
        self,
        *,
        booking_id: str,
        intervention_type: InterventionType,
        message: str,
    ) -> Any: ...

    def record_operator_escalation(self, *, booking_id: str, reason: str) -> dict[str, object]: ...

    def set_autopilot(self, enabled: bool) -> Any: ...


_TOOL_ARGUMENT_MODELS: dict[str, type[_StrictArguments]] = {
    "get_marketplace_summary": _NoArguments,
    "get_active_bookings": _NoArguments,
    "get_at_risk_bookings": _NoArguments,
    "get_booking_details": _BookingArguments,
    "get_recent_rescue_actions": _NoArguments,
    "get_high_value_cases": _NoArguments,
    "get_lister_performance": _NoArguments,
    "get_renter_history": _RenterArguments,
    "get_lister_history": _ListerArguments,
    "get_attention_cases": _NoArguments,
    "send_rescue_sms": _SendSMSArguments,
    "escalate_to_operator": _EscalateArguments,
    "set_autopilot": _SetAutopilotArguments,
}

_TOOL_DESCRIPTIONS = {
    "get_marketplace_summary": "Read the current simulation and marketplace totals.",
    "get_active_bookings": "Read all non-terminal booking journeys.",
    "get_at_risk_bookings": "Read bookings currently identified as at risk.",
    "get_booking_details": "Read one booking and its deterministic rescue state.",
    "get_recent_rescue_actions": "Read recent backend-authorized rescue actions.",
    "get_high_value_cases": "Read bookings valued at $4,000 or more.",
    "get_lister_performance": "Read lister response and rescue activity metrics.",
    "get_renter_history": "Read one renter's current booking and event history.",
    "get_lister_history": "Read one lister's current booking and event history.",
    "get_attention_cases": "Read current attention cases when that workflow is enabled.",
    "send_rescue_sms": "Request a rescue SMS through backend policy validation.",
    "escalate_to_operator": "Record a validated operator escalation.",
    "set_autopilot": "Enable or disable Autopilot through the backend.",
}


def approved_ai_tool_definitions() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "name": name,
            "description": _TOOL_DESCRIPTIONS[name],
            "input_schema": arguments.model_json_schema(),
        }
        for name, arguments in _TOOL_ARGUMENT_MODELS.items()
    )


class AIToolDispatcher:
    """Dispatch only registered AI tools through a backend-owned policy boundary."""

    def __init__(self, backend: AIToolBackend) -> None:
        self.backend = backend
        self._handlers: dict[str, Callable[[_StrictArguments], object]] = {
            "get_marketplace_summary": self._marketplace_summary,
            "get_active_bookings": self._active_bookings,
            "get_at_risk_bookings": self._at_risk_bookings,
            "get_booking_details": self._booking_details,
            "get_recent_rescue_actions": self._recent_rescue_actions,
            "get_high_value_cases": self._high_value_cases,
            "get_lister_performance": self._lister_performance,
            "get_renter_history": self._renter_history,
            "get_lister_history": self._lister_history,
            "get_attention_cases": self._attention_cases,
            "send_rescue_sms": self._send_rescue_sms,
            "escalate_to_operator": self._escalate_to_operator,
            "set_autopilot": self._set_autopilot,
        }

    def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, object] | None = None,
    ) -> AIToolDispatchResult:
        safe_name = " ".join(str(tool_name).split())[:80] or "unknown"
        argument_model = _TOOL_ARGUMENT_MODELS.get(tool_name)
        if argument_model is None:
            self._log_denial(safe_name, "Unregistered AI tool request denied.")
            raise UnknownAIToolError(f"unregistered AI tool: {safe_name}")

        try:
            validated = argument_model.model_validate(arguments or {})
        except ValidationError as error:
            self._log_denial(safe_name, "AI tool arguments failed validation.")
            raise AIToolValidationError("invalid AI tool arguments") from error

        try:
            data = self._handlers[tool_name](validated)
        except AIToolDeniedError as error:
            self._log_denial(
                safe_name,
                str(error),
                booking_id=getattr(validated, "booking_id", None),
            )
            raise

        self.backend.record_ai_log(
            action_type=_action_type_for(tool_name),
            reason_summary=_success_reason(tool_name),
            result="success",
            booking_id=getattr(validated, "booking_id", None),
            tool_name=tool_name,
            tool_arguments_summary=_arguments_summary(validated),
        )
        return AIToolDispatchResult(
            tool_name=tool_name,
            result="success",
            data=data,
        )

    def _marketplace_summary(self, _: _StrictArguments) -> dict[str, object]:
        snapshot = self.backend.snapshot()
        return {
            "run_id": snapshot.run_id,
            "status": snapshot.status.value,
            "autopilot_enabled": snapshot.autopilot_enabled,
            "bookings": len(snapshot.bookings),
            "active_bookings": sum(
                booking.status
                not in {BookingStatus.COMPLETED, BookingStatus.CANCELED, BookingStatus.LOST}
                for booking in snapshot.bookings
            ),
            "at_risk_bookings": sum(
                booking.status is BookingStatus.AT_RISK for booking in snapshot.bookings
            ),
            "rescue_actions": len(snapshot.rescue_actions),
            "analytics": snapshot.analytics.model_dump(mode="json"),
        }

    def _active_bookings(self, _: _StrictArguments) -> list[dict[str, object]]:
        snapshot = self.backend.snapshot()
        return [
            _booking_payload(snapshot, booking.id)
            for booking in snapshot.bookings
            if booking.status
            not in {BookingStatus.COMPLETED, BookingStatus.CANCELED, BookingStatus.LOST}
        ]

    def _at_risk_bookings(self, _: _StrictArguments) -> list[dict[str, object]]:
        snapshot = self.backend.snapshot()
        return [
            _booking_payload(snapshot, booking.id)
            for booking in snapshot.bookings
            if booking.status is BookingStatus.AT_RISK
        ]

    def _booking_details(self, arguments: _StrictArguments) -> dict[str, object]:
        snapshot = self.backend.snapshot()
        booking_id = _require_argument(arguments, "booking_id")
        if not any(booking.id == booking_id for booking in snapshot.bookings):
            raise AIToolDeniedError("Booking does not exist in the current marketplace.")
        return _booking_payload(snapshot, booking_id)

    def _recent_rescue_actions(self, _: _StrictArguments) -> list[dict[str, object]]:
        snapshot = self.backend.snapshot()
        actions: list[dict[str, object]] = []
        current_actions = [
            action
            for action in snapshot.rescue_actions
            if action.run_id == snapshot.run_id
            and action.status is RescueActionStatus.SENT
        ]
        for action in current_actions:
            payload = action.model_dump(mode="json")
            participants = RENTERS if action.target_type.value == "renter" else LISTERS
            participant = next(
                (item for item in participants if item.id == action.target_id),
                None,
            )
            payload["target_name"] = participant.name if participant else action.target_id
            booking = _booking_payload(snapshot, action.booking_id)
            payload.update(
                {
                    "renter_name": booking["renter_name"],
                    "lister_name": booking["lister_name"],
                    "listing_name": booking["listing_name"],
                    "booking_status": booking["booking"]["status"],
                }
            )
            actions.append(payload)
        return actions

    def _high_value_cases(self, _: _StrictArguments) -> list[dict[str, object]]:
        snapshot = self.backend.snapshot()
        return [
            _booking_payload(snapshot, booking.id)
            for booking in snapshot.bookings
            if is_high_value(booking)
        ]

    def _lister_performance(self, _: _StrictArguments) -> list[dict[str, object]]:
        snapshot = self.backend.snapshot()
        current_lister_ids = {booking.lister_id for booking in snapshot.bookings}
        return [
            {
                "run_id": snapshot.run_id,
                "lister_id": lister.id,
                "name": lister.name,
                "average_response_minutes": lister.average_response_minutes,
                "acceptance_rate": lister.acceptance_rate,
                "rescue_actions": sum(
                    action.run_id == snapshot.run_id and action.target_id == lister.id
                    for action in snapshot.rescue_actions
                ),
            }
            for lister in LISTERS
            if lister.id in current_lister_ids
        ]

    def _renter_history(self, arguments: _StrictArguments) -> dict[str, object]:
        return self._participant_history("renter_id", _require_argument(arguments, "renter_id"))

    def _lister_history(self, arguments: _StrictArguments) -> dict[str, object]:
        return self._participant_history("lister_id", _require_argument(arguments, "lister_id"))

    def _participant_history(self, field: str, participant_id: str) -> dict[str, object]:
        snapshot = self.backend.snapshot()
        bookings = [
            booking for booking in snapshot.bookings if getattr(booking, field) == participant_id
        ]
        if not bookings:
            raise AIToolDeniedError("Participant has no current marketplace history.")
        booking_ids = {booking.id for booking in bookings}
        return {
            "run_id": snapshot.run_id,
            field: participant_id,
            "bookings": [booking.model_dump(mode="json") for booking in bookings],
            "booking_details": [
                _booking_payload(snapshot, booking.id) for booking in bookings
            ],
            "events": [
                event.model_dump(mode="json")
                for event in snapshot.events
                if event.booking_id in booking_ids
            ],
            "rescue_actions": [
                action.model_dump(mode="json")
                for action in snapshot.rescue_actions
                if action.run_id == snapshot.run_id and action.booking_id in booking_ids
            ],
        }

    def _attention_cases(self, _: _StrictArguments) -> list[dict[str, object]]:
        snapshot = self.backend.snapshot()
        return [
            {"run_id": snapshot.run_id, **case.model_dump(mode="json")}
            for case in self.backend.attention_cases()
            if any(booking.id == case.booking_id for booking in snapshot.bookings)
        ]

    def _send_rescue_sms(self, arguments: _StrictArguments) -> dict[str, object]:
        action = self.backend.send_ai_rescue_sms(
            booking_id=_require_argument(arguments, "booking_id"),
            intervention_type=getattr(arguments, "intervention_type"),
            message=_require_argument(arguments, "message"),
        )
        return action.model_dump(mode="json")

    def _escalate_to_operator(self, arguments: _StrictArguments) -> dict[str, object]:
        return self.backend.record_operator_escalation(
            booking_id=_require_argument(arguments, "booking_id"),
            reason=_require_argument(arguments, "reason"),
        )

    def _set_autopilot(self, arguments: _StrictArguments) -> dict[str, object]:
        snapshot = self.backend.set_autopilot(bool(getattr(arguments, "enabled")))
        return {"autopilot_enabled": snapshot.autopilot_enabled}

    def _log_denial(
        self,
        tool_name: str,
        reason: str,
        booking_id: str | None = None,
    ) -> None:
        self.backend.record_ai_log(
            action_type=AIActionType.ACTION_DENIED,
            reason_summary=reason[:280],
            result="denied",
            booking_id=booking_id,
            tool_name=tool_name,
        )


def _booking_payload(snapshot: Any, booking_id: str) -> dict[str, object]:
    booking = next(booking for booking in snapshot.bookings if booking.id == booking_id)
    score = snapshot.scores.get(booking_id)
    renter = next((item for item in RENTERS if item.id == booking.renter_id), None)
    lister = next((item for item in LISTERS if item.id == booking.lister_id), None)
    listing = next((item for item in LISTINGS if item.id == booking.listing_id), None)
    return {
        "run_id": snapshot.run_id,
        "booking": booking.model_dump(mode="json"),
        "rescue_score": score.model_dump(mode="json") if score else None,
        "renter_name": renter.name if renter else booking.renter_id,
        "lister_name": lister.name if lister else booking.lister_id,
        "listing_name": listing.name if listing else booking.listing_id,
        "events": [
            event.model_dump(mode="json")
            for event in snapshot.events
            if event.booking_id == booking_id
        ],
        "rescue_actions": [
            action.model_dump(mode="json")
            for action in snapshot.rescue_actions
            if action.run_id == snapshot.run_id and action.booking_id == booking_id
        ],
    }


def _require_argument(arguments: _StrictArguments, name: str) -> str:
    value = getattr(arguments, name)
    if not isinstance(value, str):
        raise AIToolValidationError(f"{name} must be a string")
    return value


def _action_type_for(tool_name: str) -> AIActionType:
    return {
        "get_booking_details": AIActionType.CASE_REVIEWED,
        "send_rescue_sms": AIActionType.SMS_REQUESTED,
        "escalate_to_operator": AIActionType.ESCALATED_TO_OPERATOR,
        "set_autopilot": AIActionType.AUTOPILOT_CHANGED,
    }.get(tool_name, AIActionType.CHAT_TOOL_CALLED)


def _success_reason(tool_name: str) -> str:
    return {
        "get_booking_details": "The Rescue Agent reviewed current backend booking facts.",
        "send_rescue_sms": "Backend guardrails approved the AI rescue SMS request.",
        "escalate_to_operator": "Backend recorded the operator escalation.",
        "set_autopilot": "Backend applied the requested Autopilot setting.",
    }.get(tool_name, "The Rescue Agent used an approved marketplace read tool.")


def _arguments_summary(arguments: _StrictArguments) -> str | None:
    values: list[str] = []
    if booking_id := getattr(arguments, "booking_id", None):
        values.append(f"booking_id={booking_id}")
    if renter_id := getattr(arguments, "renter_id", None):
        values.append(f"renter_id={renter_id}")
    if lister_id := getattr(arguments, "lister_id", None):
        values.append(f"lister_id={lister_id}")
    if intervention := getattr(arguments, "intervention_type", None):
        values.append(f"intervention_type={intervention.value}")
    if hasattr(arguments, "enabled"):
        values.append(f"enabled={str(arguments.enabled).lower()}")
    return "; ".join(values) or None
