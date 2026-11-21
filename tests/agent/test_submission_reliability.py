"""Injected Responses clients and in-memory evidence only; no live/scientific run."""

import builtins
from copy import deepcopy
import json
import socket
from types import SimpleNamespace

import pytest

from src.agent import scientific_review_agent as agent
from src.agent.scientific_evidence_tools import compact
from tests.agent.test_scientific_assessment_policy import InMemoryEvidence, assessment


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Live network/SDK use is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    original = builtins.__import__

    def imports(name, *args, **kwargs):
        if name.split(".")[0] == "openai":
            forbidden()
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", imports)


class Item:
    def __init__(self, value):
        self.value = value

    def model_dump(self, **kwargs):
        return deepcopy(self.value)


def function(name, arguments=None, call_id="call"):
    return dict(type="function_call", name=name, arguments=compact(arguments or {}), call_id=call_id)


def response(*, status="completed", reason=None, items=(), output_tokens=16):
    return SimpleNamespace(status=status, incomplete_details=SimpleNamespace(reason=reason,
        message="SECRET_PROVIDER_DETAIL"), error=dict(message="SECRET_PROVIDER_ERROR"),
        output=[Item(item) for item in items], id="mock-response", model="explicit-offline-model",
        usage=Item(dict(input_tokens=100, output_tokens=output_tokens,
            output_tokens_details=dict(reasoning_tokens=8))))


def adapter(reply):
    requests = []

    def create(**kwargs):
        requests.append(deepcopy(kwargs))
        return reply(len(requests), kwargs) if callable(reply) else reply

    model = agent.OpenAIModel("explicit-offline-model", client=SimpleNamespace(
        responses=SimpleNamespace(create=create)))
    return model, requests


@pytest.mark.parametrize("reason", ["max_output_tokens", "content_filter", None, "SECRET_UNKNOWN_REASON"])
@pytest.mark.parametrize("partial_call", [False, True])
def test_incomplete_response_stops_without_dispatch_submission_or_retry(reason, partial_call):
    partial = function("submit_assessment", assessment())
    partial["arguments"] = '{"observed_facts":'  # Deliberately truncated JSON.
    model, requests = adapter(response(status="incomplete", reason=reason,
        items=[partial] if partial_call else [], output_tokens=agent.MAX_OUTPUT_TOKENS))
    run = agent.run_agent(model, InMemoryEvidence(), "Review saved evidence.")
    assert len(requests) == 1 and run["status"] == "abstained"
    assert run["assessment_outcome"] == "no_valid_assessment"
    assert run["flags"] == ["incomplete_model_output"]
    event = run["trace"][0]
    assert event["response_status"] == "incomplete" and event["calls"] == []
    assert event["incomplete_reason"] == ("unrecognized" if reason == "SECRET_UNKNOWN_REASON" else reason)
    assert run["evidence_actually_inspected"] == []
    assert "SECRET" not in compact(run) and 'observed_facts\\"' not in compact(event)


@pytest.mark.parametrize("status", ["completed", None])
def test_empty_call_list_at_token_limit_does_not_invent_incomplete_status(status):
    model, requests = adapter(response(status=status, output_tokens=agent.MAX_OUTPUT_TOKENS,
        items=[dict(type="message", content=[dict(type="output_text", text="SECRET_UNEXPECTED_TEXT")])]))
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    assert run["flags"] == ["missing_model_tool_call"] and len(requests) == 1
    assert run["trace"][0]["response_status"] == status
    assert run["trace"][0]["incomplete_reason"] is None
    assert "SECRET" not in compact(run)


@pytest.mark.parametrize("calls,category", [
    (None, "invalid_model_call"),
    ("malformed", "invalid_model_call"),
    ([function("one"), function("two", call_id="two")], "multiple_model_tool_calls"),
])
def test_structurally_invalid_responses_keep_a_distinct_failure(calls, category):
    class BadModel:
        config = dict(provider="fake", model="invalid-frame", live=False)

        def respond(self, history, tools):
            return dict(calls=calls, assistant_items=[], response_status="completed")

    run = agent.run_agent(BadModel(), InMemoryEvidence(), "Review.")
    assert run["flags"] == [category]
    assert run["trace"][0]["response_validation_failure"] == category
    assert len(run["trace"]) == 1 and run["evidence_actually_inspected"] == []


@pytest.mark.parametrize("status", ["failed", "cancelled", "queued", "in_progress", "SECRET_UNKNOWN_STATUS"])
def test_noncompleted_status_never_dispatches_apparently_valid_calls(status):
    model, requests = adapter(response(status=status, items=[function("get_temporal_summary")]))
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    assert run["flags"] == ["model_response_not_completed"]
    assert len(requests) == 1 and run["evidence_actually_inspected"] == []
    assert run["trace"][0]["response_status"] == ("unrecognized" if status.startswith("SECRET") else status)
    assert "SECRET" not in compact(run)


def test_contradictory_completion_metadata_is_not_accepted():
    model, requests = adapter(response(reason="max_output_tokens", items=[function("get_temporal_summary")]))
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    assert run["flags"] == ["inconsistent_model_response_metadata"]
    assert len(requests) == 1 and run["evidence_actually_inspected"] == []


def test_seven_successful_retrievals_then_incomplete_output_is_not_structural_rejection():
    def reply(number, request):
        if number <= 7:
            name = InMemoryEvidence.names[(number - 1) % 3]
            return response(items=[function(name, call_id="call-" + str(number))])
        assert number == 8
        return response(status="incomplete", reason="max_output_tokens", output_tokens=agent.MAX_OUTPUT_TOKENS)

    model, requests = adapter(reply)
    run = agent.run_agent(model, InMemoryEvidence(), "Assess the saved comparison.")
    assert len(requests) == len(run["trace"]) == 8
    assert len(run["evidence_actually_inspected"]) == 7
    assert run["flags"] == ["incomplete_model_output"]
    assert run["trace"][-1]["incomplete_reason"] == "max_output_tokens"
    assert run["assessment_outcome"] == "no_valid_assessment"


@pytest.mark.parametrize("correct_first", [True, False])
def test_tool_budget_reserves_bounded_submission_and_existing_correction(correct_first):
    def reply(number, request):
        if number <= 8:
            return response(items=[function(InMemoryEvidence.names[(number - 1) % 3],
                call_id="evidence-" + str(number))])
        assert [tool["name"] for tool in request["tools"]] == ["submit_assessment"]
        assert number <= 10
        proposed = assessment()
        if number == 9 and not correct_first:
            proposed["observed_facts"][0]["value_json"] = "4"
        return response(items=[function("submit_assessment", proposed, "submission-" + str(number))],
            output_tokens=1500)

    model, requests = adapter(reply)
    run = agent.run_agent(model, InMemoryEvidence(), "Assess framework consistency and limitations.")
    assert len(requests) == (9 if correct_first else 10)
    assert run["status"] == "submitted_for_researcher_review" and run["flags"] == []
    assert run["assessment_outcome"] == ("valid_first_submission" if correct_first else "valid_corrected_submission")
    assert run["trace"][8]["submission_only"] is True
    assert run["budgets"] == dict(tool_calls=8, turns=10, history_bytes=131072, assessment_submissions=2)
    assert model.config["max_output_tokens"] == agent.MAX_OUTPUT_TOKENS == 6144
    assert model.config["timeout_seconds"] == 60 and model.config["max_retries"] == 0
    assert all(r["max_output_tokens"] == 6144 and r["store"] is False
               and r["parallel_tool_calls"] is False and r["tool_choice"] == "required" for r in requests)
    assert "normally 6-12 essential scalar observed facts" in requests[0]["input"][0]["content"]
    assert "retain the evidence and scientific qualifications required by the question" in requests[0]["input"][0]["content"]
    assert run["execution_eligible"] is False and run["researcher_review"].startswith("REQUIRED")


def test_output_token_cap_still_keeps_a_bounded_response_envelope():
    model, requests = adapter(response(items=[dict(type="reasoning",
        encrypted_content="SECRET_" + "x" * agent.MAX_RESPONSE_ENVELOPE_BYTES),
        function("submit_assessment", assessment())]))
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    assert run["flags"] == ["model_response_envelope_limit"]
    assert len(run["trace"]) == 1
    event = run["trace"][0]
    assert event["parsed_function_call_count"] == 1 and event["calls"] == []
    assert event["serialized_assistant_items_bytes"] > agent.MAX_RESPONSE_ENVELOPE_BYTES
    assert event["function_call_arguments_bytes"] < agent.MAX_MODEL_BYTES
    assert len(requests) == 1 and "SECRET" not in compact(run)


def test_saved_future_run_retains_only_safe_diagnostics_and_actual_output_cap(tmp_path):
    model, requests = adapter(response(status="incomplete", reason="max_output_tokens",
        items=[dict(type="reasoning", encrypted_content="SECRET_REASONING_STATE")],
        output_tokens=agent.MAX_OUTPUT_TOKENS))
    evidence = InMemoryEvidence()
    evidence.root = tmp_path / "sources"
    evidence.sources = {}
    evidence.status = {}
    evidence.epz_binding = None
    evidence.bundle = None
    run = agent.run_agent(model, evidence, "Offline diagnostic serialization test.")
    saved = agent.save_run(tmp_path / "synthetic-future-run", run, evidence)
    trace = json.loads((saved / "agent_trace.json").read_text(encoding="utf-8"))
    record = json.loads((saved / "run_record.json").read_text(encoding="utf-8"))
    assert trace[0]["response_status"] == "incomplete"
    assert trace[0]["incomplete_reason"] == "max_output_tokens"
    assert record["model"]["max_output_tokens"] == requests[0]["max_output_tokens"] == 6144
    assert record["live_model_called"] is False
    assert "SECRET" not in "".join(p.read_text(encoding="utf-8") for p in saved.iterdir())


def test_completed_large_encrypted_envelopes_replay_and_allow_valid_assessment():
    opaque = "SECRET_ENCRYPTED_STATE_" + "x" * (40 * 1024)

    def reply(number, request):
        if number > 1:
            assert any(item.get("encrypted_content") == opaque for item in request["input"])
        if number <= 3:
            items = [function(InMemoryEvidence.names[number - 1], call_id="evidence-" + str(number))]
        else:
            assert number == 4
            items = [function("submit_assessment", assessment(), "assessment")]
        if number in (1, 4):
            items.insert(0, dict(type="reasoning", encrypted_content=opaque))
        return response(items=items, output_tokens=3626 if number == 4 else 16)

    model, requests = adapter(reply)
    run = agent.run_agent(model, InMemoryEvidence(), "Review the saved evidence.")
    assert run["status"] == "submitted_for_researcher_review" and run["flags"] == []
    assert run["assessment_outcome"] == "valid_first_submission" and len(requests) == 4
    for event in (run["trace"][0], run["trace"][-1]):
        assert event["response_status"] == "completed"
        assert event["parsed_function_call_count"] == 1
        assert agent.MAX_MODEL_BYTES < event["serialized_assistant_items_bytes"] <= agent.MAX_RESPONSE_ENVELOPE_BYTES
        assert event["assistant_item_types"] == ["reasoning", "function_call"]
        assert event["response_validation_failure"] is None
    assert all(request["store"] is False for request in requests)
    assert "SECRET" not in compact(run)
    assert run["trace"][-1]["history_bytes_after_assistant"] <= agent.MAX_HISTORY_BYTES


def test_multiple_completed_calls_are_counted_but_never_dispatched():
    model, requests = adapter(response(items=[function("get_temporal_summary", call_id="a"),
        function("get_historical_context", call_id="b")]))
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    assert run["flags"] == ["multiple_model_tool_calls"] and len(requests) == 1
    event = run["trace"][0]
    assert event["parsed_function_call_count"] == 2 and event["calls"] == []
    assert event["assistant_item_types"] == ["function_call", "function_call"]
    assert event["response_validation_failure"] == "multiple_model_tool_calls"
    assert run["evidence_actually_inspected"] == []


def test_completed_response_without_call_has_distinct_safe_diagnostics():
    model, requests = adapter(response(items=[dict(type="reasoning", encrypted_content="SECRET_REASONING"),
        dict(type="message", content=[dict(type="output_text", text="SECRET_FREE_TEXT")])]))
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    event = run["trace"][0]
    assert run["flags"] == ["missing_model_tool_call"] and len(requests) == 1
    assert event["parsed_function_call_count"] == 0
    assert event["assistant_item_types"] == ["reasoning", "message"]
    assert event["serialized_assistant_items_bytes"] > 0
    assert event["response_validation_failure"] == "missing_model_tool_call"
    assert "SECRET" not in compact(run)


@pytest.mark.parametrize("arguments", [" " * (32 * 1024 + 1), chr(0xE9) * (16 * 1024 + 1)],
    ids=["ascii-over-limit", "utf8-over-limit"])
def test_argument_size_limit_is_independent_of_reasoning_envelope(arguments):
    item = function("submit_assessment")
    item["arguments"] = arguments
    model, requests = adapter(response(items=[item]))
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    assert run["flags"] == ["model_arguments_limit"] and len(requests) == 1
    event = run["trace"][0]
    assert event["parsed_function_call_count"] == 1 and event["calls"] == []
    assert event["function_call_arguments_bytes"] == len(arguments.encode("utf-8")) > agent.MAX_MODEL_BYTES
    assert event["response_validation_failure"] == "model_arguments_limit"
    assert event["response_limits"] == dict(function_call_arguments_bytes=32768,
        assistant_items_bytes=65536, history_bytes=131072)


def test_accumulated_opaque_history_stops_before_exceeding_the_context_limit():
    def reply(number, request):
        assert number <= 3
        assert len(compact(request["input"]).encode("utf-8")) <= agent.MAX_HISTORY_BYTES
        size = 55 * 1024 if number < 3 else 20 * 1024
        return response(items=[dict(type="reasoning", encrypted_content="SECRET_" + "x" * size),
            function(InMemoryEvidence.names[number - 1], call_id="call-" + str(number))])

    model, requests = adapter(reply)
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    assert run["flags"] == ["history_limit"] and len(requests) == 3
    assert len(run["evidence_actually_inspected"]) == 2
    event = run["trace"][-1]
    assert event["serialized_assistant_items_bytes"] < agent.MAX_RESPONSE_ENVELOPE_BYTES
    assert event["history_bytes_after_assistant"] > agent.MAX_HISTORY_BYTES
    assert event["response_validation_failure"] == "history_limit"
    assert "SECRET" not in compact(run)


def test_history_limit_also_applies_before_appending_a_tool_result():
    class LargeResults(InMemoryEvidence):
        def call(self, name, arguments):
            result = super().call(name, arguments)
            result["data"]["synthetic_padding"] = "x" * (22 * 1024)
            return result

    def reply(number, request):
        assert number <= 2
        size = 55 * 1024 if number == 1 else 40 * 1024
        return response(items=[dict(type="reasoning", encrypted_content="x" * size),
            function(InMemoryEvidence.names[number - 1], call_id="call-" + str(number))])

    model, requests = adapter(reply)
    run = agent.run_agent(model, LargeResults(), "Review.")
    assert run["flags"] == ["history_limit"] and len(requests) == 2
    event = run["trace"][-1]
    assert event["history_bytes_after_assistant"] <= agent.MAX_HISTORY_BYTES
    assert event["history_bytes_after_tool_result"] > agent.MAX_HISTORY_BYTES
    assert event["response_validation_failure"] == "history_limit"


@pytest.mark.parametrize("items", [None, "SECRET_INVALID_ENVELOPE", [object()], [dict(value=object())]])
def test_invalid_envelope_is_separate_from_call_structure(items):
    class InvalidEnvelope:
        config = dict(provider="fake", model="synthetic", live=False)

        def respond(self, history, tools):
            return dict(response_status="completed", assistant_items=items,
                calls=[dict(name="submit_assessment", arguments=compact(assessment()), call_id="call")])

    run = agent.run_agent(InvalidEnvelope(), InMemoryEvidence(), "Review.")
    assert run["flags"] == ["invalid_model_response_envelope"]
    assert run["trace"][0]["response_validation_failure"] == "invalid_model_response_envelope"
    assert run["trace"][0]["parsed_function_call_count"] == 1
    assert "SECRET" not in compact(run)


@pytest.mark.parametrize("bad_call", [{}, dict(name="submit_assessment", arguments=None, call_id="call")])
def test_invalid_call_structure_is_separate_from_a_missing_call(bad_call):
    class InvalidCall:
        config = dict(provider="fake", model="synthetic", live=False)

        def respond(self, history, tools):
            return dict(response_status="completed", calls=[bad_call], assistant_items=[])

    run = agent.run_agent(InvalidCall(), InMemoryEvidence(), "Review.")
    assert run["flags"] == ["invalid_model_call"]
    assert run["trace"][0]["parsed_function_call_count"] == 1
    assert run["trace"][0]["response_validation_failure"] == "invalid_model_call"


def test_item_type_diagnostics_are_allowlisted_and_truncated():
    class UnknownTypes:
        config = dict(provider="fake", model="synthetic", live=False)

        def respond(self, history, tools):
            return dict(response_status="completed", calls=[], assistant_items=[
                dict(type="SECRET_ITEM_TYPE", text="SECRET_TEXT") for _ in range(20)])

    run = agent.run_agent(UnknownTypes(), InMemoryEvidence(), "Review.")
    event = run["trace"][0]
    assert event["assistant_item_count"] == 20 and event["assistant_item_types_truncated"] is True
    assert event["assistant_item_types"] == ["unrecognized"] * agent.MAX_DIAGNOSTIC_ITEM_TYPES
    assert len(event["assistant_item_types"]) == 16
    assert "SECRET" not in compact(run)


@pytest.mark.parametrize("violation,expected", [
    ("number", "unsupported_observed_value"),
    ("causal", "causal_or_predictive_narrative_requires_review"),
])
def test_larger_envelope_does_not_exempt_scientific_validation(violation, expected):
    def reply(number, request):
        if number <= 3:
            return response(items=[function(InMemoryEvidence.names[number - 1], call_id=str(number))])
        assert number <= 5
        proposed = assessment()
        if violation == "number":
            proposed["observed_facts"][0]["value_json"] = "4"
        else:
            proposed["scientific_inferences"][0]["text"] = "These data prove earthquake causality."
        return response(items=[dict(type="reasoning", encrypted_content="x" * (40 * 1024)),
            function("submit_assessment", proposed, "submission-" + str(number))])

    model, requests = adapter(reply)
    run = agent.run_agent(model, InMemoryEvidence(), "Review.")
    assert expected in run["flags"] and len(requests) == 5
    assert run["status"] in ("rejected_assessment", "flagged_abstention")
    assert all(event["response_validation_failure"] is None for event in run["trace"])
