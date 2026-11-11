"""MVP-01 composition tests use synthetic inputs only, never research files."""

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from examples import review_afghanistan_mvp as example
from src.workflow.planning_evidence import evidence_to_json
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_scientific_review_integration import prohibit_protected_calls


@pytest.fixture(scope="module")
def modern_files(tmp_path_factory):
    root = tmp_path_factory.mktemp("synthetic-mvp-modern")
    paths = []
    first = datetime(2022, 5, 7)
    for offset in range(46):
        day = first + timedelta(days=offset)
        tec = np.full((25, 71, 73), 10.0)
        # Six distinct UTC hours avoid changing the later reference quartiles.
        episode_day = (day - datetime(2022, 5, 28)).days
        if 0 <= episode_day < 6:
            tec[episode_day, 48, 50] = 5.0
        tec[24] = 777.0  # Must not replace the next day's own midnight map.
        path = root / f"synthetic_{offset:02d}.npz"
        np.savez_compressed(path, tec=tec,
            epochs=np.array([np.datetime64(day + timedelta(hours=h), "s") for h in range(25)]),
            lat=np.linspace(-87.5, 87.5, 71), lon=np.linspace(-180.0, 180.0, 73),
            source_file=f"synthetic-only-{offset}")
        paths.append(path)
    return paths


@pytest.fixture
def summary_path(tmp_path, historical):
    path = tmp_path / "synthetic-historical-summary.json"
    path.write_text(json.dumps(historical, allow_nan=False) + "\n", encoding="utf-8")
    return path


def read_bundle(output):
    return {path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in output.glob("*.json")}


def test_real_composition_matches_dispatch_and_preserves_both_methods(modern_files, summary_path, tmp_path):
    """Real production functions, with hand-authored synthetic data, not a real event run."""
    output = tmp_path / "review"
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in [*modern_files, summary_path]]
    selected = [0, 1]
    result = example.review(modern_files, summary_path, output, selected_cluster_ids=selected)
    assert result == output / "run_record.json" and selected == [0, 1]
    bundle = read_bundle(output)
    assert set(bundle) == {"scientific_request.json", "temporal_evidence.json", "historical_context.json",
                           "window_proposal.json", "run_record.json"}
    record = bundle["run_record.json"]
    evidence, context, proposal = (bundle[name] for name in (
        "temporal_evidence.json", "historical_context.json", "window_proposal.json"))
    assert evidence["counts"] == dict(positive=0, negative=6, valid_normal=738,
                                      unclassifiable=0, missing_timestamp=0)
    assert evidence["location"]["requested_longitude"] == 69.46
    assert evidence["location"]["grid_latitude"] == 32.5
    assert record["confirmed_event"] == dict(
        event_id="us7000hj3u", time_utc="2022-06-21T20:54:34Z", magnitude=6.0,
        latitude=33.020, longitude=69.464, depth_km=4.0,
        source_reference="https://earthquake.usgs.gov/earthquakes/eventpage/us7000hj3u/executive")
    assert record["scientific_input_coordinates"] == dict(latitude=33.02, longitude=69.46)
    assert record["historical_research_reference"]["method"] == "Vision Model and Selected Window Rule"
    assert record["historical_research_reference"]["window"]["inclusive_hours"] == 120
    assert record["historical_research_reference"]["window"]["end_utc"] == "2022-06-01T23:00:00Z"
    comparison = record["candidate_comparisons"][1]
    assert comparison["candidate_window"] == dict(
        start_utc="2022-05-28T00:00:00Z", end_utc="2022-06-02T23:00:00Z",
        inclusive_hours=144, bounds="inclusive_hourly_samples")
    assert comparison["differs_from_historical_reference"] is True
    assert proposal["anchor_reports"][0]["candidate_window"] is None
    assert proposal["anchor_reports"][1]["anchor_date_utc"] == "2022-05-30"
    assert context["historical_summary"]["inputs"]["tec"]["path"] == "synthetic-tec"
    assert context["historical_summary"]["configuration"]["end_date"] == "2021-12-31"
    assert context["historical_summary"]["clustering"]["temporal_anchors"][0]["n_negative"] == 1
    assert record["review_only"] and record["execution_eligible"] is False
    assert record["selected_execution_window"] is None
    assert record["framework_d_execution"] == "not_performed"
    assert record["windows_local_isolation"] == record["trusted_human_authorization"] == "NOT VERIFIED"
    for name, metadata in record["artifacts"].items():
        raw = (output / name).read_bytes()
        assert metadata == dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    note = (output / "review_note.md").read_text(encoding="utf-8")
    assert "120 hours" in note and "144 hours" in note
    assert "no six-day spatial result is predicted" in note
    series = example.load_temporal_tec_from_modern_gim(
        modern_files, example.START, example.END, latitude=33.02, longitude=69.46, reference_days=15)
    expected = example.dispatch_scientific_request(
        bundle["scientific_request.json"], time_series_id="modern_case_tec", time_series=series,
        historical_summary_id="historical_bc", historical_summary_path=summary_path.resolve())
    assert (evidence, context, proposal) == expected
    assert (output / "temporal_evidence.json").read_text(encoding="utf-8") == evidence_to_json(expected[0])
    assert (output / "historical_context.json").read_text(encoding="utf-8") == evidence_to_json(expected[1])
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in [*modern_files, summary_path]] == before


def test_repeat_and_reordered_files_are_byte_identical(modern_files, summary_path, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    example.review(modern_files, summary_path, first, selected_cluster_ids=[1])
    example.review(modern_files[::-1], summary_path, second, selected_cluster_ids=[1])
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {p.name: p.read_bytes() for p in second.iterdir()}


def test_explicit_empty_selection_abstains(modern_files, summary_path, tmp_path):
    output = tmp_path / "abstention"
    example.review(modern_files, summary_path, output, selected_cluster_ids=[])
    bundle = read_bundle(output)
    assert bundle["scientific_request.json"]["selected_cluster_ids"] == []
    proposal = bundle["window_proposal.json"]
    assert proposal["status"] == "abstained" and proposal["abstention_reason"] == "no_anchors_selected"
    assert all(item["candidate_window"] is None for item in bundle["run_record.json"]["candidate_comparisons"])


@pytest.mark.parametrize("selection", [None, [True], [-1], [0, 0], [0.0], "1"])
def test_invalid_selection_fails_before_acquisition(selection, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid selection reached acquisition")
    monkeypatch.setattr(example, "load_temporal_tec_from_modern_gim", forbidden)
    with pytest.raises(ValueError, match="explicit list"):
        example.review([], tmp_path / "absent.json", tmp_path / "review", selected_cluster_ids=selection)
    assert not (tmp_path / "review").exists()


def test_missing_or_unknown_selection_never_publishes(modern_files, summary_path, tmp_path):
    with pytest.raises(TypeError):
        example.review(modern_files, summary_path, tmp_path / "missing")
    with pytest.raises(ValueError, match="cluster IDs"):
        example.review(modern_files, summary_path, tmp_path / "unknown", selected_cluster_ids=[99])
    assert not (tmp_path / "unknown").exists()


def test_existing_output_rejected_before_loading(monkeypatch, tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    def forbidden(*args, **kwargs):
        pytest.fail("Existing output reached acquisition")
    monkeypatch.setattr(example, "load_temporal_tec_from_modern_gim", forbidden)
    with pytest.raises(FileExistsError):
        example.review([], tmp_path / "absent.json", tmp_path, selected_cluster_ids=[1])
    assert sentinel.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("fault", ["missing_day", "bad_summary", "summary_changed", "modern_changed"])
def test_input_failures_do_not_publish(modern_files, summary_path, monkeypatch, tmp_path, fault):
    files = modern_files.copy()
    output = tmp_path / "review"
    if fault == "missing_day":
        files.pop(10)
    elif fault == "bad_summary":
        summary_path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
    else:
        dispatch = example.dispatch_scientific_request
        if fault == "modern_changed":
            copied = tmp_path / "copied-day.npz"
            copied.write_bytes(files[0].read_bytes())
            files[0] = copied
        def changed(*args, **kwargs):
            result = dispatch(*args, **kwargs)
            changed_path = summary_path if fault == "summary_changed" else copied
            with changed_path.open("ab") as handle:
                handle.write(b" ")
            return result
        monkeypatch.setattr(example, "dispatch_scientific_request", changed)
    with pytest.raises(ValueError):
        example.review(files, summary_path, output, selected_cluster_ids=[1])
    assert not output.exists()


def test_failed_write_retains_partial_bundle_without_complete_index(modern_files, summary_path, monkeypatch, tmp_path):
    original_open = Path.open
    output = tmp_path / "partial"
    def fail(path, *args, **kwargs):
        if path == output / "historical_context.json":
            raise OSError("Synthetic disk failure")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", fail)
    with pytest.raises(OSError, match="disk failure"):
        example.review(modern_files, summary_path, output, selected_cluster_ids=[1])
    assert (output / "scientific_request.json").is_file()
    assert not (output / "run_record.json").exists()
    with pytest.raises(FileExistsError):
        example.review(modern_files, summary_path, output, selected_cluster_ids=[1])


def test_cli_requires_explicit_selection_and_rejects_execution_options(tmp_path):
    base = ["--modern-files", "synthetic.npz", "--historical-summary", "summary.json",
            "--output-dir", str(tmp_path / "review")]
    with pytest.raises(SystemExit) as caught:
        example.main(base)
    assert caught.value.code == 2
    for option in ("--execute", "--stage2", "--overwrite", "--trust"):
        with pytest.raises(SystemExit) as caught:
            example.main(base + ["--cluster-ids", "1", option])
        assert caught.value.code == 2


def test_cli_empty_selection_and_conflict_exit(modern_files, summary_path, tmp_path, capsys):
    output = tmp_path / "cli"
    arguments = ["--modern-files", *map(str, modern_files), "--historical-summary", str(summary_path),
                 "--output-dir", str(output), "--cluster-ids"]
    assert example.main(arguments) == 0
    assert read_bundle(output)["window_proposal.json"]["status"] == "abstained"
    assert "Execution Eligibility: FALSE" in capsys.readouterr().out
    with pytest.raises(SystemExit) as caught:
        example.main(arguments)
    assert caught.value.code == 3


def test_headless_import_has_no_protected_or_plotting_dependencies():
    script = """
import importlib.abc, sys
blocked = ('matplotlib', 'tkinter', '_tkinter', 'cryptography',
    'src.workflow.stage2', 'src.workflow.signed_authorization',
    'src.workflow.authorization_store', 'src.workflow.local_authorizer',
    'src.workflow.planning_approval', 'src.workflow.spatial_adapter',
    'src.workflow.modern_spatial_input_adapter', 'src.workflow.spatial_verification_workflow',
    'src.spatial_verification.spatial_anomaly')
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        assert not fullname.startswith(blocked), fullname
sys.meta_path.insert(0, Reject())
from examples.review_afghanistan_mvp import build_request
assert build_request([])['selected_cluster_ids'] == []
assert not any(name.startswith(blocked) for name in sys.modules)
"""
    completed = subprocess.run([sys.executable, "-B", "-c", script],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
