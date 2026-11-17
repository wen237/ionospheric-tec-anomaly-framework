"""Hand-authored synthetic evidence only; no detector or model execution."""

import builtins
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys

import numpy as np
import pytest

from examples import diagnose_afghanistan_epicentral_zone as diagnostic
from src.agent.scientific_evidence_tools import EvidenceTools, EXPERIMENTS, POST_ROOT, PRE_ROOT
# Reuse the existing hand-authored saved-bundle fixtures, never real case data.
from tests.agent.test_scientific_review_agent import pre_root, post_root
from tests.workflow.test_select_afghanistan_mvp_window import bundle_factory, modern_dir
from tests.workflow.test_planning_evidence import historical


@pytest.fixture(autouse=True)
def prohibit_computation_and_network(monkeypatch):
    """Test sentinels only; not a production isolation/authorization claim."""
    def forbidden(*args, **kwargs):
        raise AssertionError("Network or model-tool execution is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(EvidenceTools, "call", forbidden)
    original_import = builtins.__import__

    def offline_import(name, *args, **kwargs):
        if name.split(".")[0] == "openai":
            raise AssertionError("Diagnostic attempted an OpenAI SDK import")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", offline_import)
    blocked = {
        "src.spatial_verification.spatial_anomaly": {"compute_spatial_anomalies"},
        "src.temporal_anomaly.temporal_anomaly": {"detect_temporal_anomalies"},
        "examples.compare_afghanistan_mvp_spatial": {"run_comparison", "_run_modern_d", "_input_validity"},
        "examples.review_afghanistan_mvp": {"run_review", "main"},
    }
    blocked_modules = {
        "src.workflow.stage2_cli", "src.workflow.stage2_runner",
        "src.workflow.spatial_adapter", "src.workflow.modern_spatial_input_adapter",
        "src.agent.scientific_review_agent", "examples.run_afghanistan_mvp_agent",
        "src.workflow.statistical_analysis_adapter", "src.workflow.clustering_adapter",
        "src.workflow.statistical_significance_adapter",
    }
    previous = sys.getprofile()

    def check(frame, event, arg):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            if (module in blocked_modules or module.startswith("src.statistical_clustering.")
                    or frame.f_code.co_name in blocked.get(module, ())):
                raise AssertionError("Diagnostic attempted framework or LLM execution")
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(check)
    try:
        yield
    finally:
        sys.setprofile(previous)


def _load(path):
    return json.loads(path.read_bytes())


def _dump(path, value):
    path.write_bytes(diagnostic.serialize_report(value))


def _pin(path):
    return diagnostic.handoff._metadata(path.read_bytes())


def _repin_synthetic_arrays(root, change):
    """Mutate synthetic fixtures only; bind using existing comparison helpers."""
    base = root / POST_ROOT
    comparison = _load(base / "comparison_summary.json")
    arrays = []
    for label, name in EXPERIMENTS.items():
        path = base / name
        with np.load(path / "spatial_arrays.npz", allow_pickle=False) as archive:
            a = {k: archive[k] for k in archive.files}
        change(label, a)
        for polarity in ("positive", "negative"):
            a[polarity + "_ratio"] = a[polarity + "_counts"] / int(a["ratio_denominator"]) * 100.0
        np.savez_compressed(path / "spatial_arrays.npz", **a)
        summary = _load(path / "experiment_summary.json")
        summary["artifacts"]["spatial_arrays.npz"] = dict(path="spatial_arrays.npz", **_pin(path / "spatial_arrays.npz"))
        summary["spatial_anomalies"] = EvidenceTools._peaks(a)
        if label == "A":
            summary["historical_reference_checks"] = diagnostic.saved_spatial._reference_checks(a, summary["spatial_anomalies"])
        _dump(path / "experiment_summary.json", summary)
        comparison["experiments"][name] = summary
        comparison["artifacts"][name + "/experiment_summary.json"] = _pin(path / "experiment_summary.json")
        arrays.append(a)
    diff = diagnostic.saved_spatial._differences(*arrays)
    np.savez_compressed(base / "cellwise_differences.npz", **diff)
    comparison["artifacts"]["cellwise_differences.npz"] = _pin(base / "cellwise_differences.npz")
    comparison["cellwise_statistics"] = {k: dict(minimum=float(v.min()), maximum=float(v.max()),
        mean=float(v.mean()), changed_cells=int(np.count_nonzero(v))) for k, v in diff.items()
        if k.endswith("_b_minus_a") and v.ndim == 2}
    _dump(base / "comparison_summary.json", comparison)


def _report(root):
    return diagnostic._build_report(EvidenceTools(root, "post_spatial"))


def test_radius_definition():
    assert diagnostic.preparation_radius_km(6.0) == pytest.approx(380.1893963205613, rel=1e-14)
    assert diagnostic.preparation_radius_km(5.0) == pytest.approx(141.2537544622754, rel=1e-14)


@pytest.mark.parametrize("value", [True, 0, -1, float("nan"), float("inf"), 10000, "6"])
def test_invalid_radius_inputs(value):
    with pytest.raises(ValueError):
        diagnostic.preparation_radius_km(value)


@pytest.mark.parametrize("start,end,angle", [
    ((0, 0), (0, 0), 0), ((0, 0), (0, 90), np.pi / 2),
    ((0, 0), (0, 180), np.pi), ((0, 179), (0, -179), np.deg2rad(2)),
    ((0, -180), (0, 180), 0), ((90, 10), (90, -170), 0),
])
def test_analytic_great_circle_and_wrap(start, end, angle):
    result = diagnostic.great_circle_distances_km(*start, *end)
    reverse = diagnostic.great_circle_distances_km(*end, *start)
    assert float(result) == pytest.approx(diagnostic.EARTH_RADIUS_KM * angle, abs=1e-8)
    assert float(reverse) == pytest.approx(float(result), abs=1e-8)


def test_distances_agree_with_independent_unit_vectors():
    lat = np.array([-87.5, -30, 0, 30, 33.02, 87.5])[:, None]
    lon = np.array([-180, -150, 0, 69.464, 179, 180])[None, :]
    phi, lam = np.broadcast_arrays(np.deg2rad(lat), np.deg2rad(lon))
    p0, l0 = np.deg2rad([33.02, 69.464])
    u = np.stack([np.cos(phi)*np.cos(lam), np.cos(phi)*np.sin(lam), np.sin(phi)], axis=-1)
    v = np.array([np.cos(p0)*np.cos(l0), np.cos(p0)*np.sin(l0), np.sin(p0)])
    angle = np.arctan2(np.linalg.norm(np.cross(u, v), axis=-1), np.sum(u*v, axis=-1))
    np.testing.assert_allclose(diagnostic.great_circle_distances_km(33.02, 69.464, lat, lon),
                               diagnostic.EARTH_RADIUS_KM * angle, atol=1e-8, rtol=0)


@pytest.mark.parametrize("coordinates", [(91, 0), (0, 181), (float("nan"), 0)])
def test_invalid_geographic_coordinates(coordinates):
    with pytest.raises(ValueError):
        diagnostic.great_circle_distances_km(33.02, 69.464, *coordinates)


def test_inclusive_boundary_has_no_tolerance():
    r = diagnostic.preparation_radius_km(6.0)
    values = np.array([np.nextafter(r, -np.inf), r, np.nextafter(r, np.inf)])
    np.testing.assert_array_equal(diagnostic.center_membership(values, r), [True, True, False])


def test_canonical_grid_and_shared_mask(post_root):
    report = _report(post_root)
    assert report["event"] == diagnostic.EVENT
    assert report["grid"]["orientation"] == "canonical"
    assert report["grid"]["latitudes"][0] == -87.5
    centers = report["mask"]["centers"]
    assert [(p["row_index"], p["column_index"], p["latitude"], p["longitude"]) for p in centers] == [
        (47, 50, 30.0, 70.0), (48, 50, 32.5, 70.0), (49, 50, 35.0, 70.0)]
    assert [p["distance_km"] for p in centers] == pytest.approx([339.62980257646694, 76.52036812467, 225.64016431002625])
    assert all(p["signed_boundary_margin_km"] < 0 for p in centers)
    assert report["mask"]["sha256"] == "7644ce22be563963c99ed349737aa4a7ac582a5d4d2495f0fa49512ba89063c3"
    assert report["mask"]["closest_excluded_center_to_boundary"]["longitude"] == 65.0
    for label in ("A", "B"):
        assert [(p["row_index"], p["column_index"]) for p in report["experiments"][label]["included_centers"]] == [(47, 50), (48, 50), (49, 50)]


@pytest.mark.parametrize("mutation", ["flip_latitude", "different_longitude", "legacy", "wrong_event"])
def test_inconsistent_event_or_grid_rejected(post_root, mutation):
    evidence = EvidenceTools(post_root, "post_spatial")
    if mutation == "flip_latitude":
        evidence.arrays["A"]["latitudes"] = evidence.arrays["A"]["latitudes"][::-1]
    elif mutation == "different_longitude":
        evidence.arrays["B"]["longitudes"][0] = -179
    elif mutation == "legacy":
        evidence.summaries["B"]["parameters"]["grid_orientation"] = "legacy"
    else:
        evidence.summaries["A"]["event"]["latitude"] = 33.092
    with pytest.raises(ValueError):
        diagnostic._build_report(evidence)


def test_empty_region_is_explicit(post_root, monkeypatch):
    monkeypatch.setattr(diagnostic, "center_membership", lambda distances, radius: np.zeros(distances.shape, dtype=bool))
    report = _report(post_root)
    assert report["mask"]["status"] == "empty"
    assert report["mask"]["centers"] == []
    assert report["mask"]["closest_included_center_to_boundary"] is None
    for exp in report["experiments"].values():
        assert exp["included_centers"] == []
        for polarity in exp["polarities"].values():
            assert polarity["regional"]["grid_hour_occurrence_count_sum"] == 0
            assert polarity["regional"]["unweighted_mean_ratio_percent"] is None
            assert polarity["regional"]["count_minimum"] is None
    assert report["comparison"]["polarities"]["negative"]["mean_cell_ratio_difference_percentage_points"] is None


def test_tied_peaks_are_preserved_and_located_without_flip(post_root):
    def change(label, arrays):
        arrays["positive_counts"][26, 5] = arrays["positive_counts"][26, 6]
    _repin_synthetic_arrays(post_root, change)
    report = _report(post_root)
    for exp in report["experiments"].values():
        peaks = exp["polarities"]["positive"]["global_peak_centers"]
        assert [(p["latitude"], p["longitude"]) for p in peaks] == [(-22.5, -155.0), (-22.5, -150.0)]
        assert [p["distance_km"] for p in peaks] == pytest.approx([15521.47715669257, 15985.844341923244])
        assert all(not p["grid_center_inside_epz"] for p in peaks)
        negative = exp["polarities"]["negative"]["global_peak_centers"]
        assert len(negative) == 1 and negative[0]["latitude"] == 30.0
        assert negative[0]["grid_center_inside_epz"] is True


def test_zero_map_has_no_global_peak_and_keeps_validity_limit(post_root):
    def change(label, arrays):
        arrays["positive_counts"][:] = 0
    _repin_synthetic_arrays(post_root, change)
    report = _report(post_root)
    for exp in report["experiments"].values():
        assert exp["polarities"]["positive"]["global_peak_centers"] == []
        assert exp["polarities"]["positive"]["global_maximum_ratio_percent"] == 0
        assert exp["effective_detector_valid_counts"] is None


def test_counts_and_percentages_retain_original_denominators(post_root):
    report = _report(post_root)
    a, b = report["experiments"]["A"], report["experiments"]["B"]
    assert (a["ratio_denominator"], b["ratio_denominator"]) == (120, 144)
    assert (a["nominal_grid_hour_denominator"], b["nominal_grid_hour_denominator"]) == (360, 432)
    assert a["polarities"]["negative"]["regional"]["grid_hour_occurrence_count_sum"] == 10
    assert b["polarities"]["negative"]["regional"]["grid_hour_occurrence_count_sum"] == 12
    assert a["polarities"]["negative"]["regional"]["unweighted_mean_ratio_percent"] == pytest.approx(100 * 10 / 360)
    first_a, first_b = a["included_centers"][0], b["included_centers"][0]
    assert first_b["negative_counts"] > first_a["negative_counts"]
    assert first_b["negative_ratio"] < first_a["negative_ratio"]
    expected = ((7/144*100 - 6/120*100) + (5/144*100 - 4/120*100)) / 3
    assert report["comparison"]["polarities"]["negative"]["mean_cell_ratio_difference_percentage_points"] == pytest.approx(expected)


def test_signed_b_minus_a_cannot_underflow(post_root):
    def change(label, arrays):
        arrays["negative_counts"] = arrays["negative_counts"].astype(np.uint16)
        if label == "B":
            arrays["negative_counts"][47, 50] = 4
    _repin_synthetic_arrays(post_root, change)
    report = _report(post_root)
    assert report["comparison"]["included_centers"][0]["negative_counts_b_minus_a"] == -2
    assert report["comparison"]["polarities"]["negative"]["grid_hour_occurrence_count_sum_b_minus_a"] == -1


def test_availability_is_not_effective_detector_validity(post_root):
    def change(label, arrays):
        arrays["target_input_finite_counts"][47, 50] = 100 if label == "A" else 110
        arrays["initial_reference_input_finite_counts"][47, 50] = 300
    _repin_synthetic_arrays(post_root, change)
    report = _report(post_root)
    a = report["experiments"]["A"]
    assert a["included_centers"][0]["target_input_finite_counts"] == 100
    assert a["input_availability"]["initial_reference_input_finite_counts"]["included_minimum"] == 300
    assert a["included_centers"][0]["negative_ratio"] == 5
    assert a["ratio_denominator"] == 120 and a["effective_detector_valid_counts"] is None


def test_scientific_distinctions_and_review_state(post_root):
    report = _report(post_root)
    ref = report["scientific_reference"]
    assert ref["historical_visual_overlap_reproduced"] is False
    assert ref["grid_cell_intersection_computed"] is False
    assert ref["physical_areal_coverage_computed"] is False
    assert ref["historical_spatial_decision_rule"] != ref["diagnostic_spatial_decision_rule"]
    assert ref["radius_tolerance_km"] == 0
    assert report["summary_semantics"]["excluded_interpretations"] == [
        "unique anomaly hours", "EPZ areal coverage", "spatial statistical significance", "earthquake association probability"]
    state = report["review_state"]
    assert state["stop_point"] == "Scientific & Security Review"
    assert state["windows_local_isolation"] == state["trusted_human_authorization"] == "NOT VERIFIED"
    assert state["execution_eligible"] is False and state["agent_integration"] == "not_authorized"


def test_determinism_paths_provenance_and_cli(post_root, tmp_path, capsys):
    first, second = tmp_path / "one" / "diagnostic.json", tmp_path / "two" / "diagnostic.json"
    assert diagnostic.main(["--evidence-root", str(post_root), "--output", str(first)]) == 0
    diagnostic.diagnose(post_root, second)
    assert first.read_bytes() == second.read_bytes()
    report = _load(first)
    raw = first.read_text(encoding="utf-8")
    assert raw.endswith("\n") and raw == diagnostic.handoff._json(report)
    assert str(tmp_path) not in raw and "C:/do-not-open" not in raw
    assert "created_at" not in raw and "run_id" not in raw
    assert report["record_type"] == diagnostic.RECORD_TYPE and report["schema_version"] == 1
    assert len(report["provenance"]["validated_source_artifacts"]) == 23
    source = f"{POST_ROOT}/{EXPERIMENTS['A']}/spatial_arrays.npz"
    assert report["provenance"]["validated_source_artifacts"][source] == _pin(post_root / source)
    assert "examples/diagnose_afghanistan_epicentral_zone.py" in report["provenance"]["current_direct_code_artifacts"]


def test_no_source_array_or_file_mutation(post_root):
    evidence = EvidenceTools(post_root, "post_spatial")
    before_arrays = deepcopy(evidence.arrays)
    before_files = {p.relative_to(post_root): p.read_bytes() for p in post_root.rglob("*") if p.is_file()}
    for arrays in evidence.arrays.values():
        for value in arrays.values():
            value.setflags(write=False)
    diagnostic._build_report(evidence)
    for label in ("A", "B"):
        for field, value in before_arrays[label].items():
            np.testing.assert_array_equal(value, evidence.arrays[label][field])
    assert before_files == {p.relative_to(post_root): p.read_bytes() for p in post_root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("relative", [
    f"{POST_ROOT}/{EXPERIMENTS['A']}/spatial_arrays.npz",
    f"{POST_ROOT}/{EXPERIMENTS['B']}/experiment_summary.json",
    f"{POST_ROOT}/{EXPERIMENTS['A']}/selection_record.json",
    f"{PRE_ROOT}/run_record.json",
])
def test_source_integrity_failure_writes_nothing(post_root, tmp_path, relative):
    path = post_root / relative
    path.write_bytes(path.read_bytes() + b"CORRUPTION")
    output = tmp_path / "new" / "diagnostic.json"
    with pytest.raises(ValueError, match="Validated Post-Spatial"):
        diagnostic.diagnose(post_root, output)
    assert not output.parent.exists()


def test_missing_source_is_not_reconstructed(post_root, tmp_path):
    (post_root / POST_ROOT / EXPERIMENTS["B"] / "spatial_arrays.npz").unlink()
    with pytest.raises(ValueError):
        diagnostic.diagnose(post_root, tmp_path / "new" / "report.json")
    assert not (tmp_path / "new").exists()


def test_changed_source_during_calculation_writes_nothing(post_root, tmp_path, monkeypatch):
    original = diagnostic.regional_summary
    def change(*args):
        path = post_root / POST_ROOT / "comparison_report.md"
        path.write_bytes(b"SYNTHETIC concurrent change")
        return original(*args)
    monkeypatch.setattr(diagnostic, "regional_summary", change)
    with pytest.raises(ValueError):
        diagnostic.diagnose(post_root, tmp_path / "new" / "report.json")
    assert not (tmp_path / "new").exists()


def test_no_overwrite_even_before_loading(post_root, tmp_path, monkeypatch):
    output = tmp_path / "diagnostic.json"
    output.write_bytes(b"existing result")
    def no_load(*args):
        raise AssertionError("Existing output must be rejected before loading")
    monkeypatch.setattr(diagnostic, "EvidenceTools", no_load)
    with pytest.raises(FileExistsError):
        diagnostic.diagnose(post_root, output)
    assert output.read_bytes() == b"existing result"


def test_fresh_file_inside_source_directory_is_rejected(post_root):
    output = post_root / POST_ROOT / "new_diagnostic.json"
    with pytest.raises(ValueError, match="outside source"):
        diagnostic.diagnose(post_root, output)
    assert not output.exists()


def test_cli_failure_does_not_echo_host_paths(post_root, tmp_path, capsys):
    (post_root / POST_ROOT / "comparison_summary.json").write_bytes(b"invalid synthetic JSON")
    with pytest.raises(SystemExit) as exc:
        diagnostic.main(["--evidence-root", str(post_root), "--output", str(tmp_path / "no" / "report.json")])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Diagnostic failed" in err and str(tmp_path) not in err


def test_serialization_rejects_nonfinite_numbers():
    with pytest.raises(ValueError):
        diagnostic.serialize_report(dict(value=float("nan")))
