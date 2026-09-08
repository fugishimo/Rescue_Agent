from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.data.profiles import LISTERS, RENTERS
from app.data.seed_data import LISTINGS
from app.models import (
    AttentionCase,
    AttentionStatus,
    Booking,
    BookingStatus,
    AIActionType,
    AIAgentLog,
    Event,
    EventType,
    InterventionType,
    HumanDecision,
    Lister,
    Listing,
    MessageSource,
    Renter,
    RescueAction,
    RescueActionStatus,
    RescueOutcome,
    RescueTarget,
)
from app.services.attention import is_high_value
from app.services.analytics import RescueAnalytics, calculate_analytics
from app.services.ai_tools import (
    AIToolDeniedError,
    AIToolDispatchResult,
    AIToolDispatcher,
)
from app.services.messaging import (
    MessageGenerationResult,
    MessagingService,
    RescueMessageContext,
    build_rescue_message_context,
    validate_message,
)
from app.services.rescue_rules import (
    GuardrailCode,
    RescueRuleDecision,
    evaluate_rescue_rules,
)
from app.services.rescue_scoring import RescueScore, calculate_rescue_score


class SimulationStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"


class ScenarioType(StrEnum):
    LISTER_DELAY = "lister_delay"
    CHECKOUT_ABANDONMENT = "checkout_abandonment"
    PAYMENT_FAILURE = "payment_failure"
    HEALTHY_COMPLETION = "healthy_completion"


class SelectedJourney(BaseModel):
    model_config = ConfigDict(frozen=True)

    booking_id: str
    scenario: ScenarioType
    renter_id: str
    lister_id: str
    listing_id: str


class SimulationSnapshot(BaseModel):
    run_id: str | None
    seed: int | None
    status: SimulationStatus
    duration_seconds: float
    speed_multiplier: int
    autopilot_enabled: bool
    started_at: datetime | None
    completed_at: datetime | None
    elapsed_seconds: float = Field(ge=0)
    progress_percent: float = Field(ge=0, le=100)
    total_planned_events: int = Field(ge=0)
    processed_planned_events: int = Field(ge=0)
    selected_journeys: tuple[SelectedJourney, ...]
    bookings: tuple[Booking, ...]
    events: tuple[Event, ...]
    scores: dict[str, RescueScore]
    rescue_actions: tuple[RescueAction, ...]
    analytics: RescueAnalytics


class SimulationStartRequest(BaseModel):
    seed: int | None = None


class AutopilotRequest(BaseModel):
    enabled: bool


class SimulationAlreadyRunningError(RuntimeError):
    pass


class AttentionCaseNotFoundError(RuntimeError):
    pass


class AttentionActionDeniedError(RuntimeError):
    pass


@dataclass(frozen=True)
class _EventStep:
    event_type: EventType
    next_status: BookingStatus
    description: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class _PlannedEvent:
    offset_seconds: float
    booking_id: str
    scenario: ScenarioType
    step: _EventStep


@dataclass(frozen=True)
class _JourneyPlan:
    journey: SelectedJourney
    booking: Booking
    steps: tuple[_EventStep, ...]


@dataclass(frozen=True)
class _ResponsePlan:
    should_respond: bool
    successful: bool
    response_text: str | None
    outcome: RescueOutcome


_ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.BROWSING: {
        BookingStatus.BROWSING,
        BookingStatus.INQUIRY,
        BookingStatus.CHECKOUT_STARTED,
    },
    BookingStatus.INQUIRY: {BookingStatus.BOOKING_REQUESTED},
    BookingStatus.CHECKOUT_STARTED: {
        BookingStatus.AT_RISK,
        BookingStatus.PAYMENT_ISSUE,
        BookingStatus.COMPLETED,
    },
    BookingStatus.BOOKING_REQUESTED: {
        BookingStatus.AWAITING_LISTER,
        BookingStatus.AWAITING_AVAILABILITY,
    },
    BookingStatus.AWAITING_LISTER: {
        BookingStatus.AT_RISK,
        BookingStatus.CHECKOUT_STARTED,
    },
    BookingStatus.AWAITING_AVAILABILITY: {
        BookingStatus.AT_RISK,
        BookingStatus.CHECKOUT_STARTED,
    },
    BookingStatus.PAYMENT_ISSUE: {BookingStatus.AT_RISK},
    BookingStatus.AT_RISK: {BookingStatus.LOST, BookingStatus.RESCUED},
    BookingStatus.RESCUED: {BookingStatus.COMPLETED},
    BookingStatus.COMPLETED: set(),
    BookingStatus.CANCELED: set(),
    BookingStatus.LOST: set(),
}


class SimulationEngine:
    """Thread-safe, in-memory engine for a single live simulation run."""

    def __init__(
        self,
        duration_seconds: float = 90,
        speed_multiplier: int = 30,
        messaging_service: MessagingService | None = None,
    ):
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if speed_multiplier <= 0:
            raise ValueError("speed_multiplier must be positive")

        self.duration_seconds = duration_seconds
        self.speed_multiplier = speed_multiplier
        self.messaging_service = messaging_service or MessagingService()
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._delivery_threads: list[threading.Thread] = []
        self._response_rng = random.Random()
        self._planned_action_count = 0
        self._autopilot_enabled = True
        self._run_id: str | None = None
        self._seed: int | None = None
        self._status = SimulationStatus.IDLE
        self._started_at: datetime | None = None
        self._started_monotonic: float | None = None
        self._completed_at: datetime | None = None
        self._journeys: tuple[SelectedJourney, ...] = ()
        self._bookings: dict[str, Booking] = {}
        self._events: list[Event] = []
        self._plan: tuple[_PlannedEvent, ...] = ()
        self._processed_planned_events = 0
        self._scores: dict[str, RescueScore] = {}
        self._rescue_actions: list[RescueAction] = []
        self._ai_logs: list[AIAgentLog] = []
        self._attention_cases: list[AttentionCase] = []
        self._human_owned_booking_ids: set[str] = set()
        self._held_triggers: set[tuple[str, str]] = set()
        self._ai_tools = AIToolDispatcher(self)

    def start(self, seed: int | None = None) -> SimulationSnapshot:
        with self._lock:
            if self._status is SimulationStatus.RUNNING:
                raise SimulationAlreadyRunningError("a simulation is already running")

            chosen_seed = seed if seed is not None else random.SystemRandom().randrange(2**32)
            rng = random.Random(chosen_seed)
            run_id = f"run_{uuid4().hex[:12]}"
            started_at = datetime.now(timezone.utc)
            journeys = self._build_journeys(run_id, started_at, rng)
            plan = self._schedule_events(journeys, rng)

            self._cancel = threading.Event()
            self._delivery_threads = []
            self._response_rng = random.Random(chosen_seed ^ 0x5A17C0DE)
            self._planned_action_count = 0
            self._run_id = run_id
            self._seed = chosen_seed
            self._status = SimulationStatus.RUNNING
            self._started_at = started_at
            self._started_monotonic = time.monotonic()
            self._completed_at = None
            self._journeys = tuple(journey.journey for journey in journeys)
            self._bookings = {journey.booking.id: journey.booking for journey in journeys}
            self._events = []
            self._plan = plan
            self._processed_planned_events = 0
            self._scores = {}
            self._rescue_actions = []
            self._ai_logs = []
            self._attention_cases = []
            self._human_owned_booking_ids = set()
            self._held_triggers = set()
            for booking_id in self._bookings:
                self._refresh_score(booking_id, record_event=False)
            self._thread = threading.Thread(
                target=self._run,
                args=(run_id, self._cancel),
                name=f"simulation-{run_id}",
                daemon=True,
            )
            self._thread.start()
            return self._snapshot_locked()

    def reset(self) -> SimulationSnapshot:
        with self._lock:
            thread = self._thread
            delivery_threads = tuple(self._delivery_threads)
            cancel = self._cancel
            cancel.set()

        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
        for delivery_thread in delivery_threads:
            if delivery_thread.is_alive():
                delivery_thread.join(timeout=2)

        with self._lock:
            self._thread = None
            self._delivery_threads = []
            self._run_id = None
            self._seed = None
            self._status = SimulationStatus.IDLE
            self._started_at = None
            self._started_monotonic = None
            self._completed_at = None
            self._journeys = ()
            self._bookings = {}
            self._events = []
            self._plan = ()
            self._processed_planned_events = 0
            self._scores = {}
            self._rescue_actions = []
            self._ai_logs = []
            self._attention_cases = []
            self._human_owned_booking_ids = set()
            self._held_triggers = set()
            return self._snapshot_locked()

    def snapshot(self) -> SimulationSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def set_autopilot(self, enabled: bool) -> SimulationSnapshot:
        with self._lock:
            self._autopilot_enabled = enabled
            if enabled:
                for booking_id in self._bookings:
                    self._evaluate_booking(booking_id)
            return self._snapshot_locked()

    def ai_logs(self) -> tuple[AIAgentLog, ...]:
        with self._lock:
            return tuple(reversed(self._ai_logs))

    def attention_cases(self) -> tuple[AttentionCase, ...]:
        with self._lock:
            return tuple(
                case
                for case in reversed(self._attention_cases)
                if case.status is not AttentionStatus.RESOLVED
            )

    def approve_attention_case(self, case_id: str) -> AttentionCase:
        with self._lock:
            case_index = self._attention_case_index(case_id)
            case = self._attention_cases[case_index]
            if case.status is not AttentionStatus.AWAITING_APPROVAL:
                raise AttentionActionDeniedError(
                    "Attention case is not awaiting AI follow-up approval."
                )
            if not case.high_value or not case.drafted_response:
                raise AttentionActionDeniedError(
                    "Attention case has no approvable high-value follow-up draft."
                )
            if case.booking_id in self._human_owned_booking_ids:
                raise AttentionActionDeniedError(
                    "Human Rescue owns this booking and blocks AI messaging."
                )

            booking = self._bookings.get(case.booking_id)
            score = self._scores.get(case.booking_id)
            if booking is None or score is None:
                raise AttentionActionDeniedError(
                    "Booking is unavailable for follow-up validation."
                )
            if booking.status in {
                BookingStatus.CANCELED,
                BookingStatus.COMPLETED,
                BookingStatus.LOST,
            }:
                raise AttentionActionDeniedError(
                    "Booking is no longer eligible for rescue follow-up."
                )
            recipient, target_id = self._recipient_and_target(booking, score)
            if (
                recipient is None
                or target_id is None
                or score.target is None
                or score.recommended_intervention is None
                or recipient.opted_out
                or not recipient.phone_demo_id
            ):
                raise AttentionActionDeniedError(
                    "Current recipient or intervention context failed validation."
                )
            follow_up_context = self._follow_up_context(
                booking,
                score,
                first_message=self._first_message_for(case.booking_id),
                latest_reply=case.latest_reply,
            )
            validated_message = validate_message(
                case.drafted_response,
                follow_up_context,
            )
            if validated_message is None:
                raise AttentionActionDeniedError(
                    "Drafted response failed current server-side message validation."
                )

            sent_at = datetime.now(timezone.utc)
            action = RescueAction(
                id=f"action_{uuid4().hex[:12]}",
                booking_id=booking.id,
                score_at_trigger=score.score,
                intervention_type=score.recommended_intervention,
                target_type=score.target,
                target_id=target_id,
                reason_summary="Human-approved high-value rescue follow-up.",
                message_text=validated_message,
                message_source=MessageSource.OPENAI,
                status=RescueActionStatus.SENT,
                sent_at=sent_at,
                outcome=RescueOutcome.STILL_AT_RISK,
            )
            self._rescue_actions.append(action)
            self._record_approved_follow_up_events(action, score, recipient.name)
            resolved = case.model_copy(
                update={
                    "status": AttentionStatus.RESOLVED,
                    "human_decision": HumanDecision.APPROVE_AI,
                    "resolved_at": sent_at,
                }
            )
            self._attention_cases[case_index] = resolved
            self.record_ai_log(
                action_type=AIActionType.HUMAN_APPROVED,
                reason_summary="Operator approved the validated high-value AI follow-up.",
                result="sent",
                booking_id=booking.id,
                tool_name="approve_ai_followup",
                metadata={"attention_case_id": case.id, "action_id": action.id},
            )
            return resolved

    def human_rescue_attention_case(self, case_id: str) -> AttentionCase:
        with self._lock:
            case_index = self._attention_case_index(case_id)
            case = self._attention_cases[case_index]
            if case.status is AttentionStatus.RESOLVED:
                raise AttentionActionDeniedError("Attention case is already resolved.")
            self._human_owned_booking_ids.add(case.booking_id)
            human_owned = case.model_copy(
                update={
                    "status": AttentionStatus.HUMAN_HANDLING,
                    "human_decision": HumanDecision.HUMAN_RESCUE,
                }
            )
            self._attention_cases[case_index] = human_owned
            self.record_ai_log(
                action_type=AIActionType.HUMAN_TAKEOVER,
                reason_summary="Operator selected Human Rescue; AI sends are blocked.",
                result="human_handling",
                booking_id=case.booking_id,
                tool_name="human_rescue",
                metadata={"attention_case_id": case.id},
            )
            return human_owned

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
    ) -> AIAgentLog:
        with self._lock:
            entry = AIAgentLog(
                id=f"ai_log_{uuid4().hex[:12]}",
                timestamp=datetime.now(timezone.utc),
                booking_id=booking_id,
                action_type=action_type,
                reason_summary=reason_summary,
                tool_name=tool_name,
                tool_arguments_summary=tool_arguments_summary,
                result=result,
                metadata=metadata or {},
            )
            self._ai_logs.append(entry)
            return entry

    def dispatch_ai_tool(
        self,
        tool_name: str,
        arguments: dict[str, object] | None = None,
    ) -> AIToolDispatchResult:
        return self._ai_tools.dispatch(tool_name, arguments)

    def send_ai_rescue_sms(
        self,
        *,
        booking_id: str,
        intervention_type: InterventionType,
        message: str,
    ) -> RescueAction:
        with self._lock:
            booking = self._bookings.get(booking_id)
            score = self._scores.get(booking_id)
            if booking is None or score is None:
                raise AIToolDeniedError(
                    "Booking does not exist in the current marketplace."
                )
            if booking_id in self._human_owned_booking_ids:
                raise AIToolDeniedError(
                    "Human Rescue owns this booking and blocks AI messaging."
                )
            prior_sent_actions = [
                action
                for action in self._rescue_actions
                if action.booking_id == booking_id
                and action.status is RescueActionStatus.SENT
            ]
            if is_high_value(booking) and prior_sent_actions:
                raise AIToolDeniedError(
                    "High-value follow-up requires explicit Approve AI review."
                )
            active_attention = self._active_attention_case_for(booking_id)
            if active_attention is not None:
                raise AIToolDeniedError(
                    "Booking requires attention-case review before AI messaging."
                )
            recipient, target_id = self._recipient_and_target(booking, score)
            decision = self._rescue_decision(
                booking,
                score,
                recipient,
                target_id,
            )
            if not decision.should_create_action:
                raise AIToolDeniedError(decision.explanation)
            if intervention_type is not score.recommended_intervention:
                raise AIToolDeniedError(
                    "Requested intervention is outside the deterministic allowed action set."
                )
            context = self._message_context(booking, score)
            validated_message = validate_message(message, context)
            if validated_message is None:
                raise AIToolDeniedError(
                    "Requested message failed backend rescue-message validation."
                )
            return self._create_rescue_action(
                booking,
                score,
                recipient,
                target_id,
                generation=MessageGenerationResult(
                    message_text=validated_message,
                    message_source=MessageSource.OPENAI,
                ),
                log_request=False,
            )

    def record_operator_escalation(
        self,
        *,
        booking_id: str,
        reason: str,
    ) -> dict[str, object]:
        with self._lock:
            if booking_id not in self._bookings:
                raise AIToolDeniedError(
                    "Booking does not exist in the current marketplace."
                )
            concise_reason = " ".join(reason.split())
            if not concise_reason:
                raise AIToolDeniedError("Escalation reason is required.")
            case = self._create_attention_case(
                booking_id=booking_id,
                reason=concise_reason,
                status=AttentionStatus.NEEDS_ATTENTION,
                latest_reply=None,
                drafted_response=None,
                ai_recommendation="Human review is required before outreach continues.",
            )
            return {
                "booking_id": booking_id,
                "status": "escalated",
                "reason": concise_reason[:280],
                "attention_case_id": case.id,
            }

    def _attention_case_index(self, case_id: str) -> int:
        index = next(
            (
                index
                for index, case in enumerate(self._attention_cases)
                if case.id == case_id
            ),
            None,
        )
        if index is None:
            raise AttentionCaseNotFoundError("Attention case was not found.")
        return index

    def _active_attention_case_for(self, booking_id: str) -> AttentionCase | None:
        return next(
            (
                case
                for case in reversed(self._attention_cases)
                if case.booking_id == booking_id
                and case.status is not AttentionStatus.RESOLVED
            ),
            None,
        )

    def _create_attention_case(
        self,
        *,
        booking_id: str,
        reason: str,
        status: AttentionStatus,
        latest_reply: str | None,
        drafted_response: str | None,
        ai_recommendation: str,
    ) -> AttentionCase:
        booking = self._bookings[booking_id]
        existing_index = next(
            (
                index
                for index, case in enumerate(self._attention_cases)
                if case.booking_id == booking_id
                and case.status is not AttentionStatus.RESOLVED
            ),
            None,
        )
        first_action = next(
            (
                action
                for action in self._rescue_actions
                if action.booking_id == booking_id
            ),
            None,
        )
        now = datetime.now(timezone.utc)
        if existing_index is None:
            case = AttentionCase(
                id=f"attention_{uuid4().hex[:12]}",
                booking_id=booking_id,
                reason=reason[:280],
                priority="urgent" if is_high_value(booking) else "high",
                high_value=is_high_value(booking),
                status=status,
                created_at=now,
                first_sms_action_id=first_action.id if first_action else None,
                latest_reply=latest_reply,
                drafted_response=drafted_response,
                ai_recommendation=ai_recommendation[:280],
            )
            self._attention_cases.append(case)
            return case

        existing = self._attention_cases[existing_index]
        updated = existing.model_copy(
            update={
                "reason": reason[:280],
                "priority": "urgent" if is_high_value(booking) else "high",
                "high_value": is_high_value(booking),
                "status": status,
                "first_sms_action_id": (
                    existing.first_sms_action_id
                    or (first_action.id if first_action else None)
                ),
                "latest_reply": latest_reply,
                "drafted_response": drafted_response,
                "ai_recommendation": ai_recommendation[:280],
            }
        )
        self._attention_cases[existing_index] = updated
        return updated

    def _run(self, run_id: str, cancel: threading.Event) -> None:
        with self._lock:
            started_monotonic = self._started_monotonic
            plan = self._plan

        if started_monotonic is None:
            return

        for planned_event in plan:
            remaining = planned_event.offset_seconds - (time.monotonic() - started_monotonic)
            if cancel.wait(max(0, remaining)):
                return
            self._apply_event(run_id, planned_event)

        remaining = self.duration_seconds - (time.monotonic() - started_monotonic)
        if cancel.wait(max(0, remaining)):
            return

        with self._lock:
            delivery_threads = tuple(self._delivery_threads)
        for delivery_thread in delivery_threads:
            if delivery_thread.is_alive():
                delivery_thread.join(timeout=max(0.05, self._scaled_delay(5)))

        with self._lock:
            if self._run_id == run_id and self._status is SimulationStatus.RUNNING:
                self._status = SimulationStatus.COMPLETED
                self._completed_at = datetime.now(timezone.utc)

    def _apply_event(self, run_id: str, planned_event: _PlannedEvent) -> None:
        with self._lock:
            if self._run_id != run_id or self._status is not SimulationStatus.RUNNING:
                return

            booking = self._bookings[planned_event.booking_id]
            next_status = planned_event.step.next_status
            allowed = _ALLOWED_TRANSITIONS[booking.status]
            if next_status not in allowed:
                if booking.status in {
                    BookingStatus.RESCUED,
                    BookingStatus.COMPLETED,
                    BookingStatus.LOST,
                }:
                    self._processed_planned_events += 1
                    return
                raise RuntimeError(
                    f"invalid simulation transition: {booking.status} -> {next_status}"
                )

            event_time = datetime.now(timezone.utc)
            self._bookings[booking.id] = booking.model_copy(
                update={
                    "status": next_status,
                    "last_activity_at": event_time,
                    **(
                        {"at_risk_at": event_time}
                        if next_status is BookingStatus.AT_RISK
                        and booking.at_risk_at is None
                        else {}
                    ),
                }
            )
            self._events.append(
                Event(
                    id=f"event_{uuid4().hex[:12]}",
                    booking_id=booking.id,
                    event_type=planned_event.step.event_type,
                    timestamp=event_time,
                    metadata={
                        "description": planned_event.step.description,
                        "scenario": planned_event.scenario.value,
                        "previous_status": booking.status.value,
                        "new_status": next_status.value,
                        **planned_event.step.metadata,
                    },
                )
            )
            self._processed_planned_events += 1
            self._refresh_score(booking.id, record_event=True)
            self._evaluate_booking(booking.id)

    def _refresh_score(self, booking_id: str, *, record_event: bool) -> None:
        booking = self._bookings[booking_id]
        lister = next(lister for lister in LISTERS if lister.id == booking.lister_id)
        booking_events = [
            event for event in self._events if event.booking_id == booking_id
        ]
        previous_score = self._scores.get(booking_id)
        score = calculate_rescue_score(booking, booking_events, lister)
        self._scores[booking_id] = score
        self._bookings[booking_id] = booking.model_copy(
            update={
                "rescue_score": score.score,
                "risk_level": score.risk_level.value,
                "rescue_target": score.target,
            }
        )

        if record_event and (
            previous_score is None or previous_score.score != score.score
        ):
            self._events.append(
                Event(
                    id=f"event_{uuid4().hex[:12]}",
                    booking_id=booking_id,
                    event_type=EventType.RESCUE_SCORE_CHANGED,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "previous_score": previous_score.score if previous_score else 0,
                        "new_score": score.score,
                        "raw_score": score.raw_score,
                        "risk_level": score.risk_level.value,
                        "target": score.target.value if score.target else None,
                        "reasons": [
                            reason.model_dump(mode="json") for reason in score.reasons
                        ],
                        "explanation": score.explanation,
                    },
                )
            )

    def _evaluate_booking(self, booking_id: str) -> None:
        if (
            booking_id in self._human_owned_booking_ids
            or self._active_attention_case_for(booking_id) is not None
        ):
            return
        booking = self._bookings[booking_id]
        score = self._scores[booking_id]
        recipient, target_id = self._recipient_and_target(booking, score)
        decision = self._rescue_decision(booking, score, recipient, target_id)
        if decision.should_create_action:
            self.record_ai_log(
                action_type=AIActionType.CASE_REVIEWED,
                reason_summary="Rescue-eligible booking passed deterministic policy review.",
                result="eligible",
                booking_id=booking_id,
                metadata={"score": score.score},
            )
            self.record_ai_log(
                action_type=AIActionType.INTERVENTION_SELECTED,
                reason_summary="Selected the backend-approved deterministic intervention.",
                result="selected",
                booking_id=booking_id,
                metadata={
                    "intervention": score.recommended_intervention.value,
                    "target": score.target.value,
                },
            )
            self._create_rescue_action(booking, score, recipient, target_id)
            return

        if (
            decision.blocked_by is GuardrailCode.AUTOPILOT_OFF
            and score.trigger_code
        ):
            held_key = (booking_id, score.trigger_code)
            if held_key not in self._held_triggers:
                self._held_triggers.add(held_key)
                self._events.append(
                    Event(
                        id=f"event_{uuid4().hex[:12]}",
                        booking_id=booking_id,
                        event_type=EventType.AUTOPILOT_ACTION_HELD,
                        timestamp=datetime.now(timezone.utc),
                        metadata={
                            "score": score.score,
                            "intervention": score.recommended_intervention.value,
                            "reason": decision.explanation,
                        },
                    )
                )

    def _recipient_and_target(
        self,
        booking: Booking,
        score: RescueScore,
    ) -> tuple[Renter | Lister | None, str | None]:
        if score.target is RescueTarget.RENTER:
            return (
                next(renter for renter in RENTERS if renter.id == booking.renter_id),
                booking.renter_id,
            )
        if score.target is RescueTarget.LISTER:
            return (
                next(lister for lister in LISTERS if lister.id == booking.lister_id),
                booking.lister_id,
            )
        return None, None

    def _rescue_decision(
        self,
        booking: Booking,
        score: RescueScore,
        recipient: Renter | Lister | None,
        target_id: str | None,
    ) -> RescueRuleDecision:
        return evaluate_rescue_rules(
            booking=booking,
            score=score,
            autopilot_enabled=self._autopilot_enabled,
            target_id=target_id,
            recipient_phone_available=bool(
                recipient and getattr(recipient, "phone_demo_id", None)
            ),
            recipient_opted_out=bool(recipient and recipient.opted_out),
            existing_actions=self._rescue_actions,
        )

    def _message_context(
        self,
        booking: Booking,
        score: RescueScore,
    ) -> RescueMessageContext:
        renter = next(renter for renter in RENTERS if renter.id == booking.renter_id)
        lister = next(lister for lister in LISTERS if lister.id == booking.lister_id)
        listing = next(listing for listing in LISTINGS if listing.id == booking.listing_id)
        return build_rescue_message_context(
            booking=booking,
            score=score,
            renter=renter,
            lister=lister,
            listing=listing,
            events=[event for event in self._events if event.booking_id == booking.id],
        )

    def _follow_up_context(
        self,
        booking: Booking,
        score: RescueScore,
        *,
        first_message: str | None,
        latest_reply: str | None,
    ) -> RescueMessageContext:
        return self._message_context(booking, score).model_copy(
            update={
                "problem": (
                    "high_value_reply_follow_up"
                    if latest_reply
                    else "high_value_no_response_follow_up"
                ),
                "is_follow_up": True,
                "prior_message": first_message,
                "latest_reply": latest_reply,
            }
        )

    def _first_message_for(self, booking_id: str) -> str | None:
        first_action = next(
            (
                action
                for action in self._rescue_actions
                if action.booking_id == booking_id and action.message_text
            ),
            None,
        )
        return first_action.message_text if first_action else None

    def _create_high_value_follow_up_attention(
        self,
        *,
        action: RescueAction,
        booking: Booking,
        plan: _ResponsePlan,
    ) -> AttentionCase:
        score = self._scores[booking.id]
        follow_up_context = self._follow_up_context(
            booking,
            score,
            first_message=action.message_text,
            latest_reply=plan.response_text,
        )
        generation = self.messaging_service.generate(follow_up_context)
        drafted_response = (
            generation.message_text if generation.failure_code is None else None
        )
        reason = (
            "High-value recipient replied; follow-up requires human approval."
            if plan.should_respond
            else "High-value outreach received no reply; follow-up requires human approval."
        )
        case = self._create_attention_case(
            booking_id=booking.id,
            reason=reason,
            status=(
                AttentionStatus.AWAITING_APPROVAL
                if drafted_response
                else AttentionStatus.NEEDS_ATTENTION
            ),
            latest_reply=plan.response_text,
            drafted_response=drafted_response,
            ai_recommendation=(
                "Review the drafted follow-up and choose Approve AI or Human Rescue."
                if drafted_response
                else "AI drafting was unavailable; choose Human Rescue."
            ),
        )
        self.record_ai_log(
            action_type=AIActionType.HIGH_VALUE_FLAGGED,
            reason_summary=reason,
            result=case.status.value,
            booking_id=booking.id,
            metadata={
                "attention_case_id": case.id,
                "booking_value": booking.booking_value,
            },
        )
        if drafted_response:
            self.record_ai_log(
                action_type=AIActionType.FOLLOWUP_DRAFTED,
                reason_summary="Drafted a high-value follow-up for human review.",
                result="awaiting_approval",
                booking_id=booking.id,
                metadata={"attention_case_id": case.id},
            )
        return case

    def _record_approved_follow_up_events(
        self,
        action: RescueAction,
        score: RescueScore,
        recipient_name: str,
    ) -> None:
        timestamp = action.sent_at or datetime.now(timezone.utc)
        shared_metadata = {
            "action_id": action.id,
            "intervention": action.intervention_type.value,
            "target": action.target_type.value,
        }
        self._events.extend(
            (
                Event(
                    id=f"event_{uuid4().hex[:12]}",
                    booking_id=action.booking_id,
                    event_type=EventType.RESCUE_TRIGGERED,
                    timestamp=timestamp,
                    metadata={
                        **shared_metadata,
                        "score": score.score,
                        "explanation": action.reason_summary,
                        "trigger_code": "human_approved_high_value_follow_up",
                        "score_reasons": [
                            reason.model_dump(mode="json") for reason in score.reasons
                        ],
                        "status": RescueActionStatus.SENT.value,
                    },
                ),
                Event(
                    id=f"event_{uuid4().hex[:12]}",
                    booking_id=action.booking_id,
                    event_type=EventType.SMS_GENERATED,
                    timestamp=timestamp,
                    metadata={
                        **shared_metadata,
                        "message_source": MessageSource.OPENAI.value,
                        "generation_failure": None,
                        "status": RescueActionStatus.GENERATED.value,
                    },
                ),
                Event(
                    id=f"event_{uuid4().hex[:12]}",
                    booking_id=action.booking_id,
                    event_type=EventType.SMS_SENT,
                    timestamp=timestamp,
                    metadata={
                        **shared_metadata,
                        "recipient_name": recipient_name,
                        "demo_mode": True,
                        "human_approved": True,
                    },
                ),
            )
        )

    def _create_rescue_action(
        self,
        booking: Booking,
        score: RescueScore,
        recipient: Renter | Lister | None,
        target_id: str | None,
        *,
        generation: MessageGenerationResult | None = None,
        log_request: bool = True,
    ) -> RescueAction:
        if (
            recipient is None
            or target_id is None
            or score.target is None
            or score.recommended_intervention is None
        ):
            raise AIToolDeniedError("Required rescue context is missing.")

        triggered_at = datetime.now(timezone.utc)
        if booking.at_risk_at is None:
            booking = booking.model_copy(update={"at_risk_at": triggered_at})
            self._bookings[booking.id] = booking
        action = RescueAction(
            id=f"action_{uuid4().hex[:12]}",
            booking_id=booking.id,
            score_at_trigger=score.score,
            intervention_type=score.recommended_intervention,
            target_type=score.target,
            target_id=target_id,
            reason_summary=score.explanation,
            status=RescueActionStatus.PENDING,
        )
        self._rescue_actions.append(action)
        self._events.append(
            Event(
                id=f"event_{uuid4().hex[:12]}",
                booking_id=booking.id,
                event_type=EventType.RESCUE_TRIGGERED,
                timestamp=triggered_at,
                metadata={
                    "action_id": action.id,
                    "score": score.score,
                    "target": score.target.value,
                    "intervention": score.recommended_intervention.value,
                    "explanation": score.explanation,
                    "trigger_code": score.trigger_code,
                    "score_reasons": [
                        reason.model_dump(mode="json") for reason in score.reasons
                    ],
                    "status": RescueActionStatus.PENDING.value,
                },
            )
        )
        generation = generation or self.messaging_service.generate(
            self._message_context(booking, score)
        )
        generated_action = action.model_copy(
            update={
                "message_text": generation.message_text,
                "message_source": generation.message_source,
                "status": RescueActionStatus.GENERATED,
            }
        )
        self._rescue_actions[-1] = generated_action
        self._events.append(
            Event(
                id=f"event_{uuid4().hex[:12]}",
                booking_id=booking.id,
                event_type=EventType.SMS_GENERATED,
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "action_id": generated_action.id,
                    "intervention": generated_action.intervention_type.value,
                    "target": generated_action.target_type.value,
                    "message_source": generation.message_source.value,
                    "generation_failure": (
                        generation.failure_code.value
                        if generation.failure_code
                        else None
                    ),
                    "status": RescueActionStatus.GENERATED.value,
                },
            )
        )
        if log_request:
            self.record_ai_log(
                action_type=AIActionType.SMS_REQUESTED,
                reason_summary="Rescue SMS requested through the approved backend tool.",
                result=generation.message_source.value,
                booking_id=booking.id,
                tool_name="send_rescue_sms",
                tool_arguments_summary=(
                    f"booking_id={booking.id}; "
                    f"intervention_type={generated_action.intervention_type.value}"
                ),
                metadata={"action_id": generated_action.id},
            )
        response_plan = self._plan_response(generated_action, recipient)
        delivery_thread = threading.Thread(
            target=self._deliver_action,
            args=(
                self._run_id,
                generated_action.id,
                recipient.name,
                response_plan,
                self._cancel,
            ),
            name=f"delivery-{generated_action.id}",
            daemon=True,
        )
        self._delivery_threads.append(delivery_thread)
        delivery_thread.start()
        return generated_action

    def _plan_response(
        self,
        action: RescueAction,
        recipient: Renter | Lister,
    ) -> _ResponsePlan:
        successful = self._planned_action_count == 0
        self._planned_action_count += 1

        if successful:
            return _ResponsePlan(
                should_respond=True,
                successful=True,
                response_text=self._positive_response(recipient),
                outcome=RescueOutcome.RESCUED,
            )

        if action.target_type is RescueTarget.RENTER:
            return _ResponsePlan(
                should_respond=False,
                successful=False,
                response_text=None,
                outcome=RescueOutcome.NO_RESPONSE,
            )

        should_respond = self._response_rng.random() < recipient.sms_response_rate
        return _ResponsePlan(
            should_respond=should_respond,
            successful=False,
            response_text=(
                self._negative_lister_response(recipient)
                if should_respond and isinstance(recipient, Lister)
                else None
            ),
            outcome=(
                RescueOutcome.LOST if should_respond else RescueOutcome.NO_RESPONSE
            ),
        )

    def _positive_response(self, recipient: Renter | Lister) -> str:
        if isinstance(recipient, Renter) and recipient.successful_sms_response:
            return recipient.successful_sms_response
        if isinstance(recipient, Lister) and recipient.representative_sms_response:
            response = recipient.representative_sms_response
            if not _looks_negative(response):
                return response
        options = (
            ("Yes, those dates are available.", "Those dates work.")
            if isinstance(recipient, Lister)
            else (
                "Yes, I'm still interested.",
                "Got it — I'll finish the booking now.",
            )
        )
        return self._response_rng.choice(options)

    def _negative_lister_response(self, recipient: Lister) -> str:
        if recipient.representative_sms_response and _looks_negative(
            recipient.representative_sms_response
        ):
            return recipient.representative_sms_response
        return self._response_rng.choice(
            (
                "Sorry, those dates won't work.",
                "The space isn't available anymore.",
                "I can't accommodate that move-in date.",
            )
        )

    def _deliver_action(
        self,
        run_id: str | None,
        action_id: str,
        recipient_name: str,
        plan: _ResponsePlan,
        cancel: threading.Event,
    ) -> None:
        if cancel.wait(self._scaled_delay(0.4)):
            return
        with self._lock:
            action_index = self._action_index(run_id, action_id)
            if action_index is None:
                return
            action = self._rescue_actions[action_index]
            sent_at = datetime.now(timezone.utc)
            self._rescue_actions[action_index] = action.model_copy(
                update={"status": RescueActionStatus.SENT, "sent_at": sent_at}
            )
            self._events.append(
                Event(
                    id=f"event_{uuid4().hex[:12]}",
                    booking_id=action.booking_id,
                    event_type=EventType.SMS_SENT,
                    timestamp=sent_at,
                    metadata={
                        "action_id": action.id,
                        "recipient_name": recipient_name,
                        "target": action.target_type.value,
                        "intervention": action.intervention_type.value,
                        "demo_mode": True,
                    },
                )
            )
            self.record_ai_log(
                action_type=AIActionType.SMS_SENT,
                reason_summary="Backend guardrails approved and demo-sent the rescue SMS.",
                result="sent",
                booking_id=action.booking_id,
                tool_name="send_rescue_sms",
                tool_arguments_summary=(
                    f"booking_id={action.booking_id}; "
                    f"intervention_type={action.intervention_type.value}"
                ),
                metadata={"action_id": action.id},
            )

        if cancel.wait(self._scaled_delay(2.5)):
            return
        with self._lock:
            action_index = self._action_index(run_id, action_id)
            if action_index is None:
                return
            action = self._rescue_actions[action_index]
            outcome_at = datetime.now(timezone.utc)
            booking = self._bookings[action.booking_id]
            high_value_follow_up = is_high_value(booking) and not any(
                existing.booking_id == action.booking_id
                and existing.id != action.id
                and existing.status is RescueActionStatus.SENT
                for existing in self._rescue_actions
            )
            self._rescue_actions[action_index] = action.model_copy(
                update={
                    "response_text": plan.response_text,
                    "response_at": outcome_at if plan.should_respond else None,
                    "outcome": (
                        RescueOutcome.STILL_AT_RISK
                        if high_value_follow_up
                        else plan.outcome
                    ),
                }
            )
            if plan.should_respond:
                self._events.append(
                    Event(
                        id=f"event_{uuid4().hex[:12]}",
                        booking_id=action.booking_id,
                        event_type=EventType.SMS_RECEIVED,
                        timestamp=outcome_at,
                        metadata={
                            "action_id": action.id,
                            "recipient_name": recipient_name,
                            "response_text": plan.response_text,
                            "demo_mode": True,
                        },
                    )
                )

            if high_value_follow_up:
                self._create_high_value_follow_up_attention(
                    action=self._rescue_actions[action_index],
                    booking=booking,
                    plan=plan,
                )
                return

            if plan.successful:
                self._bookings[action.booking_id] = booking.model_copy(
                    update={
                        "status": BookingStatus.RESCUED,
                        "rescued_at": outcome_at,
                        "last_activity_at": outcome_at,
                    }
                )
                self._events.append(
                    Event(
                        id=f"event_{uuid4().hex[:12]}",
                        booking_id=action.booking_id,
                        event_type=EventType.BOOKING_RESCUED,
                        timestamp=outcome_at,
                        metadata={
                            "action_id": action.id,
                            "booking_value": booking.booking_value,
                            "outcome": RescueOutcome.RESCUED.value,
                        },
                    )
                )
            else:
                self._bookings[action.booking_id] = booking.model_copy(
                    update={
                        "status": BookingStatus.LOST,
                        "last_activity_at": outcome_at,
                    }
                )
                self._events.append(
                    Event(
                        id=f"event_{uuid4().hex[:12]}",
                        booking_id=action.booking_id,
                        event_type=EventType.RESCUE_FAILED,
                        timestamp=outcome_at,
                        metadata={
                            "action_id": action.id,
                            "outcome": plan.outcome.value,
                            "reason": (
                                "Recipient did not respond"
                                if not plan.should_respond
                                else "Recipient could not continue the booking"
                            ),
                        },
                    )
                )

        if not plan.successful or cancel.wait(self._scaled_delay(0.5)):
            return
        with self._lock:
            action_index = self._action_index(run_id, action_id)
            if action_index is None:
                return
            action = self._rescue_actions[action_index]
            booking = self._bookings[action.booking_id]
            if booking.status is not BookingStatus.RESCUED:
                return
            completed_at = datetime.now(timezone.utc)
            self._bookings[action.booking_id] = booking.model_copy(
                update={
                    "status": BookingStatus.COMPLETED,
                    "completed_at": completed_at,
                    "last_activity_at": completed_at,
                }
            )
            self._events.append(
                Event(
                    id=f"event_{uuid4().hex[:12]}",
                    booking_id=action.booking_id,
                    event_type=EventType.BOOKING_COMPLETED,
                    timestamp=completed_at,
                    metadata={
                        "action_id": action.id,
                        "outcome": RescueOutcome.RESCUED.value,
                        "rescued_booking": True,
                        "booking_value": booking.booking_value,
                    },
                )
            )

    def _action_index(self, run_id: str | None, action_id: str) -> int | None:
        if self._run_id != run_id or self._status is not SimulationStatus.RUNNING:
            return None
        return next(
            (
                index
                for index, action in enumerate(self._rescue_actions)
                if action.id == action_id
            ),
            None,
        )

    def _scaled_delay(self, normal_run_seconds: float) -> float:
        return max(0.001, normal_run_seconds * (self.duration_seconds / 90))

    def _snapshot_locked(self) -> SimulationSnapshot:
        elapsed = self._elapsed_locked()
        progress = min(100.0, (elapsed / self.duration_seconds) * 100)
        return SimulationSnapshot(
            run_id=self._run_id,
            seed=self._seed,
            status=self._status,
            duration_seconds=self.duration_seconds,
            speed_multiplier=self.speed_multiplier,
            autopilot_enabled=self._autopilot_enabled,
            started_at=self._started_at,
            completed_at=self._completed_at,
            elapsed_seconds=round(elapsed, 3),
            progress_percent=round(progress, 1),
            total_planned_events=len(self._plan),
            processed_planned_events=self._processed_planned_events,
            selected_journeys=self._journeys,
            bookings=tuple(self._bookings.values()),
            events=tuple(self._events),
            scores=dict(self._scores),
            rescue_actions=tuple(self._rescue_actions),
            analytics=calculate_analytics(
                tuple(self._bookings.values()), self._rescue_actions
            ),
        )

    def _elapsed_locked(self) -> float:
        if self._started_monotonic is None:
            return 0
        if self._status is SimulationStatus.COMPLETED:
            return self.duration_seconds
        return min(self.duration_seconds, time.monotonic() - self._started_monotonic)

    def _build_journeys(
        self,
        run_id: str,
        started_at: datetime,
        rng: random.Random,
    ) -> tuple[_JourneyPlan, ...]:
        renters = {renter.id: renter for renter in RENTERS}
        listers = {lister.id: lister for lister in LISTERS}
        listings_by_lister: dict[str, list[Listing]] = {}
        for listing in LISTINGS:
            listings_by_lister.setdefault(listing.lister_id, []).append(listing)

        delayed_renter = renters[rng.choice(("renter_maya", "renter_sofia"))]
        delayed_lister_id = rng.choice(("lister_sarah", "lister_andre"))
        delayed_listing = rng.choice(listings_by_lister[delayed_lister_id])

        if rng.choice((True, False)):
            renter_risk = renters[rng.choice(("renter_alex", "renter_marcus"))]
            renter_scenario = ScenarioType.CHECKOUT_ABANDONMENT
        else:
            renter_risk = renters["renter_jordan"]
            renter_scenario = ScenarioType.PAYMENT_FAILURE

        available_listings = [
            listing for listing in LISTINGS if listing.id != delayed_listing.id
        ]
        renter_risk_listing = rng.choice(available_listings)
        healthy_renter = renters["renter_emily"]
        healthy_candidates = [
            listing
            for listing in available_listings
            if listing.id != renter_risk_listing.id
        ]
        healthy_listing = rng.choice(healthy_candidates)

        return (
            self._journey_plan(
                run_id,
                delayed_renter,
                listers[delayed_listing.lister_id],
                delayed_listing,
                ScenarioType.LISTER_DELAY,
                started_at,
                rng,
            ),
            self._journey_plan(
                run_id,
                renter_risk,
                listers[renter_risk_listing.lister_id],
                renter_risk_listing,
                renter_scenario,
                started_at,
                rng,
            ),
            self._journey_plan(
                run_id,
                healthy_renter,
                listers[healthy_listing.lister_id],
                healthy_listing,
                ScenarioType.HEALTHY_COMPLETION,
                started_at,
                rng,
            ),
        )

    def _journey_plan(
        self,
        run_id: str,
        renter: Renter,
        lister: Lister,
        listing: Listing,
        scenario: ScenarioType,
        started_at: datetime,
        rng: random.Random,
    ) -> _JourneyPlan:
        booking_id = f"booking_{run_id[4:]}_{scenario.value}"
        move_in_days = rng.randint(
            renter.move_in_days_range.minimum,
            renter.move_in_days_range.maximum,
        )
        move_in = started_at.date() + timedelta(days=move_in_days)
        booking = Booking(
            id=booking_id,
            renter_id=renter.id,
            lister_id=listing.lister_id,
            listing_id=listing.id,
            move_in=move_in,
            move_out=move_in + timedelta(days=30),
            booking_value=rng.randint(
                renter.booking_value_range.minimum,
                renter.booking_value_range.maximum,
            ),
            status=BookingStatus.BROWSING,
            created_at=started_at,
            last_activity_at=started_at,
        )
        return _JourneyPlan(
            journey=SelectedJourney(
                booking_id=booking_id,
                scenario=scenario,
                renter_id=renter.id,
                lister_id=listing.lister_id,
                listing_id=listing.id,
            ),
            booking=booking,
            steps=self._steps_for(scenario, renter, lister, rng),
        )

    def _steps_for(
        self,
        scenario: ScenarioType,
        renter: Renter,
        lister: Lister,
        rng: random.Random,
    ) -> tuple[_EventStep, ...]:
        view_count = rng.randint(
            renter.views_before_action.minimum,
            renter.views_before_action.maximum,
        )
        view = _EventStep(
            EventType.LISTING_VIEWED,
            BookingStatus.BROWSING,
            "Renter viewed the listing",
            {"view_count": view_count},
        )
        if scenario is ScenarioType.LISTER_DELAY:
            minutes_waiting = max(
                11,
                round(lister.average_response_minutes * rng.uniform(2.2, 4.5)),
            )
            return (
                view,
                _EventStep(EventType.INQUIRY_SENT, BookingStatus.INQUIRY, "Inquiry sent", {}),
                _EventStep(
                    EventType.BOOKING_REQUESTED,
                    BookingStatus.BOOKING_REQUESTED,
                    "Booking request submitted",
                    {},
                ),
                _EventStep(
                    EventType.LISTER_NOTIFIED,
                    BookingStatus.AWAITING_LISTER,
                    "Lister notified of the request",
                    {},
                ),
                _EventStep(
                    EventType.LISTER_RESPONSE_DELAYED,
                    BookingStatus.AT_RISK,
                    "Lister response exceeded the expected window",
                    {
                        "risk_signal": "lister_response_delay",
                        "minutes_waiting": minutes_waiting,
                        "lister_average_response_minutes": (
                            lister.average_response_minutes
                        ),
                        "response_ratio": round(
                            minutes_waiting / lister.average_response_minutes,
                            2,
                        ),
                    },
                ),
            )
        if scenario is ScenarioType.CHECKOUT_ABANDONMENT:
            return (
                view,
                _EventStep(
                    EventType.BOOKING_STARTED,
                    BookingStatus.CHECKOUT_STARTED,
                    "Renter started checkout",
                    {},
                ),
                _EventStep(
                    EventType.CHECKOUT_ABANDONED,
                    BookingStatus.AT_RISK,
                    "Checkout became inactive",
                    {"risk_signal": "checkout_abandonment"},
                ),
            )
        if scenario is ScenarioType.PAYMENT_FAILURE:
            return (
                view,
                _EventStep(
                    EventType.BOOKING_STARTED,
                    BookingStatus.CHECKOUT_STARTED,
                    "Renter started checkout",
                    {},
                ),
                _EventStep(
                    EventType.PAYMENT_FAILED,
                    BookingStatus.PAYMENT_ISSUE,
                    "Payment attempt failed",
                    {"risk_signal": "payment_failure"},
                ),
                _EventStep(
                    EventType.RENTER_INACTIVE,
                    BookingStatus.AT_RISK,
                    "Booking remained inactive after payment failure",
                    {"risk_signal": "payment_failure_unresolved"},
                ),
            )
        return (
            view,
            _EventStep(EventType.INQUIRY_SENT, BookingStatus.INQUIRY, "Inquiry sent", {}),
            _EventStep(
                EventType.BOOKING_REQUESTED,
                BookingStatus.BOOKING_REQUESTED,
                "Booking request submitted",
                {},
            ),
            _EventStep(
                EventType.AVAILABILITY_REQUESTED,
                BookingStatus.AWAITING_AVAILABILITY,
                "Availability requested from lister",
                {},
            ),
            _EventStep(
                EventType.AVAILABILITY_CONFIRMED,
                BookingStatus.CHECKOUT_STARTED,
                "Lister confirmed availability",
                {},
            ),
            _EventStep(
                EventType.BOOKING_COMPLETED,
                BookingStatus.COMPLETED,
                "Healthy booking completed without intervention",
                {"outcome": "healthy_completion"},
            ),
        )

    def _schedule_events(
        self,
        journeys: tuple[_JourneyPlan, ...],
        rng: random.Random,
    ) -> tuple[_PlannedEvent, ...]:
        interleaved: list[tuple[_JourneyPlan, _EventStep]] = []
        longest_journey = max(len(journey.steps) for journey in journeys)
        for step_index in range(longest_journey):
            active = [journey for journey in journeys if step_index < len(journey.steps)]
            rng.shuffle(active)
            interleaved.extend((journey, journey.steps[step_index]) for journey in active)

        weights = [rng.uniform(4, 7) for _ in interleaved]
        # Finish the story with enough time for the reviewer to read the final
        # outcomes before the 90-second run ends.
        target_end = self.duration_seconds * 0.82
        scale = target_end / sum(weights)
        elapsed = 0.0
        planned: list[_PlannedEvent] = []
        for (journey, step), weight in zip(interleaved, weights, strict=True):
            elapsed += weight * scale
            planned.append(
                _PlannedEvent(
                    offset_seconds=elapsed,
                    booking_id=journey.booking.id,
                    scenario=journey.journey.scenario,
                    step=step,
                )
            )
        return tuple(planned)


def _looks_negative(response: str) -> bool:
    lowered = response.casefold()
    return any(
        phrase in lowered
        for phrase in (
            "sorry",
            "won't",
            "isn't",
            "not available",
            "can't",
            "cannot",
        )
    )


SIMULATION_ENGINE = SimulationEngine(
    messaging_service=MessagingService.from_environment()
)
