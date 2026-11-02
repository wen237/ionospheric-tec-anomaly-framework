"""Real A -> evidence -> review-only planning, using synthetic inputs ONLY.

This is a composition test, not a production Agent or tool dispatcher. The B+C
summary is the existing hand-authored contract fixture; B/C are NOT recomputed
by this chain. No Framework D, signing, Store, keys or trusted deployment runs.
"""

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import sys

import numpy as np
import pytest

from src.temporal_anomaly.tec_timeseries import extract_tec_timeseries
from src.temporal_anomaly.temporal_anomaly import detect_temporal_anomalies
from src.workflow.planning_evidence import (
    build_temporal_evidence, evidence_to_json, load_historical_bc_evidence,
)
from src.workflow.planning_approval import (
    build_decision_record, build_execution_intent, validate_decisions,
)
from src.workflow.window_planning import plan_anchor_based_daily_windows
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_planning_approval import config


START = datetime(2000, 12, 20)
END = datetime(2000, 12, 23, 23)
EVENT = dict(case_id="synthetic_case", event_id="synthetic-case-event",
             time_utc="2000-12-29T10:30:00Z", source_reference="synthetic:case-event-v1")


@pytest.fixture(autouse=True)
def prohibit_protected_calls():
    """Test-only call sentinel; NOT an authorization boundary or production gate."""
    protected_modules = {
        "src.spatial_verification.spatial_anomaly", "src.workflow.spatial_adapter",
        "src.workflow.modern_spatial_input_adapter", "src.workflow.spatial_verification_workflow",
        "src.workflow.stage2_runner", "src.workflow.stage2_cli",
        "src.workflow.signed_authorization", "src.workflow.authorization_store", "src.workflow.local_authorizer",
    }
    previous = sys.getprofile()

    def check(frame, event, arg):
        if event == "call" and frame.f_globals.get("__name__") in protected_modules:
            raise AssertionError("Protected execution entered the scientific review test chain")

    sys.setprofile(check)
    try:
        yield
    finally:
        sys.setprofile(previous)


@pytest.fixture
def inputs(tmp_path, historical):
    # Tiny synthetic grid, not a Modern/Legacy GIM product or research dataset.
    first = START - timedelta(days=15)
    epochs = np.array([first + timedelta(hours=i) for i in range(19 * 24)], dtype=object)
    cube = np.full((len(epochs), 2, 2), 10.0)
    cube[(15 + 1) * 24 + 4, 0, 1] = 40.0
    cube[(15 + 2) * 24 + 4, 0, 1] = 40.0
    # Other cells must not influence the requested nearest grid.
    cube[:, 1, 0] = 100.0
    summary_path = tmp_path / "synthetic-historical-context.json"
    summary_path.write_text(json.dumps(historical, allow_nan=False, sort_keys=True) + "\n", encoding="utf-8")
    return epochs, cube, summary_path


def compose_review(inputs, *, selected=(0,), event=None):
    """Exercise public interfaces; deliberately no new production result schema."""
    epochs, cube, path = inputs
    # Reject invalid context before scientific computation or artifact generation.
    context = load_historical_bc_evidence(path)
    series = extract_tec_timeseries(cube, epochs, np.array([32.5, 35.0]), np.array([67.5, 70.0]),
                                   latitude=33.02, longitude=69.46)
    result = detect_temporal_anomalies(series.tec, series.epochs, reference_days=15,
                                      threshold_multiplier=3.0, min_reference_samples=15)
    epoch_bytes = json.dumps([epoch.isoformat() + "Z" for epoch in epochs], separators=(",", ":")).encode("utf-8")
    source_digest = hashlib.sha256(epoch_bytes + cube.astype("<f8").tobytes(order="C")).hexdigest()
    evidence = build_temporal_evidence(result, case_id="synthetic_case", expected_start=START,
        expected_end=END, input_time_convention="naive_utc", time_series=series,
        provenance=dict(sources=[dict(identity="synthetic:tiny-grid-v1", sha256=source_digest)],
                        processing_history="Synthetic in-memory grid. Hash covers UTC epochs plus float64 little-endian TEC bytes, not an observed source file."))
    proposal = plan_anchor_based_daily_windows(evidence, context, case_event=EVENT if event is None else event,
                                              selected_cluster_ids=list(selected), mode="retrospective")
    return result, evidence, context, proposal


def review(intent, proposal, *, declared_approved=False):
    pending = build_decision_record(intent, decision_id="synthetic-pending", status="pending_review",
        reviewer_identity_declaration="synthetic reviewer, not authenticated",
        decision_time_utc="2000-12-30T00:00:00Z", reason="Synthetic test declaration only.")
    records = [pending]
    if declared_approved:
        records.append(build_decision_record(intent, decision_id="synthetic-approved-declaration", status="approved",
            reviewer_identity_declaration="synthetic reviewer, not authenticated",
            decision_time_utc="2000-12-30T01:00:00Z", reason="Not actual authorization.", supersedes=pending))
    checked = validate_decisions(intent, proposal, records, now_utc="2000-12-30T02:00:00Z")
    assert checked["execution_eligible"] is False and checked["trusted_human_authorization"] is False
    assert checked["authorization_verification_status"] == "not_configured"
    return checked


@pytest.mark.parametrize("declared_approved", [False, True], ids=["pending", "approved-declaration"])
def test_actual_A_evidence_candidate_and_review_remain_non_authorizing(inputs, historical, declared_approved):
    epochs, cube, path = inputs
    epochs_before, cube_before, raw = epochs.copy(), cube.copy(), path.read_bytes()
    source_before = deepcopy(historical)
    result, evidence, context, proposal = compose_review(inputs)
    assert result.anomaly.dtype.kind in "iu"
    assert evidence["counts"] == dict(positive=2, negative=0, valid_normal=94, unclassifiable=0, missing_timestamp=0)
    assert evidence["location"]["requested_latitude"] == 33.02
    assert evidence["location"]["grid_latitude"] == 32.5 and evidence["location"]["grid_longitude"] == 70.0
    assert evidence["observation_quality"] is None
    assert evidence["provenance"]["source_hash_verification"] == "not_performed"
    assert context["historical_summary"] == source_before
    assert context["summary_artifact"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert context["summary_artifact"]["hash_verification"] == "computed_from_read_bytes"
    assert context["original_observation_quality"] is None
    assert context["historical_summary"]["clustering"]["temporal_anchors"][0]["n_negative"] == 1
    assert proposal["status"] == "candidates_proposed" and proposal["review_only"] is True
    candidate = proposal["anchor_reports"][0]
    assert candidate["anchor_date_utc"] == "2000-12-21"
    assert candidate["candidate_window"] == dict(start_utc="2000-12-21T00:00:00Z", end_utc="2000-12-22T23:00:00Z",
                                               inclusive_hours=48, bounds="inclusive_hourly_samples")
    assert candidate["backward_stop"]["reason"] == candidate["forward_stop"]["reason"] == "no_anomalies"
    assert proposal["anchor_reports"][1]["reason"] == "not_selected"
    for name, item in (("temporal", evidence), ("historical", context)):
        assert proposal["evidence_references"][name]["content_sha256"] == hashlib.sha256(evidence_to_json(item).encode("utf-8")).hexdigest()
        assert json.loads(evidence_to_json(item)) == item
    intent = build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())
    checked = review(intent, proposal, declared_approved=declared_approved)
    assert checked["decision_history_valid"] is True
    assert checked["review_status"] == ("approved" if declared_approved else "pending_review")
    assert intent.to_dict()["source_hash_verification"] == "declared_not_verified"
    # Fixed epochs/selection/parameters/context produce byte-identical artifacts.
    _, again_evidence, again_context, again_proposal = compose_review(inputs)
    assert evidence_to_json(evidence) == evidence_to_json(again_evidence)
    assert evidence_to_json(context) == evidence_to_json(again_context)
    assert json.dumps(proposal, allow_nan=False, sort_keys=True) == json.dumps(again_proposal, allow_nan=False, sort_keys=True)
    np.testing.assert_array_equal(epochs, epochs_before)
    np.testing.assert_array_equal(cube, cube_before)
    assert path.read_bytes() == raw and historical == source_before


@pytest.mark.parametrize("fault", ["missing_hour", "missing_observation", "insufficient_reference"])
def test_actual_A_quality_failure_abstains_instead_of_normal_fill(inputs, fault):
    epochs, cube, path = inputs
    anchor_hour = (15 + 1) * 24 + 1
    if fault == "missing_hour":
        epochs, cube = np.delete(epochs, anchor_hour), np.delete(cube, anchor_hour, axis=0)
    else:
        cube[(1 * 24 + 1) if fault == "insufficient_reference" else anchor_hour, 0, 1] = np.nan
    result, evidence, _, proposal = compose_review((epochs, cube, path))
    row = next(item for item in evidence["hourly"] if item["timestamp_utc"] == "2000-12-21T01:00:00Z")
    if fault == "missing_hour":
        assert row["classification"] == "missing_timestamp" and row["anomaly_code"] is None
    else:
        assert row["classification"] == "unclassifiable" and row["anomaly_code"] == 0
        assert ("insufficient_reference" if fault == "insufficient_reference" else "nonfinite_observation") in row["unclassifiable_reasons"]
    assert proposal["status"] == "abstained" and proposal["review_only"] is True
    assert proposal["anchor_reports"][0]["candidate_window"] is None
    with pytest.raises(ValueError, match="selected candidate"):
        build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())
    assert json.loads(evidence_to_json(evidence)) == evidence


def test_changed_real_detector_input_invalidates_old_review_binding(inputs):
    _, evidence, _, proposal = compose_review(inputs)
    intent = build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())
    assert review(intent, proposal)["decision_history_valid"]
    inputs[1][(15 + 1) * 24 + 4, 0, 1] += 1
    _, changed_evidence, _, changed = compose_review(inputs)
    replacement = build_execution_intent(changed, selected_cluster_id=0, framework_d=config())
    assert evidence["counts"] == changed_evidence["counts"]
    assert proposal["anchor_reports"][0]["candidate_window"] == changed["anchor_reports"][0]["candidate_window"]
    assert proposal["evidence_references"]["temporal"] != changed["evidence_references"]["temporal"]
    assert intent.digest != replacement.digest
    checked = review(intent, changed)
    assert "invalid_or_stale_intent" in checked["reasons"] and checked["decision_history_valid"] is False


@pytest.mark.parametrize("invalid", ["unsupported_schema", "malformed_json"])
def test_bad_context_fails_before_A_without_fallback(inputs, historical, monkeypatch, invalid):
    def forbid(*args, **kwargs):
        pytest.fail("A ran before context validation")

    monkeypatch.setattr(sys.modules[__name__], "detect_temporal_anomalies", forbid)
    if invalid == "malformed_json":
        inputs[2].write_text("{", encoding="utf-8")
    else:
        invalid_summary = {**historical, "schema_version": 2}
        inputs[2].write_text(json.dumps(invalid_summary), encoding="utf-8")
    with pytest.raises(ValueError):
        compose_review(inputs)


def test_no_explicit_anchor_selection_abstains(inputs):
    _, _, _, proposal = compose_review(inputs, selected=())
    assert proposal["status"] == "abstained" and proposal["abstention_reason"] == "no_anchors_selected"
    assert all(item["candidate_window"] is None for item in proposal["anchor_reports"])


def test_event_without_declared_UTC_is_rejected(inputs):
    with pytest.raises(ValueError, match="UTC"):
        compose_review(inputs, event={**EVENT, "time_utc": "2000-12-29T10:30:00"})
