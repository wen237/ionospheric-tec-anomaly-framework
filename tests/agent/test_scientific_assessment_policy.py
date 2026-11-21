"""Policy/validation contracts with in-memory evidence and FakeModel only.

These fixtures do not establish published criteria or observed scientific results.
No scientific detector, saved research artifact, diagnostic or live API is used.
"""

from copy import deepcopy
import json
import socket
import sys
from types import SimpleNamespace

import pytest

from src.agent import scientific_review_agent as agent
from src.agent.scientific_evidence_tools import compact, definitions


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Scientific computation and live model/network calls are forbidden")

    monkeypatch.setattr(agent.OpenAIModel, "__init__", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    previous = sys.getprofile()

    def guard(frame, event, arg):
        if event == "call" and frame.f_code.co_name in {
            "compute_spatial_anomalies", "detect_temporal_anomalies",
            "run_spatial_verification_from_modern_gim", "run_temporal_review",
            "dispatch_scientific_request", "run_comparison", "diagnose", "_build_report",
        }:
            forbidden()

    sys.setprofile(guard)
    yield
    sys.setprofile(previous)


RESULTS = {
    "R1": dict(ok=True, data=dict(counts=dict(negative=3))),
    "R2": dict(ok=True, data=dict(significant_cells=2)),
    "R3": dict(ok=True, data=dict(historical_reference_checks=dict(all_match=True),
        missing_physical_evidence=["Kp", "Dst", "F10.7"], effective_detector_valid_counts=None)),
}
REFS = [dict(result_id="R1", pointer="/data/counts/negative"),
        dict(result_id="R2", pointer="/data/significant_cells"),
        dict(result_id="R3", pointer="/data/historical_reference_checks/all_match")]


def assessment(text="The TEC anomaly is a framework-consistent potential precursor candidate."):
    return dict(
        observed_facts=[dict(**ref, value_json=compact(value)) for ref, value in zip(REFS, (3, 2, True))],
        scientific_inferences=[dict(text=text, evidence=deepcopy(REFS))],
        alternative_explanations=[dict(text="Space-weather variability remains an unresolved alternative explanation.",
            evidence=[dict(result_id="R3", pointer="/data/missing_physical_evidence")])],
        missing_evidence=["Kp, Dst and F10.7 are not supplied."],
        uncertainties=["Physical mechanisms and effective detector-valid samples remain unresolved."],
        limitations=["Framework consistency does not establish earthquake causality or predictive performance."],
        recommendation=dict(action="review_spatial_comparison", cluster_id=None,
            rationale="The evidence supports a framework-level assessment; physical attribution remains unresolved.",
            evidence=deepcopy(REFS)),
    )


@pytest.mark.parametrize("text", [
    "The TEC anomaly is a framework-consistent potential precursor candidate.",
    "The evidence supports a framework-consistent potential precursor candidate without resolving physical attribution.",
    "The evidence confirms framework consistency.",
    "The evidence establishes consistency with the published framework.",
    "The evidence confirms that the published framework criteria are satisfied.",
    "The evidence establishes that the TEC anomaly is a framework-consistent potential precursor candidate.",
    "The evidence confirms a framework-consistent potential precursor candidate.",
    "The evidence confirms framework consistency; physical attribution remains unresolved.",
    "The evidence confirms framework consistency. This does not establish earthquake causality.",
])
def test_framework_interpretation_is_not_rejected_for_unresolved_physics(text):
    checked, flags = agent._check_assessment(assessment(text), deepcopy(RESULTS), SimpleNamespace(mode="post_spatial"))
    assert flags == []
    assert checked["scientific_inferences"][0]["text"] == text
    assert checked["recommendation"]["action"] == "review_spatial_comparison"
    assert checked["observed_facts"][0]["value"] == 3
    assert checked["missing_evidence"] == ["Kp, Dst and F10.7 are not supplied."]


@pytest.mark.parametrize("text", [
    "Framework consistency proves earthquake causality.",
    "The framework-consistent potential precursor candidate predicts an earthquake.",
    "The evidence confirms framework consistency and earthquake causality.",
    "The evidence confirms a framework-consistent potential precursor candidate and predictive performance.",
    "The evidence establishes that the TEC anomaly is a framework-consistent potential precursor candidate and is a precursor.",
    "The evidence confirms framework consistency; this proves an earthquake relationship.",
    "The evidence confirms framework consistency. This predicts earthquakes.",
    "The evidence confirms framework consistency, which establishes causality.",
    "The evidence confirms that the anomaly is a precursor.",
    "This does not establish causality, but confirms a causal mechanism.",
])
def test_framework_wording_does_not_exempt_physical_or_predictive_overclaims(text):
    with pytest.raises(agent.AssessmentValidationError) as raised:
        agent._check_assessment(assessment(text), deepcopy(RESULTS), SimpleNamespace(mode="post_spatial"))
    assert {p["code"] for p in raised.value.issues} == {"causal_or_predictive_narrative_requires_review"}


@pytest.mark.parametrize("problem,expected", [
    ("missing", "invalid_evidence_reference"),
    ("invalid", "invalid_evidence_reference"),
    ("contradictory", "unsupported_observed_value"),
    ("unchecked", "recommendation_without_checked_observations"),
    ("pre_spatial", "recommendation_outside_evidence_mode"),
])
def test_policy_preserves_required_evidence_and_mode_checks(problem, expected):
    results = deepcopy(RESULTS)
    proposed = assessment()
    mode = "post_spatial"
    if problem == "missing":
        del results["R2"]
    elif problem == "invalid":
        results["R3"]["ok"] = False
    elif problem == "contradictory":
        proposed["observed_facts"][0]["value_json"] = "4"
    elif problem == "unchecked":
        proposed["observed_facts"] = []
    else:
        mode = "pre_spatial"
    with pytest.raises(agent.AssessmentValidationError) as raised:
        agent._check_assessment(proposed, results, SimpleNamespace(mode=mode))
    assert expected in {p["code"] for p in raised.value.issues}


class InMemoryEvidence:
    """A unit-test double, not a scientific evidence validator."""

    mode = "post_spatial"
    names = ("get_temporal_summary", "get_historical_context", "get_spatial_experiment_summary")

    def tool_definitions(self):
        return definitions(self.mode)

    def call(self, name, arguments):
        assert name in self.names and json.loads(arguments) == {}
        return deepcopy(RESULTS["R" + str(self.names.index(name) + 1)])

    def recheck(self):
        pass


def test_bounded_offline_adapter_receives_policy_and_submits_supported_interpretation():
    requests = []

    def model(history, available):
        requests.append((deepcopy(history), deepcopy(available)))
        if len(requests) <= 3:
            name = InMemoryEvidence.names[len(requests) - 1]
            return [dict(name=name, arguments="{}", call_id="call-" + str(len(requests)))]
        system = history[0]["content"]
        assert "Assess evidence validity, framework consistency, and physical attribution" in system
        assert "must\nnot force abstention" in system
        assert "published framework criteria" in system
        assert "Never claim precursor identification" not in system
        assert "review_spatial_comparison" in available[-1]["parameters"]["properties"]["recommendation"]["properties"]["action"]["enum"]
        return [dict(name="submit_assessment", arguments=compact(assessment()), call_id="assessment")]

    run = agent.run_agent(agent.FakeModel(model), InMemoryEvidence(), "Assess the framework-level evidence.")
    assert len(requests) == 4
    assert run["status"] == "submitted_for_researcher_review"
    assert run["assessment_outcome"] == "valid_first_submission" and run["flags"] == []
    assert run["assessment"]["recommendation"]["action"] == "review_spatial_comparison"
    assert len(run["evidence_actually_inspected"]) == 3
    assert run["budgets"] == dict(tool_calls=8, turns=10, history_bytes=131072, assessment_submissions=2)
    assert run["execution_eligible"] is False
    assert run["windows_local_isolation"] == run["trusted_human_authorization"] == "NOT VERIFIED"
    assert run["researcher_review"].startswith("REQUIRED")


AVAILABILITY_LIMITATION = (
    "Finite-input availability is not effective detector-valid coverage, "
    "and zero counts cannot establish valid normal observations."
)
PEAK_POINTER = "/data/experiments/A/polarities/negative/global_peak_centers"
# Synthetic JSON values only; no geographic calculation or diagnostic generation.
PEAKS = [dict(row_index=4, column_index=7, latitude=12.5, longitude=35.0,
              distance_km=9.75, signed_boundary_margin_km=-0.123456789012345,
              count=2, ratio_percent=25.0, grid_center_inside_epz=True),
         dict(row_index=5, column_index=8, latitude=15.0, longitude=40.0,
              distance_km=8.0, signed_boundary_margin_km=-1.873456789012345,
              count=2, ratio_percent=25.0, grid_center_inside_epz=True)]
PEAK_RESULT = dict(ok=True, data=dict(experiments=dict(A=dict(polarities=dict(
    negative=dict(global_peak_centers=PEAKS))))))


def peak_assessment(pointer, value):
    proposed = agent._abstention("Synthetic JSON validation only.")
    ref = dict(result_id="R1", pointer=pointer)
    proposed["observed_facts"] = [dict(**ref, value_json=compact(value))]
    proposed["limitations"] = [AVAILABILITY_LIMITATION]
    proposed["recommendation"].update(action="review_spatial_comparison", evidence=[ref],
        rationale="Inspect the saved descriptive observations; physical attribution remains unresolved.")
    return proposed


@pytest.mark.parametrize("field", ["count", "ratio_percent", "signed_boundary_margin_km", "grid_center_inside_epz"])
def test_exact_scalar_leaf_pointers_support_narrow_peak_observations(field):
    proposed = peak_assessment(PEAK_POINTER + "/0/" + field, PEAKS[0][field])
    checked, flags = agent._check_assessment(proposed, {"R1": deepcopy(PEAK_RESULT)}, SimpleNamespace(mode="post_spatial"))
    assert flags == []
    assert checked["observed_facts"][0]["value"] == PEAKS[0][field]
    assert type(checked["observed_facts"][0]["value"]) is type(PEAKS[0][field])


@pytest.mark.parametrize("whole_array", [True, False])
def test_complete_complex_peak_values_still_pass_exact_validation(whole_array):
    pointer, value = (PEAK_POINTER, PEAKS) if whole_array else (PEAK_POINTER + "/0", PEAKS[0])
    checked, flags = agent._check_assessment(peak_assessment(pointer, value),
        {"R1": deepcopy(PEAK_RESULT)}, SimpleNamespace(mode="post_spatial"))
    assert flags == [] and checked["observed_facts"][0]["value"] == value
    first = checked["observed_facts"][0]["value"][0] if whole_array else checked["observed_facts"][0]["value"]
    assert first["signed_boundary_margin_km"] == PEAKS[0]["signed_boundary_margin_km"]


@pytest.mark.parametrize("mutation", ["omit_margin", "rounded_margin", "integer_for_float", "extra_field", "missing_center", "reordered_centers"])
def test_reconstructed_complex_peak_values_remain_strictly_rejected(mutation):
    wrong = deepcopy(PEAKS)
    if mutation == "omit_margin":
        del wrong[0]["signed_boundary_margin_km"]
    elif mutation == "rounded_margin":
        wrong[0]["signed_boundary_margin_km"] = round(wrong[0]["signed_boundary_margin_km"], 4)
    elif mutation == "integer_for_float":
        wrong[0]["ratio_percent"] = 25
    elif mutation == "extra_field":
        wrong[0]["invented"] = True
    elif mutation == "missing_center":
        wrong.pop()
    else:
        wrong.reverse()
    with pytest.raises(agent.AssessmentValidationError) as raised:
        agent._check_assessment(peak_assessment(PEAK_POINTER, wrong),
            {"R1": deepcopy(PEAK_RESULT)}, SimpleNamespace(mode="post_spatial"))
    assert raised.value.issues == [dict(code="unsupported_observed_value", assessment_location="/observed_facts/0/value_json")]


@pytest.mark.parametrize("suffix", ["/0/missing_margin", "/00/count", "/-1/count", "/0/bad~2escape"])
def test_scalar_guidance_does_not_relax_json_pointer_validation(suffix):
    with pytest.raises(agent.AssessmentReferenceError) as raised:
        agent._check_assessment(peak_assessment(PEAK_POINTER + suffix, 2),
            {"R1": deepcopy(PEAK_RESULT)}, SimpleNamespace(mode="post_spatial"))
    assert raised.value.issues[0]["code"] == "invalid_evidence_reference"


@pytest.mark.parametrize("text", [
    AVAILABILITY_LIMITATION,
    AVAILABILITY_LIMITATION.replace("coverage, and", "coverage,\nand"),
    AVAILABILITY_LIMITATION.upper(),
    "Input coverage is not detector validity, and zero counts cannot establish valid normal observations.",
    "These data do not establish causality, and these data do not predict earthquakes.",
])
def test_coordinated_explicit_limitations_are_not_double_negation(text):
    proposed = assessment()
    proposed["limitations"] = [text]
    checked, flags = agent._check_assessment(proposed, deepcopy(RESULTS), SimpleNamespace(mode="post_spatial"))
    assert flags == [] and checked["limitations"] == [text]
    assert checked["recommendation"]["action"] == "review_spatial_comparison"


@pytest.mark.parametrize("text", [
    "Finite-input availability is not detector validity, and zero counts establish valid normal observations.",
    "These data do not establish causality, and this pattern predicts earthquakes.",
    "Finite-input availability is not detector validity, and zero counts cannot not establish valid normal observations.",
    "Finite-input availability is not detector validity, and zero counts cannot fail to establish valid normal observations.",
    "It is not true that finite-input availability is not detector validity, and zero counts cannot establish valid normal observations.",
    "It is not only finite-input availability, and zero counts cannot establish valid normal observations.",
    "Finite-input availability is not detector validity, and it is not true that zero counts cannot establish valid normal observations.",
    "These data confirm framework consistency; this pattern predicts earthquakes.",
    "These data confirm framework consistency and earthquake causality.",
    AVAILABILITY_LIMITATION + " This proves an earthquake precursor.",
])
def test_coordinated_negation_keeps_overclaim_and_ambiguous_scope_rejection(text):
    proposed = assessment()
    proposed["limitations"] = [text]
    with pytest.raises(agent.AssessmentValidationError) as raised:
        agent._check_assessment(proposed, deepcopy(RESULTS), SimpleNamespace(mode="post_spatial"))
    assert {issue["code"] for issue in raised.value.issues} == {"causal_or_predictive_narrative_requires_review"}


def test_offline_adapter_receives_scalar_guidance_and_handles_both_original_failures():
    class PeakEvidence(InMemoryEvidence):
        def tool_definitions(self):
            return definitions(self.mode, epz_available=True)

        def call(self, name, arguments):
            assert name == "get_epz_diagnostic_summary" and json.loads(arguments) == {}
            return deepcopy(PEAK_RESULT)

    requests = []

    def model(history, available):
        requests.append(deepcopy(history))
        system = history[0]["content"]
        assert "Prefer exact leaf-level scalar JSON Pointers" in system
        assert "complete exact JSON value" in system and "signed_boundary_margin_km" in system
        assert "Pointer resolution and value_json equality remain strict" in system
        if len(requests) == 1:
            return [dict(name="get_epz_diagnostic_summary", arguments="{}", call_id="epz")]
        pointer = PEAK_POINTER + "/0/signed_boundary_margin_km"
        return [dict(name="submit_assessment", arguments=compact(peak_assessment(pointer,
            PEAKS[0]["signed_boundary_margin_km"])), call_id="assessment")]

    run = agent.run_agent(agent.FakeModel(model), PeakEvidence(), "Review the descriptive EPZ observations.")
    assert run["status"] == "submitted_for_researcher_review" and run["flags"] == []
    assert run["assessment_outcome"] == "valid_first_submission" and len(requests) == 2
    assert run["assessment"]["observed_facts"][0]["value"] == PEAKS[0]["signed_boundary_margin_km"]
    assert run["assessment"]["limitations"] == [AVAILABILITY_LIMITATION]
    assert run["execution_eligible"] is False
