"""Synthetic saved evidence + inert daily files; no D or authorization runtime."""

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from examples import review_afghanistan_mvp as mvp01
from examples import select_afghanistan_mvp_window as example
from src.temporal_anomaly.tec_timeseries import TECTimeSeries
from src.temporal_anomaly.temporal_anomaly import TemporalAnomalyResult
from src.workflow.planning_evidence import build_historical_bc_evidence, build_temporal_evidence, evidence_to_json
from src.workflow.window_planning import plan_anchor_based_daily_windows
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_scientific_review_integration import prohibit_protected_calls


def _dump(path, value):
    path.write_bytes(mvp01._json(value).encode("utf-8"))


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _repin(bundle, name, value):
    _dump(bundle / name, value)
    record = _load(bundle / "run_record.json")
    raw = (bundle / name).read_bytes()
    record["artifacts"][name] = dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    _dump(bundle / "run_record.json", record)


def _original_sources():
    payload = b"synthetic inventory placeholder"
    result = []
    for offset in range(46):
        day = datetime(2022, 5, 7) + timedelta(days=offset)
        name = f"codg{day.timetuple().tm_yday:03d}0.22i.npz"
        result.append(dict(path=f"C:/do-not-open/{name}", size_bytes=len(payload),
                           sha256=hashlib.sha256(payload).hexdigest()))
    return result


@pytest.fixture
def bundle_factory(tmp_path, historical):
    def make(name="bundle", selected_ids=None, original_sources=None):
        # Hand-authored classifications/statistics, not a fresh observed A run.
        selected_ids = [0, 1] if selected_ids is None else selected_ids
        epochs = np.array([mvp01.START + timedelta(hours=i) for i in range(744)], dtype=object)
        observed, codes = np.full(744, 10.0), np.zeros(744, dtype=np.int8)
        for first, count, hour, value, code in (
            (datetime(2022, 5, 28), 6, 6, 6.0, -1),
            (datetime(2022, 6, 11), 3, 8, 14.0, 1),
        ):
            for day in range(count):
                index = (first + timedelta(days=day, hours=hour) - mvp01.START) // timedelta(hours=1)
                observed[index], codes[index] = value, code
        result = TemporalAnomalyResult(epochs=epochs, observed=observed, anomaly=codes,
            q1=np.full(744, 9.0), median=np.full(744, 10.0), q3=np.full(744, 11.0),
            lower_bound=np.full(744, 7.0), upper_bound=np.full(744, 13.0),
            reference_days=15, threshold_multiplier=3.0, min_reference_samples=15)
        series = TECTimeSeries(epochs, observed, 33.02, 69.46, 32.5, 70.0, 48, 50)
        sources = _original_sources() if original_sources is None else original_sources
        provenance = dict(sources=[dict(identity=s["path"], sha256=s["sha256"]) for s in sources],
                          processing_history="Synthetic saved evidence; no observed research input.")
        request = mvp01.build_request(selected_ids, provenance=provenance)
        temporal = build_temporal_evidence(result, case_id=mvp01.CASE_ID,
            expected_start=mvp01.START, expected_end=mvp01.END, input_time_convention="naive_utc",
            time_series=series, provenance=dict(processing_history=provenance["processing_history"],
                sources=provenance["sources"] + [dict(identity=example._COMPUTED_SOURCE, sha256="e" * 64)]))
        context = build_historical_bc_evidence(historical)
        summary = dict(path="C:/do-not-open/summary.json", size_bytes=123, sha256="c" * 64)
        context["summary_artifact"] = dict(identity=summary["path"], size_bytes=123, sha256=summary["sha256"],
                                            hash_verification="computed_from_read_bytes")
        proposal = plan_anchor_based_daily_windows(temporal, context, case_event=request["case_event"],
            selected_cluster_ids=selected_ids, mode="retrospective")
        comparisons = mvp01._comparisons(proposal)
        artifacts = {"scientific_request.json": mvp01._json(request),
            "temporal_evidence.json": evidence_to_json(temporal),
            "historical_context.json": evidence_to_json(context),
            "window_proposal.json": mvp01._json(proposal), "review_note.md": mvp01._note(proposal, comparisons)}
        record = dict(record_type="afghanistan_mvp_review_run", schema_version=1, case_id=mvp01.CASE_ID,
            review_only=True, execution_eligible=False, framework_d_execution="not_performed",
            windows_local_isolation="NOT VERIFIED", trusted_human_authorization="NOT VERIFIED",
            selected_execution_window=None, confirmed_event=dict(mvp01.EVENT),
            scientific_input_coordinates=dict(latitude=33.02, longitude=69.46), selected_cluster_ids=selected_ids,
            historical_research_reference=dict(method="Vision Model and Selected Window Rule",
                window=dict(mvp01.REFERENCE_WINDOW), selected_for_execution=False),
            candidate_comparisons=comparisons, inputs=dict(modern_daily_files=sources, historical_summary=summary),
            input_hashes_rechecked_after_review=True, event_metadata_basis="Synthetic fixture declaration only",
            environment=dict(python="synthetic", numpy="synthetic"), code_sha256={"C:/do-not-open/code.py": "d" * 64},
            artifacts={key: dict(size_bytes=len(text.encode("utf-8")),
                                  sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
                       for key, text in artifacts.items()})
        root = tmp_path / name
        root.mkdir()
        for key, text in artifacts.items():
            (root / key).write_bytes(text.encode("utf-8"))
        _dump(root / "run_record.json", record)
        return root
    return make


@pytest.fixture
def bundle(bundle_factory):
    return bundle_factory()


@pytest.fixture
def modern_dir(tmp_path):
    root = tmp_path / "modern"
    root.mkdir()
    for offset in range(46):
        day = datetime(2022, 5, 7) + timedelta(days=offset)
        # Inventory presence only: intentionally not NPZ data or a scientific substitute.
        (root / f"codg{day.timetuple().tm_yday:03d}0.22i.npz").write_bytes(b"synthetic inventory placeholder")
    (root / "unexpected.txt").write_text("inert", encoding="utf-8")
    return root


@pytest.mark.parametrize("cluster_id,hours,first,last,days", [
    (0, 72, "2022-06-11T00:00:00Z", "2022-06-13T23:00:00Z", 18),
    (1, 144, "2022-05-28T00:00:00Z", "2022-06-02T23:00:00Z", 21),
])
def test_exact_candidate_and_binding(bundle, modern_dir, tmp_path, cluster_id, hours, first, last, days):
    before = {p.name: p.read_bytes() for p in bundle.iterdir()}
    output = example.select_window(bundle, modern_dir, tmp_path / "selection", cluster_id=cluster_id)
    assert output.name == "selection_record.json"
    record = _load(output)
    proposal = _load(bundle / "window_proposal.json")
    assert record["selection_mode"] == "candidate" and record["cluster_id"] == cluster_id
    assert record["window"] == dict(start_utc=first, end_utc=last, inclusive_hours=hours)
    assert record["selected_candidate"] == proposal["anchor_reports"][cluster_id]
    assert record["scientific_rationale"].strip()
    parent = record["parent_review_bundle"]
    assert parent["directory"] == str(bundle)
    assert parent["run_record"]["sha256"] == hashlib.sha256(before["run_record.json"]).hexdigest()
    assert parent["artifacts"] == _load(bundle / "run_record.json")["artifacts"]
    inventory = record["modern_gim_inputs"]
    assert inventory["reference"]["inclusive_hours"] == 360 and inventory["reference_days"] == 15
    assert len(inventory["required_daily_files"]) == days and inventory["required_files_present"] is True
    assert inventory["original_sources_consistent"] is True and inventory["source_integrity_ready"] is True
    assert inventory["source_consistency_issues"] == []
    assert all(item["source_consistency"] == "matched" for item in inventory["required_daily_files"])
    assert inventory["recheck_before_computation_required"] is True
    assert inventory["grid_orientation"] == "canonical" and inventory["npz_content_validation"] == "not_performed"
    assert "unexpected.txt" in inventory["extra_directory_entries"]
    assert record["review_only"] and record["execution_eligible"] is False
    assert record["framework_d_execution"] == "not_performed"
    assert record["trusted_human_authorization"] == record["windows_local_isolation"] == "NOT VERIFIED"
    assert {p.name: p.read_bytes() for p in bundle.iterdir()} == before


def test_independent_reference_preserves_candidate_difference(bundle, modern_dir, tmp_path):
    output = example.select_window(bundle, modern_dir, tmp_path / "independent",
        start_utc="2022-05-28T00:00:00+00:00", end_utc="2022-06-01T23:00:00Z",
        justification="Compare the original Vision Model and Selected Window Rule reference.")
    record = _load(output)
    assert record["selection_mode"] == "independent" and record["cluster_id"] is None
    assert record["selected_candidate"] is None
    assert record["historical_reference_comparison"]["matches_selected_window"] is True
    assert record["historical_reference_comparison"]["duration_difference_hours"] == 0
    assert record["candidate_comparisons"][1]["candidate_window"]["inclusive_hours"] == 144
    assert record["candidate_comparisons"][1]["matches_selected_window"] is False
    inventory = record["modern_gim_inputs"]
    assert len(inventory["required_daily_files"]) == 20
    assert inventory["reference"]["start_utc"] == "2022-05-13T00:00:00Z"
    assert inventory["reference"]["end_utc"] == "2022-05-27T23:00:00Z"
    assert inventory["source_integrity_ready"] is True


def test_modified_daily_file_with_same_name_is_not_source_ready(bundle, modern_dir):
    path = modern_dir / "codg1530.22i.npz"
    path.write_bytes(b"modified synthetic input")
    result = example.inspect_handoff(bundle, modern_dir)
    inventory = result["candidate_inventories"][1]["inventory"]
    assert inventory["required_files_present"] is True
    assert inventory["original_sources_consistent"] is False and inventory["source_integrity_ready"] is False
    assert inventory["source_consistency_issues"] == [dict(filename=path.name, reason="sha256_mismatch",
        source_identity=f"C:/do-not-open/{path.name}", expected_sha256=_original_sources()[26]["sha256"],
        current_sha256=hashlib.sha256(path.read_bytes()).hexdigest())]
    assert result["historical_reference_inventory"]["source_integrity_ready"] is True  # Does not need June 2.
    assert inventory["npz_content_validation"] == "not_performed"
    assert inventory["numerical_correctness"] == "not_verified"
    assert result["execution_eligible"] is False


@pytest.mark.parametrize("fault", ["missing", "ambiguous"])
def test_missing_or_ambiguous_original_identity_not_source_ready(bundle_factory, modern_dir, fault):
    sources = _original_sources()
    original = sources[26]
    if fault == "missing":
        sources.pop(26)
    else:
        sources.append({**original, "path": r"D:\other-origin\CODG1530.22I.NPZ"})
    bundle = bundle_factory(original_sources=sources)
    result = example.inspect_handoff(bundle, modern_dir)
    inventory = result["candidate_inventories"][1]["inventory"]
    reason = "missing_source_identity" if fault == "missing" else "ambiguous_source_identity"
    issue = inventory["source_consistency_issues"][0]
    assert issue["filename"] == "codg1530.22i.npz" and issue["reason"] == reason
    if fault == "ambiguous":
        assert issue["source_identities"] == [original["path"], sources[-1]["path"]]
    assert inventory["required_files_present"] is True and inventory["source_integrity_ready"] is False
    assert inventory["original_sources_consistent"] is False


def test_source_filename_matching_is_lexical_across_path_styles(bundle_factory, modern_dir):
    sources = _original_sources()
    sources[26]["path"] = r"D:\do-not-open\CODG1530.22I.NPZ"
    bundle = bundle_factory(original_sources=sources)
    inventory = example.inspect_handoff(bundle, modern_dir)["candidate_inventories"][1]["inventory"]
    assert inventory["original_sources_consistent"] is True
    assert inventory["required_daily_files"][-1]["original_source"]["path"] == sources[26]["path"]


@pytest.mark.parametrize("start,end", [
    ("2022-05-21T23:00:00Z", "2022-05-22T00:00:00Z"),
    ("0002-01-20T00:00:00Z", "2022-06-01T23:00:00Z"),
    ("2022-06-21T20:00:00Z", "2022-06-22T00:00:00Z"),
])
def test_outside_analysis_rejected_before_inventory(bundle, modern_dir, tmp_path, monkeypatch, start, end):
    def forbidden(*args):
        pytest.fail("Out-of-coverage window reached the daily inventory")
    monkeypatch.setattr(example, "_inventory", forbidden)
    with pytest.raises(ValueError, match="coverage|precede"):
        example.select_window(bundle, modern_dir, tmp_path / "outside", start_utc=start, end_utc=end,
                              justification="Synthetic boundary test.")
    assert not (tmp_path / "outside").exists()


def test_analysis_start_allowed_with_reference_before_analysis(bundle, modern_dir, tmp_path):
    record = _load(example.select_window(bundle, modern_dir, tmp_path / "boundary",
        start_utc="2022-05-22T00:00:00Z", end_utc="2022-05-22T00:00:00Z",
        justification="Explicit first analysis sample; reference history remains separate."))
    assert record["window"]["inclusive_hours"] == 1
    assert record["modern_gim_inputs"]["reference"]["start_utc"] == "2022-05-07T00:00:00Z"
    assert record["modern_gim_inputs"]["source_integrity_ready"] is True


@pytest.mark.parametrize("choice", [{}, {"cluster_id": True}, {"cluster_id": -1}, {"cluster_id": 0.0},
    {"cluster_id": 99}, {"cluster_id": 0, "start_utc": "2022-05-28T00:00:00Z"},
    {"start_utc": "2022-05-28T00:00:00Z", "end_utc": "2022-06-01T23:00:00Z"},
    {"start_utc": "2022-05-28T00:00:00Z", "end_utc": "2022-06-01T23:00:00Z", "justification": "  "}])
def test_no_default_or_invalid_selection(bundle, modern_dir, tmp_path, choice):
    with pytest.raises(ValueError):
        example.select_window(bundle, modern_dir, tmp_path / "invalid", **choice)
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("start,end", [
    ("2022-05-28T00:00:00", "2022-06-01T23:00:00Z"),
    ("2022-05-28T00:00:00+08:00", "2022-06-01T23:00:00Z"),
    ("2022-05-28T00:30:00Z", "2022-06-01T23:00:00Z"),
    ("2022-06-02T00:00:00Z", "2022-06-01T23:00:00Z"),
    ("2022-06-21T21:00:00Z", "2022-06-21T23:00:00Z"),
])
def test_invalid_or_post_event_bounds(bundle, modern_dir, tmp_path, start, end):
    with pytest.raises(ValueError):
        example.select_window(bundle, modern_dir, tmp_path / "invalid", start_utc=start, end_utc=end,
                              justification="Explicit synthetic test rationale.")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("selected_ids,cluster_id", [([], 0), ([0], 1)])
def test_abstained_or_unrequested_candidate_not_eligible(bundle_factory, modern_dir, tmp_path, selected_ids, cluster_id):
    bundle = bundle_factory(selected_ids=selected_ids)
    with pytest.raises(ValueError, match="eligible saved candidate"):
        example.select_window(bundle, modern_dir, tmp_path / "selection", cluster_id=cluster_id)


@pytest.mark.parametrize("fault", ["missing", "corrupt", "manifest_path", "proposal", "stale_evidence",
    "case", "event", "parameters", "source_binding", "duplicate_key", "run_metadata"])
def test_bad_bundle_rejected_even_with_rehashed_artifact(bundle, modern_dir, tmp_path, fault):
    if fault == "missing":
        (bundle / "review_note.md").unlink()
    elif fault == "corrupt":
        with (bundle / "temporal_evidence.json").open("ab") as handle:
            handle.write(b" ")
    elif fault in ("manifest_path", "case", "run_metadata"):
        record = _load(bundle / "run_record.json")
        if fault == "manifest_path":
            record["artifacts"]["../../unapproved.txt"] = record["artifacts"].pop("review_note.md")
        elif fault == "case":
            record["case_id"] = "other_case"
        else:
            record["environment"] = None
        _dump(bundle / "run_record.json", record)
    elif fault == "duplicate_key":
        with (bundle / "run_record.json").open("wb") as handle:
            handle.write(b'{"case_id":"one","case_id":"two"}')
    else:
        name = "window_proposal.json" if fault in ("proposal", "stale_evidence") else (
            "scientific_request.json" if fault == "event" else "temporal_evidence.json")
        value = _load(bundle / name)
        if fault == "proposal":
            value["anchor_reports"][1]["candidate_window"]["end_utc"] = "2022-06-01T23:00:00Z"
        elif fault == "stale_evidence":
            value["evidence_references"]["temporal"]["content_sha256"] = "0" * 64
        elif fault == "event":
            value["case_event"]["event_id"] = "older_solution"
        elif fault == "parameters":
            value["parameters"]["reference_days"] = 14
        else:
            value["provenance"]["sources"][0]["sha256"] = "f" * 64
        _repin(bundle, name, value)
    with pytest.raises(ValueError):
        example.select_window(bundle, modern_dir, tmp_path / "selection", cluster_id=1)
    assert not (tmp_path / "selection").exists()


def test_missing_daily_file_is_explicitly_incomplete(bundle, modern_dir, tmp_path):
    (modern_dir / "codg1530.22i.npz").unlink()  # June 2, required by cluster 1.
    record = _load(example.select_window(bundle, modern_dir, tmp_path / "selection", cluster_id=1))
    assert record["modern_gim_inputs"]["missing_files"] == ["codg1530.22i.npz"]
    assert record["modern_gim_inputs"]["required_files_present"] is False
    assert record["execution_eligible"] is False


def test_wrong_daily_file_type_is_not_ready(bundle, modern_dir):
    path = modern_dir / "codg1530.22i.npz"
    path.unlink()
    path.mkdir()
    result = example.inspect_handoff(bundle, modern_dir)
    inventory = result["candidate_inventories"][1]["inventory"]
    assert inventory["required_files_present"] is False
    assert inventory["invalid_files"] == [dict(filename=path.name, reason="not_regular_file")]


def test_read_only_inspect_and_recorded_paths_never_followed(bundle, modern_dir, monkeypatch):
    from src.workflow import temporal_workflow
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        assert path.is_relative_to(bundle) or path.is_relative_to(modern_dir), path
        return original_open(path, *args, **kwargs)
    def forbidden(*args, **kwargs):
        pytest.fail("Handoff attempted A detection or request dispatch")
    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr(mvp01, "dispatch_scientific_request", forbidden)
    monkeypatch.setattr(temporal_workflow, "detect_temporal_anomalies", forbidden)
    result = example.inspect_handoff(bundle, modern_dir)
    assert result["selection_made"] is False
    assert len(result["candidate_inventories"]) == 2
    assert result["historical_reference_inventory"]["target"]["inclusive_hours"] == 120
    assert not (bundle / "selection_record.json").exists()


def test_no_overwrite_parent_or_data_mutation(bundle, modern_dir, tmp_path):
    for destination in (tmp_path, bundle / "child", modern_dir / "child"):
        with pytest.raises((FileExistsError, ValueError)):
            example.select_window(bundle, modern_dir, destination, cluster_id=1)
    assert not (bundle / "child").exists() and not (modern_dir / "child").exists()


def test_deterministic_record(bundle, modern_dir, tmp_path):
    first = example.select_window(bundle, modern_dir, tmp_path / "one", cluster_id=1, justification="Chosen explicitly.")
    second = example.select_window(bundle, modern_dir, tmp_path / "two", cluster_id=1, justification="Chosen explicitly.")
    assert first.read_bytes() == second.read_bytes()


def test_bundle_change_during_inventory_rejected(bundle, modern_dir, tmp_path, monkeypatch):
    original = example._inventory
    def changed(*args):
        result = original(*args)
        with (bundle / "review_note.md").open("ab") as handle:
            handle.write(b"changed")
        return result
    monkeypatch.setattr(example, "_inventory", changed)
    with pytest.raises(ValueError, match="bundle changed"):
        example.select_window(bundle, modern_dir, tmp_path / "selection", cluster_id=1)
    assert not (tmp_path / "selection").exists()


def test_cli_explicit_modes_only(bundle, modern_dir, tmp_path, capsys):
    base = ["--review-bundle", str(bundle), "--modern-data-dir", str(modern_dir)]
    for extra in ([], ["--cluster-id", "0", "--start-utc", "2022-05-28T00:00:00Z"],
                  ["--inspect", "--output-dir", str(tmp_path / "forbidden")], ["--execute"]):
        with pytest.raises(SystemExit) as caught:
            example.main(base + extra)
        assert caught.value.code == 2
    assert example.main(base + ["--inspect"]) == 0
    assert '"selection_made": false' in capsys.readouterr().out
    output = tmp_path / "selection"
    assert example.main(base + ["--cluster-id", "1", "--output-dir", str(output)]) == 0
    with pytest.raises(SystemExit) as caught:
        example.main(base + ["--cluster-id", "1", "--output-dir", str(output)])
    assert caught.value.code == 3


def test_fresh_import_excludes_all_protected_modules():
    script = """
import importlib.abc, sys
blocked = ('matplotlib', 'tkinter', 'cryptography', 'src.workflow.stage2',
    'src.workflow.planning_approval', 'src.workflow.signed_authorization',
    'src.workflow.authorization_store', 'src.workflow.local_authorizer',
    'src.workflow.spatial_adapter', 'src.workflow.modern_spatial_input_adapter',
    'src.workflow.spatial_verification_workflow', 'src.spatial_verification.spatial_anomaly')
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        assert not fullname.startswith(blocked), fullname
sys.meta_path.insert(0, Reject())
from examples.select_afghanistan_mvp_window import inspect_handoff, select_window
assert not any(name.startswith(blocked) for name in sys.modules)
"""
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
