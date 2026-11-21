"""Synthetic selections and harmless D/plot doubles; no actual D computation."""

from datetime import timedelta
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from examples import compare_afghanistan_mvp_spatial as example
from examples import select_afghanistan_mvp_window as handoff
# Import definitions before the test-only call guard. No detector is run.
from src.workflow import modern_spatial_input_adapter as modern
from src.spatial_verification import spatial_plot
from src.workflow.spatial_summary_export import _maximum_anomaly
from tests.workflow.test_select_afghanistan_mvp_window import bundle, bundle_factory, historical, modern_dir
from tests.workflow.test_scientific_review_integration import prohibit_protected_calls


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def selected(bundle, modern_dir, tmp_path):
    a = handoff.select_window(bundle, modern_dir, tmp_path / "selection_a",
        start_utc="2022-05-28T00:00:00Z", end_utc="2022-06-01T23:00:00Z",
        justification="Reproduce the original published Vision Model and Selected Window Rule result as the historical scientific reference.")
    b = handoff.select_window(bundle, modern_dir, tmp_path / "selection_b", cluster_id=1,
        justification="Evaluate the new evidence-aware negative-anomaly candidate and compare its spatial verification against the original research reference.")
    return a, b, dict(review_bundle=bundle, modern_data_dir=modern_dir, output_dir=tmp_path / "comparison")


@pytest.fixture
def doubles(monkeypatch):
    calls, maps = [], []
    def data(window, files):
        hours = handoff._bounds(window)["inclusive_hours"]
        finite = np.full((71, 73), hours, dtype=np.int64)
        finite[0, 0] = 140 if hours == 144 else 120
        return dict(target_input_finite_counts=finite,
                    initial_reference_input_finite_counts=np.full((71, 73), 360, dtype=np.int64))
    def compute(window, files, *, reference_days, k):
        assert reference_days == 15 and k == 3.0
        hours = handoff._bounds(window)["inclusive_hours"]
        assert len(files) == (20 if hours == 120 else 21)
        assert [p.name for p in files] == sorted(p.name for p in files)
        calls.append((window, files))
        positive, negative = np.zeros((71, 73)), np.zeros((71, 73))
        positive[26, 5:7] = 12 if hours == 120 else 20
        negative[47, 50] = 102 if hours == 120 else 106
        return SimpleNamespace(positive_counts=positive, negative_counts=negative,
            positive_ratio=positive / hours * 100.0, negative_ratio=negative / hours * 100.0,
            latitudes=np.linspace(-87.5, 87.5, 71), longitudes=np.linspace(-180, 180, 73), window_steps=hours)
    def plot(result, **kwargs):
        assert kwargs["grid_orientation"] == "canonical" and kwargs["show_boundaries"] is False
        assert kwargs["epicenter_longitude"] == 69.464 and kwargs["epicenter_latitude"] == 33.020
        assert (kwargs["end_time"] - kwargs["start_time"]) // timedelta(hours=1) + 1 == result.window_steps
        maps.append(kwargs)
        with kwargs["output_path"].open("xb") as handle:
            handle.write(b"synthetic map placeholder, not an actual scientific plot")
        return kwargs["output_path"]
    actual_boundary = example._run_modern_d
    def test_boundary(window, files):
        result, _ = actual_boundary(window, files)  # The Modern function below is replaced, not executed.
        return result, "test_double_only"
    monkeypatch.setattr(modern, "run_spatial_verification_from_modern_gim", compute)
    monkeypatch.setattr(spatial_plot, "save_spatial_anomaly_plot", plot)
    monkeypatch.setattr(example, "_run_modern_d", test_boundary)
    monkeypatch.setattr(example, "_input_validity", data)
    return calls, maps


def test_plan_revalidates_selections_without_computation(selected, doubles, capsys):
    a, b, kwargs = selected
    assert example.main(["plan", "--selection-a", str(a), "--selection-b", str(b),
        "--review-bundle", str(kwargs["review_bundle"]), "--modern-data-dir", str(kwargs["modern_data_dir"]),
        "--output-dir", str(kwargs["output_dir"])]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["framework_d_execution"] == "not_performed" and plan["execution_eligible"] is False
    assert [e["window"]["inclusive_hours"] for e in plan["experiments"].values()] == [120, 144]
    assert [len(e["input_files"]) for e in plan["experiments"].values()] == [20, 21]
    assert plan["cluster_0_status"] == "valid_candidate_not_selected_for_this_comparison"
    assert not kwargs["output_dir"].exists() and doubles == ([], [])


def test_stubbed_dual_outputs_serialization_and_comparison(selected, doubles):
    a, b, kwargs = selected
    before = (a.read_bytes(), b.read_bytes())
    output = example.run_comparison(a, b, **kwargs)
    comparison = _load(output)
    assert comparison["framework_d_execution"] == "test_double_only"
    assert comparison["execution_eligible"] is False
    summaries = list(comparison["experiments"].values())
    assert summaries[0]["historical_reference_checks"]["all_match"] is True
    assert summaries[1]["historical_reference_checks"] is None
    assert [s["ratio_denominator"] for s in summaries] == [120, 144]
    assert summaries[0]["spatial_anomalies"]["negative"]["maximum_grid_points"] == [dict(latitude=30.0, longitude=70.0)]
    assert summaries[0]["spatial_anomalies"]["positive"]["maximum_grid_points"] == [
        dict(latitude=-22.5, longitude=-155.0), dict(latitude=-22.5, longitude=-150.0)]
    assert all(s["effective_detector_valid_counts"] is None for s in summaries)
    for name, summary in comparison["experiments"].items():
        directory = output.parent / name
        for artifact in summary["artifacts"].values():
            raw = (directory / artifact["path"]).read_bytes()
            assert handoff._metadata(raw) == {k: artifact[k] for k in ("size_bytes", "sha256")}
        assert (directory / "selection_record.json").read_bytes() == before[0 if name == example._EXPERIMENTS[0] else 1]
        with np.load(directory / "spatial_arrays.npz", allow_pickle=False) as arrays:
            assert arrays["negative_counts"][47, 50] == (102 if name == example._EXPERIMENTS[0] else 106)
            assert arrays["latitudes"][47] == 30.0 and arrays["window_steps"] == summary["ratio_denominator"]
    with np.load(output.parent / "cellwise_differences.npz", allow_pickle=False) as delta:
        assert delta["negative_counts_b_minus_a"][47, 50] == 4
        assert np.isclose(delta["negative_ratio_b_minus_a"][47, 50], 106 / 144 * 100 - 85)
        assert delta["ratio_denominator_b_minus_a"] == 24
        assert delta["target_input_finite_counts_b_minus_a"][0, 0] == 20
        assert not delta["initial_reference_input_finite_counts_b_minus_a"].any()
    assert len(doubles[0]) == 2 and len(doubles[1]) == 4
    assert (a.read_bytes(), b.read_bytes()) == before
    assert "test_double_only" in (output.parent / "comparison_report.md").read_text(encoding="utf-8")


def test_repeat_metadata_and_numeric_files_are_deterministic(selected, doubles):
    a, b, kwargs = selected
    first = example.run_comparison(a, b, **kwargs).parent
    second = example.run_comparison(a, b, **{**kwargs, "output_dir": first.parent / "repeat"}).parent
    for path in first.rglob("*"):
        if path.is_file() and path.name != "comparison_plan.json":
            assert path.read_bytes() == (second / path.relative_to(first)).read_bytes(), path
    assert len(doubles[0]) == 4


@pytest.mark.parametrize("fault", ["duration", "parent", "wrong_cluster"])
def test_changed_selection_rejected_before_boundary(selected, doubles, fault):
    a, b, kwargs = selected
    value = _load(b)
    if fault == "duration":
        value["window"]["inclusive_hours"] = 120
    elif fault == "parent":
        value["parent_review_bundle"]["run_record"]["sha256"] = "0" * 64
    else:
        value["cluster_id"] = 0
    b.write_text(handoff._json(value), encoding="utf-8")
    with pytest.raises(ValueError):
        example.run_comparison(a, b, **kwargs)
    assert doubles[0] == [] and not kwargs["output_dir"].exists()


@pytest.mark.parametrize("fault", ["missing", "modified"])
def test_missing_or_modified_input_rejected(selected, doubles, fault):
    a, b, kwargs = selected
    path = kwargs["modern_data_dir"] / "codg1530.22i.npz"
    if fault == "missing":
        path.unlink()
    else:
        path.write_bytes(b"changed synthetic source")
    with pytest.raises(ValueError, match="Modern inputs|input inventory"):
        example.run_comparison(a, b, **kwargs)
    assert doubles[0] == [] and not kwargs["output_dir"].exists()


def test_source_change_after_diagnostics_is_caught_immediately_before_d(selected, doubles, monkeypatch):
    a, b, kwargs = selected
    diagnostics = example._input_validity
    def changed(window, files):
        result = diagnostics(window, files)
        files[0].write_bytes(b"changed after diagnostics")
        return result
    monkeypatch.setattr(example, "_input_validity", changed)
    with pytest.raises(ValueError, match="Modern inputs"):
        example.run_comparison(a, b, **kwargs)
    assert doubles[0] == []
    failure = _load(kwargs["output_dir"] / example._EXPERIMENTS[0] / "failure.json")
    assert failure["framework_d_execution"] == "not_performed"
    assert not (kwargs["output_dir"] / "comparison_summary.json").exists()


def test_no_overwrite_or_source_directory_outputs(selected, doubles):
    a, b, kwargs = selected
    target = kwargs["output_dir"]
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    with pytest.raises(FileExistsError):
        example.run_comparison(a, b, **kwargs)
    with pytest.raises(ValueError):
        example.run_comparison(a, b, **{**kwargs, "output_dir": a.parent / "nested"})
    assert sentinel.read_text(encoding="utf-8") == "unchanged" and doubles[0] == []


def test_input_availability_is_not_a_detector_denominator(monkeypatch):
    from src.data import modern_gim_bridge
    window = handoff._window("2022-05-28T00:00:00Z", "2022-06-01T23:00:00Z")
    data = np.ones((480, 71, 73))
    data[:360, 0, 0] = np.nan
    data[360, 0, 1] = np.nan
    def load(files, start, end, *, reference_days):
        assert reference_days == 15 and start.tzinfo is None and end.tzinfo is None
        return SimpleNamespace(tec=data)
    monkeypatch.setattr(modern_gim_bridge, "load_modern_gim_window", load)
    validity = example._input_validity(window, ())
    assert validity["target_input_finite_counts"][0, 0] == 120
    assert validity["initial_reference_input_finite_counts"][0, 0] == 0
    assert validity["target_input_finite_counts"][0, 1] == 119
    assert "NOT effective" in example.__doc__


def test_unsigned_validity_differences_do_not_wrap():
    a = dict(latitudes=np.linspace(-87.5, 87.5, 71), longitudes=np.linspace(-180, 180, 73))
    for key in ("positive_counts", "negative_counts", "positive_ratio", "negative_ratio",
                "target_input_finite_counts", "initial_reference_input_finite_counts", "ratio_denominator"):
        a[key] = np.array(120, dtype=np.uint64)
    b = {**a, "target_input_finite_counts": np.array(100, dtype=np.uint64),
         "positive_counts": np.array(100, dtype=np.uint64), "ratio_denominator": np.array(144)}
    delta = example._differences(a, b)
    assert delta["target_input_finite_counts_b_minus_a"] == -20
    assert delta["positive_counts_b_minus_a"] == -20
    assert delta["ratio_denominator_b_minus_a"] == 24


def test_fresh_plan_import_has_no_protected_or_plotting_dependency():
    script = """
import importlib.abc, sys
blocked = ('matplotlib', 'cryptography', 'src.workflow.stage2', 'src.workflow.signed_authorization',
    'src.workflow.authorization_store', 'src.workflow.local_authorizer', 'src.workflow.planning_approval',
    'src.workflow.spatial_adapter', 'src.workflow.modern_spatial_input_adapter',
    'src.workflow.spatial_verification_workflow', 'src.spatial_verification.spatial_anomaly')
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        assert not fullname.startswith(blocked), fullname
sys.meta_path.insert(0, Reject())
from examples.compare_afghanistan_mvp_spatial import plan_comparison
assert not any(name.startswith(blocked) for name in sys.modules)
"""
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
