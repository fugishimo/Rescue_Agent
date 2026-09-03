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
from app.models import Booking, BookingStatus, Event, EventType, Lister, Listing, Renter


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
    started_at: datetime | None
    completed_at: datetime | None
    elapsed_seconds: float = Field(ge=0)
    progress_percent: float = Field(ge=0, le=100)
    total_planned_events: int = Field(ge=0)
    selected_journeys: tuple[SelectedJourney, ...]
    bookings: tuple[Booking, ...]
    events: tuple[Event, ...]


class SimulationStartRequest(BaseModel):
    seed: int | None = None


class SimulationAlreadyRunningError(RuntimeError):
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

    def __init__(self, duration_seconds: float = 90, speed_multiplier: int = 30):
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if speed_multiplier <= 0:
            raise ValueError("speed_multiplier must be positive")

        self.duration_seconds = duration_seconds
        self.speed_multiplier = speed_multiplier
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
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
            cancel = self._cancel
            cancel.set()

        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

        with self._lock:
            self._thread = None
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
            return self._snapshot_locked()

    def snapshot(self) -> SimulationSnapshot:
        with self._lock:
            return self._snapshot_locked()

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
                raise RuntimeError(
                    f"invalid simulation transition: {booking.status} -> {next_status}"
                )

            event_time = datetime.now(timezone.utc)
            self._bookings[booking.id] = booking.model_copy(
                update={"status": next_status, "last_activity_at": event_time}
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

    def _snapshot_locked(self) -> SimulationSnapshot:
        elapsed = self._elapsed_locked()
        progress = min(100.0, (elapsed / self.duration_seconds) * 100)
        return SimulationSnapshot(
            run_id=self._run_id,
            seed=self._seed,
            status=self._status,
            duration_seconds=self.duration_seconds,
            speed_multiplier=self.speed_multiplier,
            started_at=self._started_at,
            completed_at=self._completed_at,
            elapsed_seconds=round(elapsed, 3),
            progress_percent=round(progress, 1),
            total_planned_events=len(self._plan),
            selected_journeys=self._journeys,
            bookings=tuple(self._bookings.values()),
            events=tuple(self._events),
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
        target_end = self.duration_seconds * 0.9
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


SIMULATION_ENGINE = SimulationEngine()
