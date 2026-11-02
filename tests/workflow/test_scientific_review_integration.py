"""Real A -> evidence -> review-only planning, using synthetic inputs ONLY.

This tests the production composition, not an Agent or tool dispatcher. The B+C
summary is the existing hand-authored contract fixture; B/C are NOT recomputed
by this chain. No Framework D, signing, Store, keys or trusted deployment runs.
"""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from textwrap import dedent

import numpy as np
import pytest

from src.temporal_anomaly.tec_timeseries import extract_tec_timeseries
from src.workflow.planning_evidence import evidence_to_json
from src.workflow import temporal_workflow
from src.workflow.temporal_workflow import run_temporal_review
from src.workflow.planning_approval import (
    build_decision_record, build_execution_intent, validate_decisions,
)
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_planning_approval import config


START = datetime(2000, 12, 20)
END = datetime(2000, 12, 23, 23)
EVENT = dict(case_id="synthetic_case", event_id="synthetic-case-event",
             time_utc="2000-12-29T10:30:00Z", source_reference="synthetic:case-event-v1")


@pytest.mark.parametrize("action", ["import", "review"])
def test_fresh_review_process_needs_no_plotting_imports_or_backend(inputs, action):
    # A fresh interpreter avoids false results from pytest's module collection.
    # Blocking these imports also proves review works without plotting installed.
    script = dedent("""
        import importlib.abc
        import os
        import sys

        assert 'MPLBACKEND' not in os.environ

        class RejectPlotting(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {'matplotlib', 'tkinter', '_tkinter'}:
                    raise AssertionError('Review attempted plotting import: ' + fullname)

        sys.meta_path.insert(0, RejectPlotting())
        from src.workflow.temporal_workflow import run_temporal_review

        if sys.argv[2] == 'review':
            from datetime import datetime, timedelta
            import numpy as np
            from src.temporal_anomaly.tec_timeseries import TECTimeSeries

            start = datetime(2000, 12, 20)
            first = start - timedelta(days=15)
            epochs = np.array([first + timedelta(hours=i) for i in range(19 * 24)], dtype=object)
            values = np.full(len(epochs), 10.0)
            values[16 * 24 + 4] = values[17 * 24 + 4] = 40.0
            series = TECTimeSeries(epochs=epochs, tec=values,
                requested_latitude=33.02, requested_longitude=69.46,
                grid_latitude=32.5, grid_longitude=70.0,
                latitude_index=0, longitude_index=0)
            temporal, historical, proposal = run_temporal_review(series,
                case_id='synthetic_case', analysis_start=start,
                analysis_end=datetime(2000, 12, 23, 23), input_time_convention='naive_utc',
                historical_summary_path=sys.argv[1], selected_cluster_ids=[0], mode='retrospective',
                case_event=dict(case_id='synthetic_case', event_id='synthetic-case-event',
                    time_utc='2000-12-29T10:30:00Z', source_reference='synthetic:case-event-v1'))
            assert temporal['counts']['positive'] == 2
            assert historical['evidence_type'] == 'historical_bc_context'
            assert proposal['review_only'] is True
            assert proposal['status'] == 'candidates_proposed'

        for name in ('matplotlib', 'matplotlib.pyplot', 'tkinter', '_tkinter',
                     'src.workflow.temporal_adapter', 'src.temporal_anomaly.plotting'):
            assert name not in sys.modules, name
        print('headless_review_ok')
    """)
    environment = os.environ.copy()
    environment.pop("MPLBACKEND", None)
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script, str(inputs[2]), action],
        cwd=Path(__file__).resolve().parents[2], env=environment,
        capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "headless_review_ok"


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


def series_from(inputs):
    epochs, cube, _ = inputs
    return extract_tec_timeseries(cube, epochs, np.array([32.5, 35.0]), np.array([67.5, 70.0]),
                                 latitude=33.02, longitude=69.46)


def compose_review(inputs, *, selected=(0,), event=None):
    """Prepare synthetic input and call the real production entry point."""
    epochs, cube, path = inputs
    epoch_bytes = json.dumps([epoch.isoformat() + "Z" for epoch in epochs], separators=(",", ":")).encode("utf-8")
    source_digest = hashlib.sha256(epoch_bytes + cube.astype("<f8").tobytes(order="C")).hexdigest()
    return run_temporal_review(series_from(inputs), case_id="synthetic_case", analysis_start=START,
        analysis_end=END, input_time_convention="naive_utc", historical_summary_path=path,
        case_event=EVENT if event is None else event, selected_cluster_ids=list(selected), mode="retrospective",
        reference_days=15, threshold_multiplier=3.0, min_reference_samples=15,
        provenance=dict(sources=[dict(identity="synthetic:tiny-grid-v1", sha256=source_digest)],
                        processing_history="Synthetic in-memory grid. Hash covers UTC epochs plus float64 little-endian TEC bytes, not an observed source file."))


def production_call(series, summary_path, **overrides):
    arguments = dict(case_id="synthetic_case", analysis_start=START, analysis_end=END,
        input_time_convention="naive_utc", historical_summary_path=summary_path,
        case_event=deepcopy(EVENT), selected_cluster_ids=[0], mode="retrospective")
    arguments.update(overrides)
    return run_temporal_review(series, **arguments)


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
    evidence, context, proposal = compose_review(inputs)
    assert all(type(row["anomaly_code"]) is int for row in evidence["hourly"])
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
    again_evidence, again_context, again_proposal = compose_review(inputs)
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
    evidence, _, proposal = compose_review((epochs, cube, path))
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
    evidence, _, proposal = compose_review(inputs)
    intent = build_execution_intent(proposal, selected_cluster_id=0, framework_d=config())
    assert review(intent, proposal)["decision_history_valid"]
    inputs[1][(15 + 1) * 24 + 4, 0, 1] += 1
    changed_evidence, _, changed = compose_review(inputs)
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

    monkeypatch.setattr(temporal_workflow, "detect_temporal_anomalies", forbid)
    if invalid == "malformed_json":
        inputs[2].write_text("{", encoding="utf-8")
    else:
        invalid_summary = {**historical, "schema_version": 2}
        inputs[2].write_text(json.dumps(invalid_summary), encoding="utf-8")
    with pytest.raises(ValueError):
        compose_review(inputs)


def test_no_explicit_anchor_selection_abstains(inputs):
    _, _, proposal = compose_review(inputs, selected=())
    assert proposal["status"] == "abstained" and proposal["abstention_reason"] == "no_anchors_selected"
    assert all(item["candidate_window"] is None for item in proposal["anchor_reports"])


def test_event_without_declared_UTC_is_rejected(inputs):
    with pytest.raises(ValueError, match="UTC"):
        compose_review(inputs, event={**EVENT, "time_utc": "2000-12-29T10:30:00"})


def test_reference_only_change_binds_even_if_all_statistics_remain_identical(inputs):
    series = series_from(inputs)
    before = production_call(series, inputs[2])
    intent = build_execution_intent(before[2], selected_cluster_id=0, framework_d=config())
    # One reference value changes below the quartile resolution. No caller hash
    # is supplied, so the production input fingerprint must bind this change.
    changed = replace(series, tec=series.tec.copy())
    changed.tec[0] += 1
    after = production_call(changed, inputs[2])
    assert before[0]["hourly"] == after[0]["hourly"]
    assert before[0]["counts"] == after[0]["counts"]
    assert before[2]["anchor_reports"][0]["candidate_window"] == after[2]["anchor_reports"][0]["candidate_window"]
    assert before[0]["provenance"]["sources"] != after[0]["provenance"]["sources"]
    assert "invalid_or_stale_intent" in review(intent, after[2])["reasons"]
    assert before[0]["provenance"]["processing_history"] is None
    assert before[0]["provenance"]["source_hash_verification"] == "not_performed"
    assert before[0]["provenance"]["sources"][0]["identity"] == "computed:temporal-review-input-series-v1"


def test_provenance_changes_invalidate_binding_without_mutating_callers(inputs):
    series = series_from(inputs)
    provenance = dict(sources=[dict(identity="synthetic:declared-source", sha256=None)], processing_history="Synthetic only.")
    event, selected = deepcopy(EVENT), [0]
    original = deepcopy((provenance, event, selected))
    epochs, values = series.epochs.copy(), series.tec.copy()
    first = production_call(series, inputs[2], provenance=provenance, case_event=event, selected_cluster_ids=selected)
    assert (provenance, event, selected) == original
    np.testing.assert_array_equal(series.epochs, epochs)
    np.testing.assert_array_equal(series.tec, values)
    intent = build_execution_intent(first[2], selected_cluster_id=0, framework_d=config())
    changed = {**provenance, "processing_history": "Synthetic provenance revised."}
    second = production_call(series, inputs[2], provenance=changed)
    assert first[0]["hourly"] == second[0]["hourly"]
    assert first[2]["anchor_reports"][0]["candidate_window"] == second[2]["anchor_reports"][0]["candidate_window"]
    assert "invalid_or_stale_intent" in review(intent, second[2])["reasons"]


@pytest.mark.parametrize("mode", ["prospective", "", None, True])
def test_unsupported_mode_fails_before_context_io_or_detector(inputs, monkeypatch, mode):
    def forbid(*args, **kwargs):
        pytest.fail("Unsupported mode reached I/O or detector")

    monkeypatch.setattr(temporal_workflow, "load_historical_bc_evidence", forbid)
    monkeypatch.setattr(temporal_workflow, "detect_temporal_anomalies", forbid)
    with pytest.raises(ValueError, match="retrospective"):
        production_call(series_from(inputs), inputs[2], mode=mode)


@pytest.mark.parametrize("fault", ["duplicate", "unordered", "nonhourly", "local_time", "fold", "mixed_convention"])
def test_all_source_timestamps_including_reference_are_validated(inputs, monkeypatch, fault):
    series = series_from(inputs)
    epochs = series.epochs.copy()
    if fault == "duplicate":
        epochs[1] = epochs[0]
    elif fault == "unordered":
        epochs[0], epochs[1] = epochs[1], epochs[0]
    elif fault == "nonhourly":
        epochs[0] += timedelta(minutes=1)
    elif fault == "fold":
        epochs[0] = epochs[0].replace(fold=1)
    else:
        epochs[0] = epochs[0].replace(tzinfo=timezone(timedelta(hours=8)) if fault == "local_time" else timezone.utc)

    def forbid(*args, **kwargs):
        pytest.fail("Malformed reference timestamp reached detector")

    monkeypatch.setattr(temporal_workflow, "detect_temporal_anomalies", forbid)
    with pytest.raises(ValueError):
        production_call(replace(series, epochs=epochs), inputs[2])


def test_aware_UTC_preserves_convention_without_changing_caller_epochs(inputs):
    series = series_from(inputs)
    epochs = np.array([epoch.replace(tzinfo=timezone.utc) for epoch in series.epochs], dtype=object)
    aware = replace(series, epochs=epochs)
    before = epochs.copy()
    evidence, _, proposal = production_call(aware, inputs[2], input_time_convention="aware_utc",
        analysis_start=START.replace(tzinfo=timezone.utc), analysis_end=END.replace(tzinfo=timezone.utc))
    assert evidence["input_time_convention"] == "aware_utc"
    assert proposal["anchor_reports"][0]["candidate_window"]["inclusive_hours"] == 48
    np.testing.assert_array_equal(epochs, before)


@pytest.mark.parametrize("bounds", [dict(analysis_start=END, analysis_end=START),
    dict(analysis_start=START + timedelta(minutes=1)),
    dict(analysis_end=END.replace(tzinfo=timezone.utc))])
def test_invalid_or_convention_mismatched_bounds_rejected(inputs, bounds):
    with pytest.raises(ValueError):
        production_call(series_from(inputs), inputs[2], **bounds)


def test_requested_bounds_clip_detector_rows_without_expanding_analysis(inputs):
    series = series_from(inputs)
    full, _, _ = production_call(series, inputs[2])
    start, end = START + timedelta(days=1), START + timedelta(days=1, hours=23)
    clipped, _, proposal = production_call(series, inputs[2], analysis_start=start, analysis_end=end)
    assert clipped["analysis"]["expected_hours"] == 24
    assert clipped["hourly"] == full["hourly"][24:48]
    assert proposal["anchor_reports"][0]["candidate_window"]["inclusive_hours"] == 24


def test_insufficient_calendar_history_fails_without_shortening_reference(inputs):
    series = series_from(inputs)
    short = replace(series, epochs=series.epochs[24:], tec=series.tec[24:])
    with pytest.raises(ValueError, match="calendar reference"):
        production_call(short, inputs[2])


def test_explicit_relaxed_reference_parameter_is_preserved_without_retry(inputs, monkeypatch):
    series = series_from(inputs)
    values = series.tec.copy()
    values[25] = np.nan
    real = temporal_workflow.detect_temporal_anomalies
    calls = []

    def spy(*args, **kwargs):
        calls.append(kwargs.copy())
        return real(*args, **kwargs)

    monkeypatch.setattr(temporal_workflow, "detect_temporal_anomalies", spy)
    evidence, _, proposal = production_call(replace(series, tec=values), inputs[2], min_reference_samples=14)
    assert len(calls) == 1 and calls[0]["min_reference_samples"] == 14
    assert calls[0]["reference_days"] == 15 and calls[0]["threshold_multiplier"] == 3.0
    assert evidence["parameters"]["min_reference_samples"] == 14
    assert evidence["counts"]["unclassifiable"] == 0
    assert proposal["status"] == "candidates_proposed"


@pytest.mark.parametrize("provenance", [dict(sources=[]), dict(unrecognized="value"),
    dict(sources=[dict(identity="same", sha256="a" * 64), dict(identity="same", sha256="b" * 64)]),
    dict(sources=[dict(identity="computed:temporal-review-input-series-v1", sha256="a" * 64)])])
def test_ambiguous_or_invalid_provenance_rejected_before_A(inputs, monkeypatch, provenance):
    def forbid(*args, **kwargs):
        pytest.fail("Invalid provenance reached detector")

    monkeypatch.setattr(temporal_workflow, "detect_temporal_anomalies", forbid)
    with pytest.raises(ValueError):
        production_call(series_from(inputs), inputs[2], provenance=provenance)


@pytest.mark.parametrize("parameters", [dict(reference_days=True), dict(reference_days=0),
    dict(threshold_multiplier=float("nan")), dict(threshold_multiplier=-1),
    dict(min_reference_samples=16), dict(min_reference_samples=True)])
def test_invalid_detector_parameters_fail_explicitly(inputs, parameters):
    with pytest.raises(ValueError):
        production_call(series_from(inputs), inputs[2], **parameters)


def test_only_reference_rows_yield_defined_missing_analysis_abstention(inputs):
    series = series_from(inputs)
    reference_only = replace(series, epochs=series.epochs[:15 * 24], tec=series.tec[:15 * 24])
    evidence, _, proposal = production_call(reference_only, inputs[2])
    assert evidence["counts"]["missing_timestamp"] == 96
    assert evidence["counts"]["valid_normal"] == 0
    assert all(row["anomaly_code"] is None for row in evidence["hourly"])
    assert proposal["status"] == "abstained"


def test_missing_context_file_is_not_recomputed_or_replaced(inputs):
    missing = inputs[2].with_name("absent-context.json")
    with pytest.raises(FileNotFoundError):
        production_call(series_from(inputs), missing)
    assert not missing.exists()


def test_non_authorizing_entrypoint_creates_no_review_declarations(inputs, monkeypatch):
    module = sys.modules["src.workflow.planning_approval"]

    def forbid(*args, **kwargs):
        pytest.fail("Production review attempted to create review declarations")

    monkeypatch.setattr(module, "build_execution_intent", forbid)
    monkeypatch.setattr(module, "build_decision_record", forbid)
    evidence, context, proposal = production_call(series_from(inputs), inputs[2])
    assert evidence["evidence_type"] == "case_temporal_anomalies"
    assert context["evidence_type"] == "historical_bc_context"
    assert proposal["review_only"] is True
    assert "approval_status" not in proposal


def test_input_fingerprint_is_canonical_across_numeric_byte_order(inputs):
    series = series_from(inputs)
    first = production_call(series, inputs[2])
    swapped = replace(series, tec=series.tec.astype(series.tec.dtype.newbyteorder(">")))
    assert production_call(swapped, inputs[2]) == first


@pytest.mark.parametrize("value,marker", [(np.inf, "positive_infinity"), (-np.inf, "negative_infinity")])
def test_nonfinite_observations_remain_explicit_in_production_output(inputs, value, marker):
    series = series_from(inputs)
    values = series.tec.copy()
    values[(15 + 1) * 24 + 1] = value
    evidence, _, proposal = production_call(replace(series, tec=values), inputs[2])
    row = evidence["hourly"][25]
    assert row["classification"] == "unclassifiable" and row["anomaly_code"] == 0
    assert row["observed"] is None and row["nonfinite_values"]["observed"] == marker
    assert proposal["status"] == "abstained"
    assert json.loads(evidence_to_json(evidence)) == evidence
