"""Synthetic-only request dispatch; resource IDs confer no execution authority."""

from copy import deepcopy
from dataclasses import replace
from datetime import timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from textwrap import dedent
from types import FunctionType

import numpy as np
import pytest

from src.workflow import scientific_request
from src.workflow.planning_approval import build_execution_intent
from src.workflow.scientific_request import dispatch_scientific_request
from tests.workflow.test_planning_approval import config
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_scientific_review_integration import (
    END, EVENT, START, inputs, production_call, prohibit_protected_calls, review, series_from,
)


@pytest.fixture
def request_data():
    return dict(schema_version=1, operation="temporal_review",
        resources=dict(time_series="tec_case", historical_summary="bc_context"),
        case_id="synthetic_case", analysis=dict(start_utc="2000-12-20T00:00:00Z", end_utc="2000-12-23T23:00:00Z"),
        input_time_convention="naive_utc", case_event=deepcopy(EVENT), selected_cluster_ids=[0],
        mode="retrospective", detector=dict(reference_days=15, threshold_multiplier=3.0, min_reference_samples=None),
        provenance=dict(sources=[dict(identity="synthetic:declared-source", sha256=None)], processing_history=None))


def dispatch(request, inputs, **overrides):
    bound = dict(time_series_id="tec_case", time_series=series_from(inputs),
                 historical_summary_id="bc_context", historical_summary_path=inputs[2])
    bound.update(overrides)
    return dispatch_scientific_request(request, **bound)


@pytest.fixture
def prohibit_dispatch(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid metadata reached the scientific workflow")

    monkeypatch.setattr(scientific_request, "run_temporal_review", forbidden)


def test_valid_dispatch_matches_existing_contracts_and_is_deterministic(request_data, inputs, monkeypatch):
    series = series_from(inputs)
    original_request = deepcopy(request_data)
    epochs, tec = series.epochs.copy(), series.tec.copy()
    raw_summary = inputs[2].read_bytes()
    expected = production_call(series, inputs[2], provenance=request_data["provenance"])
    real = scientific_request.run_temporal_review
    calls = []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(scientific_request, "run_temporal_review", spy)
    result = dispatch(request_data, inputs, time_series=series)
    assert len(calls) == 1 and calls[0][0] == (series,)
    assert calls[0][1]["analysis_start"] == START and calls[0][1]["analysis_end"] == END
    assert result == expected
    assert dispatch(json.loads(json.dumps(request_data)), inputs, time_series=series) == result
    assert result[0]["counts"]["positive"] == 2 and result[2]["review_only"] is True
    assert request_data == original_request
    np.testing.assert_array_equal(series.epochs, epochs)
    np.testing.assert_array_equal(series.tec, tec)
    assert inputs[2].read_bytes() == raw_summary


def test_dispatch_reads_only_the_explicitly_bound_summary(request_data, inputs, monkeypatch):
    request_data["case_event"]["source_reference"] = "C:/unapproved/event.json"
    request_data["provenance"]["sources"][0]["identity"] = "../../unapproved-tec.npy"
    original_read = Path.read_bytes
    reads = []

    def read_selected(path):
        assert path == inputs[2], "Metadata was used as a loading path"
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_selected)
    _, _, proposal = dispatch(request_data, inputs)
    assert reads == [inputs[2]] and proposal["review_only"] is True


@pytest.mark.parametrize("value", [None, [], "temporal_review", lambda: pytest.fail("Callable executed")])
def test_request_must_be_a_dictionary(inputs, prohibit_dispatch, value):
    with pytest.raises(ValueError):
        dispatch(value, inputs)


@pytest.mark.parametrize("operation", ["stage2", "framework_d", "run_stage2", "shell", "os.system",
    "src.workflow.temporal_workflow.run_temporal_review", "", None, True, lambda: pytest.fail("Callable executed")])
def test_unknown_operations_and_callables_never_dispatch(request_data, inputs, prohibit_dispatch, operation):
    request_data["operation"] = operation
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("field", ["execute", "execution_eligible", "trusted_human_authorization", "approved",
    "approval_status", "stage2", "module", "callable", "shell", "command", "tool", "loader", "retry",
    "historical_summary_path", "dataset_dir", "output_path"])
def test_unknown_execution_and_path_fields_rejected(request_data, inputs, prohibit_dispatch, field):
    request_data[field] = "C:/unapproved/input.json"
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("section", ["resources", "analysis", "case_event", "detector", "provenance"])
def test_nested_unexpected_path_fields_rejected(request_data, inputs, prohibit_dispatch, section):
    request_data[section]["path"] = "../../unapproved.json"
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("field", ["schema_version", "operation", "resources", "case_id", "analysis",
    "input_time_convention", "case_event", "selected_cluster_ids", "mode", "detector", "provenance"])
def test_all_request_fields_are_required(request_data, inputs, prohibit_dispatch, field):
    del request_data[field]
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("schema_version", 1.0), ("schema_version", 2),
    ("mode", "prospective"), ("mode", None), ("input_time_convention", "local"),
    ("case_id", ""), ("case_id", 1), ("case_id", "different_case"),
    ("selected_cluster_ids", "0"), ("selected_cluster_ids", [True]),
    ("selected_cluster_ids", [0.0]), ("selected_cluster_ids", [-1]), ("selected_cluster_ids", [0, 0]),
    ("detector", {}), ("resources", None), ("case_event", None), ("analysis", []),
])
def test_malformed_request_metadata_fails_before_dispatch(request_data, inputs, prohibit_dispatch, field, value):
    request_data[field] = value
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("field,value", [
    ("reference_days", True), ("reference_days", 15.0), ("reference_days", 0),
    ("reference_days", np.int64(15)), ("threshold_multiplier", True), ("threshold_multiplier", "3"),
    ("reference_days", 10**100), ("threshold_multiplier", 10**400),
    ("threshold_multiplier", float("nan")), ("threshold_multiplier", float("inf")),
    ("threshold_multiplier", -1), ("min_reference_samples", 0),
    ("min_reference_samples", 16), ("min_reference_samples", 15.0),
])
def test_malformed_parameters_are_not_coerced(request_data, inputs, prohibit_dispatch, field, value):
    request_data["detector"][field] = value
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("stamp", ["2000-12-20T00:00:00", "2000-12-20T00:00:00+08:00",
    "2000-12-20T00:00:00+00:00", "2000-12-20T00:01:00Z", "2000-13-20T00:00:00Z",
    "2000-12-25T00:00:00Z", None])
def test_noncanonical_or_invalid_UTC_bounds_rejected(request_data, inputs, prohibit_dispatch, stamp):
    request_data["analysis"]["start_utc"] = stamp
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("field,value", [("time_utc", "2000-12-29T10:30:00"),
    ("event_id", ""), ("source_reference", None), ("source_sha256", "invalid")])
def test_invalid_event_metadata_rejected(request_data, inputs, prohibit_dispatch, field, value):
    request_data["case_event"][field] = value
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("provenance", [dict(sources=[]), dict(sources=[dict(identity="x", sha256="bad")]),
    dict(sources=[dict(identity="x", sha256=None, path="unapproved")]),
    dict(sources=[dict(identity="x", sha256=None), dict(identity="x", sha256=None)]),
    dict(sources=[dict(identity="computed:temporal-review-input-series-v1", sha256=None)]),
    dict(processing_history=True)])
def test_invalid_or_ambiguous_provenance_rejected(request_data, inputs, prohibit_dispatch, provenance):
    request_data["provenance"] = provenance
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


def test_deep_and_cyclic_metadata_fail_without_recursive_validation(request_data, inputs, prohibit_dispatch):
    deeply_nested = {}
    for _ in range(1500):
        deeply_nested = {"nested": deeply_nested}
    for bad in (deeply_nested, request_data):
        request_data["provenance"] = dict(processing_history=bad)
        with pytest.raises(ValueError):
            dispatch(request_data, inputs)


@pytest.mark.parametrize("reference", ["unbound", "../other", "C:\\secret.json", "/tmp/secret", "a/b",
    "https://example.invalid/data", "src.workflow", "$(whoami)", "", None])
@pytest.mark.parametrize("resource", ["time_series", "historical_summary"])
def test_unbound_and_pathlike_resource_references_rejected(request_data, inputs, prohibit_dispatch, resource, reference):
    request_data["resources"][resource] = reference
    with pytest.raises(ValueError):
        dispatch(request_data, inputs)


@pytest.mark.parametrize("overrides", [dict(time_series=None), dict(historical_summary_path=Path("relative.json")),
    dict(historical_summary_path="C:/unapproved.json"), dict(time_series_id="different"),
    dict(historical_summary_id="different"), dict(time_series_id="src.module")])
def test_invalid_bound_resources_rejected(request_data, inputs, prohibit_dispatch, overrides):
    with pytest.raises(ValueError):
        dispatch(request_data, inputs, **overrides)


def test_execution_callback_is_not_an_interface_argument(request_data, inputs, prohibit_dispatch):
    with pytest.raises(TypeError):
        dispatch(request_data, inputs, executor=lambda: pytest.fail("Callback executed"))


@pytest.mark.parametrize("fault", ["empty_selection", "missing_hour", "nonfinite", "insufficient_reference"])
def test_defined_abstention_is_preserved(request_data, inputs, fault):
    series = series_from(inputs)
    if fault == "empty_selection":
        request_data["selected_cluster_ids"] = []
    elif fault == "missing_hour":
        series = replace(series, epochs=np.delete(series.epochs, 16 * 24 + 1), tec=np.delete(series.tec, 16 * 24 + 1))
    else:
        values = series.tec.copy()
        values[25 if fault == "insufficient_reference" else 16 * 24 + 1] = np.nan
        series = replace(series, tec=values)
    evidence, _, proposal = dispatch(request_data, inputs, time_series=series)
    assert proposal["status"] == "abstained" and proposal["review_only"] is True
    assert evidence["counts"]["valid_normal"] < 96
    assert all(report["candidate_window"] is None for report in proposal["anchor_reports"])


@pytest.mark.parametrize("change", ["reference_input", "provenance", "detector", "historical_context"])
def test_same_window_with_changed_input_or_provenance_invalidates_stale_intent(request_data, inputs, change):
    series = series_from(inputs)
    before = dispatch(request_data, inputs, time_series=series)
    intent = build_execution_intent(before[2], selected_cluster_id=0, framework_d=config())
    if change == "reference_input":
        series = replace(series, tec=series.tec.copy())
        series.tec[0] += 1  # Does not move a quartile or candidate boundary.
    elif change == "provenance":
        request_data["provenance"]["processing_history"] = "Revised synthetic declaration."
    elif change == "detector":
        request_data["detector"]["threshold_multiplier"] = 4.0
    else:
        summary = json.loads(inputs[2].read_bytes())
        summary["inputs"]["tec"]["sha256"] = "b" * 64
        inputs[2].write_text(json.dumps(summary), encoding="utf-8")
    after = dispatch(request_data, inputs, time_series=series)
    assert before[0]["hourly"] == after[0]["hourly"]
    assert before[2]["anchor_reports"][0]["candidate_window"] == after[2]["anchor_reports"][0]["candidate_window"]
    assert before[2]["evidence_references"] != after[2]["evidence_references"]
    checked = review(intent, after[2])
    assert "invalid_or_stale_intent" in checked["reasons"]
    assert checked["trusted_human_authorization"] is False and checked["execution_eligible"] is False


def test_aware_UTC_request_is_explicit_not_local_time_conversion(request_data, inputs):
    series = series_from(inputs)
    aware = replace(series, epochs=np.array([epoch.replace(tzinfo=timezone.utc) for epoch in series.epochs], dtype=object))
    request_data["input_time_convention"] = "aware_utc"
    evidence, _, proposal = dispatch(request_data, inputs, time_series=aware)
    assert evidence["input_time_convention"] == "aware_utc" and proposal["review_only"] is True
    with pytest.raises(ValueError):
        dispatch(request_data, inputs, time_series=series)


@pytest.mark.parametrize("fault", ["bad_context", "missing_file", "unknown_cluster"])
def test_existing_resource_and_context_failures_propagate(request_data, inputs, historical, fault):
    if fault == "bad_context":
        inputs[2].write_text(json.dumps({**historical, "schema_version": 99}), encoding="utf-8")
    elif fault == "missing_file":
        inputs = (*inputs[:2], inputs[2].with_name("not-created.json"))
    else:
        request_data["selected_cluster_ids"] = [999]
    with pytest.raises(FileNotFoundError if fault == "missing_file" else ValueError):
        dispatch(request_data, inputs)


def test_production_dispatch_creates_no_review_records_or_protected_calls(
    request_data, inputs, monkeypatch, prohibit_protected_calls,
):
    # The imported autouse fixture already covers this module; name it explicitly
    # here to keep the regression's dependency visible. It guards Python calls
    # in this thread, not OS permissions, other threads or subprocess execution.
    assert callable(sys.getprofile())
    from src.workflow import planning_approval

    def forbidden(*args, **kwargs):
        pytest.fail("Dispatch attempted review/authorization record creation")

    monkeypatch.setattr(planning_approval, "build_execution_intent", forbidden)
    monkeypatch.setattr(planning_approval, "build_decision_record", forbidden)
    request_data["provenance"] = None
    evidence, historical, proposal = dispatch(request_data, inputs)
    assert evidence["evidence_type"] == "case_temporal_anomalies"
    assert historical["evidence_type"] == "historical_bc_context"
    assert proposal["review_only"] is True and "execution_eligible" not in proposal


@pytest.mark.parametrize("module_name", [
    "src.spatial_verification.spatial_anomaly", "src.workflow.stage2_runner",
    "src.workflow.signed_authorization", "src.workflow.authorization_store", "src.workflow.local_authorizer",
])
def test_existing_guard_detects_a_protected_dispatch_regression(
    request_data, inputs, monkeypatch, prohibit_protected_calls, module_name,
):
    # A harmless test function with only a protected namespace label. No actual
    # protected module is imported/called, and no authorization record is made.
    def harmless_probe(*args, **kwargs):
        raise RuntimeError("Guard failed to intercept before the probe body")

    probe = FunctionType(harmless_probe.__code__, {"__name__": module_name})
    monkeypatch.setattr(scientific_request, "run_temporal_review", probe)
    guard = sys.getprofile()
    assert callable(guard)
    try:
        with pytest.raises(AssertionError, match="Protected execution entered"):
            dispatch(request_data, inputs)
    finally:
        # CPython disables a profiler when its callback raises; retain the
        # fixture's protection for the rest of this test and its teardown.
        sys.setprofile(guard)


def test_dispatch_import_remains_headless_in_a_fresh_process():
    script = dedent("""
        import importlib.abc
        import os
        import sys
        assert 'MPLBACKEND' not in os.environ

        class RejectPlotting(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {'matplotlib', 'tkinter', '_tkinter'}:
                    raise AssertionError('Unexpected plotting import: ' + fullname)

        sys.meta_path.insert(0, RejectPlotting())
        from src.workflow.scientific_request import dispatch_scientific_request
        for name in ('matplotlib.pyplot', 'tkinter', 'src.workflow.temporal_adapter',
                     'src.workflow.signed_authorization', 'src.workflow.authorization_store',
                     'src.workflow.local_authorizer', 'src.workflow.stage2_runner',
                     'src.spatial_verification.spatial_anomaly'):
            assert name not in sys.modules, name
    """)
    environment = os.environ.copy()
    environment.pop("MPLBACKEND", None)
    result = subprocess.run([sys.executable, "-B", "-c", script], env=environment,
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
