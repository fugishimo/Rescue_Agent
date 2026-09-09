from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.data.profiles import LISTERS, RENTERS
from app.data.seed_data import LISTINGS
from app.main import app
from app.models import AIActionType, OpsChatToolResult
from app.services.ops_chat import (
    LLMOpsChatPlanner,
    OUT_OF_DOMAIN_RESPONSE,
    OpsEntity,
    OpsChatPlan,
    OpsChatService,
    resolve_entity_reference,
)
from app.services.simulation import SimulationEngine


class SequencePlanner:
    def __init__(self, *plans: OpsChatPlan) -> None:
        self.plans = plans
        self.calls = 0

    def plan(
        self,
        *,
        message: str,
        tool_results: tuple[OpsChatToolResult, ...],
    ) -> OpsChatPlan:
        del message, tool_results
        plan = self.plans[min(self.calls, len(self.plans) - 1)]
        self.calls += 1
        return plan


class FailingPlanner:
    def plan(
        self,
        *,
        message: str,
        tool_results: tuple[OpsChatToolResult, ...],
    ) -> OpsChatPlan:
        del message, tool_results
        raise TimeoutError("provider unavailable")


class StructuredPlanClient:
    def generate_text(
        self,
        *,
        system: str,
        prompt: str,
        output_schema: dict[str, object],
        max_tokens: int,
    ) -> str:
        del system, prompt, output_schema, max_tokens
        return (
            '{"response":"I will pause Autopilot.",'
            '"tool_name":"set_autopilot",'
            '"arguments_json":"{\\"enabled\\": false}"}'
        )


def test_provider_neutral_planner_parses_structured_tool_request() -> None:
    planner = LLMOpsChatPlanner(StructuredPlanClient())

    plan = planner.plan(message="Pause Autopilot.", tool_results=())

    assert plan.tool_name == "set_autopilot"
    assert plan.arguments == {"enabled": False}


def _completed_engine(seed: int) -> SimulationEngine:
    engine = SimulationEngine(duration_seconds=0.15)
    engine.start(seed=seed)
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if engine.snapshot().status.value == "completed":
            return engine
        time.sleep(0.005)
    raise AssertionError("accelerated simulation did not complete")


def test_chat_uses_planned_approved_tool_and_returns_result() -> None:
    planner = SequencePlanner(
        OpsChatPlan(
            response="I’ll inspect high-value bookings.",
            tool_name="get_high_value_cases",
        ),
        OpsChatPlan(response="The high-value review is complete."),
    )
    engine = SimulationEngine(
        duration_seconds=90,
        ops_chat_service=OpsChatService(planner),
    )
    engine.start(seed=0)

    response = engine.ops_chat("Show me all high-value cases.")

    assert response.message.content == "The high-value review is complete."
    assert response.message.tool_calls[0].tool_name == "get_high_value_cases"
    assert response.message.tool_calls[0].result == "success"
    assert planner.calls == 2
    assert any(
        log.action_type is AIActionType.CHAT_TOOL_CALLED
        and log.tool_name == "get_high_value_cases"
        for log in engine.ai_logs()
    )
    engine.reset()


def test_out_of_domain_chat_is_restricted_without_tools() -> None:
    engine = SimulationEngine(duration_seconds=90)
    before = engine.snapshot()

    response = engine.ops_chat("Write me a poem about the ocean.")
    after = engine.snapshot()

    assert response.message.content == OUT_OF_DOMAIN_RESPONSE
    assert response.message.tool_calls == ()
    assert after.autopilot_enabled == before.autopilot_enabled
    assert after.bookings == before.bookings
    assert engine.ai_logs() == ()


def test_pause_and_resume_autopilot_use_validated_backend_tool() -> None:
    engine = SimulationEngine(duration_seconds=90)

    paused = engine.ops_chat("Pause Autopilot.")
    resumed = engine.ops_chat("Resume Autopilot.")

    assert paused.message.content == "Autopilot is now OFF."
    assert paused.message.tool_calls[0].tool_name == "set_autopilot"
    assert resumed.message.content == "Autopilot is now ON."
    assert engine.snapshot().autopilot_enabled is True
    assert sum(
        log.action_type is AIActionType.AUTOPILOT_CHANGED
        for log in engine.ai_logs()
    ) == 2


def test_chat_cannot_call_unregistered_score_or_outcome_tools() -> None:
    planner = SequencePlanner(
        OpsChatPlan(
            response="Attempting an unsupported change.",
            tool_name="change_rescue_score",
            arguments={"score": 0},
        )
    )
    engine = SimulationEngine(
        duration_seconds=90,
        ops_chat_service=OpsChatService(planner),
    )
    started = engine.start(seed=42)
    scores_before = {
        booking_id: score.model_dump(mode="json")
        for booking_id, score in started.scores.items()
    }
    statuses_before = {booking.id: booking.status for booking in started.bookings}

    response = engine.ops_chat("Change this booking rescue score.")
    after = engine.snapshot()

    assert response.message.tool_calls[0].result == "denied"
    assert {
        booking_id: score.model_dump(mode="json")
        for booking_id, score in after.scores.items()
    } == scores_before
    assert {booking.id: booking.status for booking in after.bookings} == statuses_before
    assert engine.ai_logs()[0].action_type is AIActionType.ACTION_DENIED
    engine.reset()


def test_provider_failure_falls_back_to_safe_supported_read() -> None:
    engine = SimulationEngine(
        duration_seconds=90,
        ops_chat_service=OpsChatService(FailingPlanner()),
    )
    engine.start(seed=0)

    response = engine.ops_chat("What needs my attention right now?")

    assert response.message.tool_calls[0].tool_name == "get_attention_cases"
    assert response.message.tool_calls[0].result == "success"
    assert "attention cases" in response.message.content
    engine.reset()


def test_fallback_answers_run_history_and_contact_reason_from_backend_actions() -> None:
    engine = _completed_engine(42)
    action = engine.snapshot().rescue_actions[0]
    participant = next(
        item
        for item in engine.dispatch_ai_tool("get_recent_rescue_actions").data
        if item["id"] == action.id
    )

    history = engine.ops_chat("What did you do during this run?")
    reason = engine.ops_chat(f"Why did you contact {participant['target_name']}?")

    assert history.message.tool_calls[0].tool_name == "get_recent_rescue_actions"
    assert participant["target_name"] in reason.message.content
    assert action.reason_summary in reason.message.content
    engine.reset()


def test_named_renter_question_uses_current_renter_history_and_exact_action() -> None:
    engine = _completed_engine(0)
    jordan = next(renter for renter in RENTERS if renter.name == "Jordan Patel")
    action = next(
        action
        for action in engine.snapshot().rescue_actions
        if action.target_id == jordan.id
    )

    response = engine.ops_chat("why did you contact jordan")

    assert response.message.tool_calls[0].tool_name == "get_renter_history"
    assert "Jordan Patel" in response.message.content
    assert str(action.score_at_trigger) in response.message.content
    assert action.reason_summary in response.message.content
    assert action.intervention_type.value.replace("_", " ") in response.message.content
    assert engine.ai_logs()[0].tool_name == "get_renter_history"
    assert f"renter_id={jordan.id}" == engine.ai_logs()[0].tool_arguments_summary
    engine.reset()


def test_named_lister_question_uses_current_lister_history_and_exact_action() -> None:
    engine = _completed_engine(0)
    andre = next(lister for lister in LISTERS if lister.name == "Andre Williams")
    action = next(
        action
        for action in engine.snapshot().rescue_actions
        if action.target_id == andre.id
    )

    response = engine.ops_chat("why did you contact andre")

    assert response.message.tool_calls[0].tool_name == "get_lister_history"
    assert "Andre Williams" in response.message.content
    assert str(action.score_at_trigger) in response.message.content
    assert action.reason_summary in response.message.content
    assert engine.ai_logs()[0].tool_name == "get_lister_history"
    assert f"lister_id={andre.id}" == engine.ai_logs()[0].tool_arguments_summary
    engine.reset()


def test_named_entity_without_action_is_not_replaced_by_recent_action() -> None:
    engine = _completed_engine(0)

    response = engine.ops_chat("what happened with emily")

    assert response.message.tool_calls[0].tool_name == "get_renter_history"
    assert response.message.content.startswith(
        "Emily Nguyen has not had a rescue intervention in the current run."
    )
    assert "Jordan Patel" not in response.message.content
    assert "Andre Williams" not in response.message.content
    engine.reset()


def test_nonexistent_entity_is_reported_without_tool_substitution() -> None:
    engine = _completed_engine(0)
    log_count = len(engine.ai_logs())

    response = engine.ops_chat("why did you contact Morgan")

    assert response.message.content == (
        "Morgan is not part of the current simulation run."
    )
    assert response.message.tool_calls == ()
    assert len(engine.ai_logs()) == log_count
    engine.reset()


def test_ambiguous_entity_requests_clarification_without_guessing() -> None:
    entities = (
        OpsEntity(kind="renter", id="renter_one", name="Alex Kim", booking_ids=("b1",)),
        OpsEntity(kind="lister", id="lister_one", name="Alex Rivera", booking_ids=("b2",)),
    )
    resolution = resolve_entity_reference("what happened with alex", entities)

    assert resolution.status == "ambiguous"
    assert {candidate.id for candidate in resolution.candidates} == {
        "renter_one",
        "lister_one",
    }
    turn = OpsChatService().respond(
        "what happened with alex",
        lambda name, arguments: (_ for _ in ()).throw(
            AssertionError(f"unexpected dispatch: {name} {arguments}")
        ),
        entities,
    )
    assert "matches multiple" in turn.content
    assert "Alex Kim (renter)" in turn.content
    assert "Alex Rivera (lister)" in turn.content
    assert turn.tool_results == ()


def test_entity_grounding_overrides_broad_provider_tool_selection() -> None:
    planner = SequencePlanner(
        OpsChatPlan(
            response="I will inspect recent actions.",
            tool_name="get_recent_rescue_actions",
        )
    )
    engine = SimulationEngine(
        duration_seconds=0.15,
        ops_chat_service=OpsChatService(planner),
    )
    engine.start(seed=0)
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        if engine.snapshot().status.value == "completed":
            break
        time.sleep(0.005)

    response = engine.ops_chat("why did you contact jordan")

    assert response.message.tool_calls[0].tool_name == "get_renter_history"
    assert planner.calls == 0
    engine.reset()


def test_exact_booking_and_listing_queries_use_booking_details() -> None:
    engine = _completed_engine(0)
    snapshot = engine.snapshot()
    booking = next(
        booking
        for booking in snapshot.bookings
        if booking.listing_id == "listing_astoria_apartment"
    )
    listing = next(item for item in LISTINGS if item.id == booking.listing_id)

    booking_response = engine.ops_chat(f"Tell me about {booking.id}")
    listing_response = engine.ops_chat(f"Tell me about the {listing.name} booking")

    assert booking_response.message.tool_calls[0].tool_name == "get_booking_details"
    assert listing_response.message.tool_calls[0].tool_name == "get_booking_details"
    assert listing.name in listing_response.message.content
    assert booking.status.value.replace("_", " ") in listing_response.message.content
    engine.reset()


def test_broad_queries_keep_using_broad_approved_tools() -> None:
    engine = _completed_engine(0)
    expectations = {
        "what did you do during this run?": "get_recent_rescue_actions",
        "what needs my attention?": "get_attention_cases",
        "show me high-value cases": "get_high_value_cases",
        "which booking is most at risk?": "get_at_risk_bookings",
    }

    for question, tool_name in expectations.items():
        response = engine.ops_chat(question)
        assert response.message.tool_calls[0].tool_name == tool_name

    engine.reset()


def test_entity_grounding_tracks_randomized_current_run_and_not_prior_run() -> None:
    renter_names = {renter.id: renter.name for renter in RENTERS}
    for seed in (1, 6, 9):
        engine = _completed_engine(seed)
        journey = engine.snapshot().selected_journeys[0]
        first_name = renter_names[journey.renter_id].split()[0]

        response = engine.ops_chat(f"what happened with {first_name}")

        assert response.message.tool_calls[0].tool_name == "get_renter_history"
        assert renter_names[journey.renter_id] in response.message.content
        engine.reset()

    engine = _completed_engine(0)
    engine.reset()
    engine.start(seed=1)
    response = engine.ops_chat("why did you contact jordan")
    assert response.message.content == (
        "jordan is not part of the current simulation run."
    )
    assert response.message.tool_calls == ()
    engine.reset()


def test_reset_then_new_run_excludes_retained_prior_run_actions() -> None:
    engine = _completed_engine(0)
    run_a = engine.snapshot()
    assert run_a.rescue_actions
    run_a_action_ids = {action.id for action in run_a.rescue_actions}

    engine.reset()
    run_b = engine.start(seed=1)
    assert run_b.run_id != run_a.run_id

    # Simulate retained audit/history storage: active tools must still filter by run_id.
    with engine._lock:
        engine._rescue_actions.extend(run_a.rescue_actions)

    response = engine.ops_chat("what did you handle during this run?")
    actions = response.message.tool_calls[0].data

    assert response.message.tool_calls[0].tool_name == "get_recent_rescue_actions"
    assert isinstance(actions, list)
    assert not run_a_action_ids.intersection(
        action["id"] for action in actions if isinstance(action, dict)
    )
    assert all(action["run_id"] == run_b.run_id for action in actions)
    engine.reset()


def test_prior_run_person_is_not_resolved_in_new_run_even_if_history_is_retained() -> None:
    engine = _completed_engine(0)
    run_a_actions = engine.snapshot().rescue_actions
    jordan = next(renter for renter in RENTERS if renter.name == "Jordan Patel")
    assert any(action.target_id == jordan.id for action in run_a_actions)

    engine.reset()
    engine.start(seed=1)
    with engine._lock:
        engine._rescue_actions.extend(run_a_actions)

    response = engine.ops_chat("Why did you contact Jordan?")

    assert response.message.content == (
        "Jordan is not part of the current simulation run."
    )
    assert response.message.tool_calls == ()
    engine.reset()


def test_prior_run_attention_and_ai_logs_are_excluded_from_active_scope() -> None:
    engine = _completed_engine(0)
    run_a_cases = engine.attention_cases()
    run_a_logs = engine.ai_logs()
    assert run_a_cases
    assert run_a_logs

    engine.reset()
    run_b = engine.start(seed=1)
    with engine._lock:
        engine._attention_cases.extend(run_a_cases)
        engine._ai_logs.extend(run_a_logs)

    attention = engine.ops_chat("What needs my attention?")

    assert attention.run_id == run_b.run_id
    assert attention.message.tool_calls[0].data == []
    assert not {log.id for log in run_a_logs}.intersection(
        log.id for log in engine.ai_logs()
    )
    engine.reset()


def test_current_run_action_queries_handle_zero_one_and_multiple_interventions() -> None:
    zero_engine = SimulationEngine(duration_seconds=90)
    zero_engine.set_autopilot(False)
    zero = zero_engine.start(seed=0)
    zero_response = zero_engine.ops_chat("What did you handle during this run?")
    assert zero_response.message.tool_calls[0].data == []
    assert zero_engine.snapshot().run_id == zero.run_id
    zero_engine.reset()

    for seed, expected_count in ((1, 1), (0, 2)):
        engine = _completed_engine(seed)
        snapshot = engine.snapshot()
        response = engine.ops_chat("What did you handle during this run?")
        actions = response.message.tool_calls[0].data

        assert len(snapshot.rescue_actions) == expected_count
        assert len(actions) == expected_count
        assert {action["run_id"] for action in actions} == {snapshot.run_id}
        engine.reset()


def test_high_value_and_at_risk_tools_return_only_current_run_bookings() -> None:
    engine = _completed_engine(0)
    snapshot = engine.snapshot()
    current_booking_ids = {booking.id for booking in snapshot.bookings}

    high_value = engine.ops_chat("Show me high-value cases.")
    at_risk = engine.ops_chat("Which booking is most at risk?")

    for response in (high_value, at_risk):
        records = response.message.tool_calls[0].data
        assert isinstance(records, list)
        assert records
        assert {record["run_id"] for record in records} == {snapshot.run_id}
        assert {
            record["booking"]["id"] for record in records
        }.issubset(current_booking_ids)
    engine.reset()


def test_chat_turn_is_discarded_if_active_run_changes_during_planning() -> None:
    engine = SimulationEngine(duration_seconds=90)
    first_run = engine.start(seed=0)

    class RunChangingPlanner:
        def plan(
            self,
            *,
            message: str,
            tool_results: tuple[OpsChatToolResult, ...],
        ) -> OpsChatPlan:
            del message, tool_results
            engine.reset()
            engine.start(seed=1)
            return OpsChatPlan(
                response="I will inspect the old run.",
                tool_name="get_recent_rescue_actions",
            )

    engine.ops_chat_service = OpsChatService(RunChangingPlanner())
    response = engine.ops_chat("What happened overall?")

    assert engine.snapshot().run_id != first_run.run_id
    assert response.run_id == engine.snapshot().run_id
    assert response.message.content == (
        "The simulation run changed while I was checking. "
        "Please ask again for the current run."
    )
    assert response.message.tool_calls == ()
    engine.reset()


def test_ops_chat_api_validates_input_and_returns_restricted_response() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/ops/chat",
            json={"message": "Write me a poem about the ocean."},
        )
        invalid = client.post("/ops/chat", json={"message": ""})
        whitespace = client.post("/ops/chat", json={"message": "   "})

    assert response.status_code == 200
    assert response.json()["message"]["content"] == OUT_OF_DOMAIN_RESPONSE
    assert invalid.status_code == 422
    assert whitespace.status_code == 422
