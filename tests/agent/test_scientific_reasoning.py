"""Synthetic saved observations only. Tools cannot execute detectors or Stage 2."""

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import socket

import numpy as np
import pytest

from examples.investigate_scientific_reasoning import offline_demo, write_json
from src.agent.follow_up_experiments import window_comparison_proposal
from src.agent.scientific_evidence_tools import EvidenceTools, compact, strict_json
from src.agent.scientific_review_agent import (
    AssessmentValidationError, FakeModel, _abstention, _check_assessment,
    _submission_tool, run_agent,
)
from src.workflow.space_weather_evidence import build_space_weather_report, metadata
from src.workflow.window_sensitivity import build_window_diagnostic, load_hourly_snapshot
from tests.agent.test_scientific_review_agent import pre_root, post_root
from tests.workflow.test_select_afghanistan_mvp_window import bundle_factory, modern_dir
from tests.workflow.test_planning_evidence import historical


@pytest.fixture
def reasoning_root(post_root):
    evidence = EvidenceTools(post_root, "post_spatial")
    base, ext = (evidence.summaries[label]["window"] for label in ("A", "B"))
    a = dict(epochs=np.arange(1653696000, 1653696000 + 144 * 3600, 3600, dtype=np.int64),
             latitudes=evidence.arrays["A"]["latitudes"], longitudes=evidence.arrays["A"]["longitudes"])
    for p in ("positive", "negative"):
        flags = np.zeros((144, 5183), dtype=np.int8)
        for index, value in enumerate(evidence.arrays["A"][p + "_counts"].ravel()):
            flags[:int(value), index] = 1
            extra = int(evidence.arrays["B"][p + "_counts"].ravel()[index] - value)
            flags[120:120 + extra, index] = 1
        a[p] = flags
    for key in ("target_finite", "positive_finite", "negative_finite", "reference_finite_counts"):
        a[key] = np.full((144, 5183), 15 if key == "reference_finite_counts" else 1, dtype=np.uint8)
    folder = post_root / "reasoning" / "window"
    folder.mkdir(parents=True)
    np.savez_compressed(folder / "hourly_snapshot.npz", **a)
    d = build_window_diagnostic(a, base, ext, case_id="afghanistan_2022", selected_cells=[dict(latitude=33.02, longitude=69.464)])
    report = dict(record_type="saved_window_investigation", schema_version=1, case_id="afghanistan_2022",
                  event=evidence.bundle["record"]["confirmed_event"], diagnostic=d,
                  hourly_snapshot=dict(artifact="hourly_snapshot.npz", **metadata((folder / "hourly_snapshot.npz").read_bytes())),
                  source_evidence=dict(evidence.sources), saved_comparison_checks=dict(baseline=True, extended=True),
                  original_inputs={s["filename"]: {k: s[k] for k in ("sha256", "size_bytes")} for s in evidence.summaries["B"]["input_files"]})
    pin = write_json(folder / "window.json", report)
    declarations = dict(window_sensitivity=dict(artifact="reasoning/window/window.json", **pin))
    stamp = datetime(2022, 5, 28)
    rows = [SimpleNamespace(timestamp=stamp + timedelta(hours=h), year=2022, doy=148, hour=h,
                            values=dict(kp=2.7, kp_x10=27.0, dst=-17.0, f107=110.6)) for h in range(3)]
    weather = build_space_weather_report(rows, ext, case_id="afghanistan_2022", provenance=dict(
        provider="NASA OMNIWeb", product="OMNI2 hourly", retrieval_performed=False,
        input=dict(identity="synthetic.csv", sha256="a" * 64, size_bytes=100),
        toolkit=dict(identity="omni_downloader.py", sha256="b" * 64, size_bytes=100),
        service_url="https://omniweb.gsfc.nasa.gov/cgi/nx1.cgi"))
    folder = post_root / "reasoning" / "weather"
    folder.mkdir()
    pin = write_json(folder / "weather.json", weather)
    declarations["space_weather"] = dict(artifact="reasoning/weather/weather.json", **pin)
    return post_root, declarations


def call(name, args=None, identity="call"):
    return dict(name=name, arguments=compact(args or {}), call_id=identity)


def assessment(data, result_id="R1"):
    final = _abstention("Both windows warrant controlled comparison before human selection.")
    pointer = "/data/baseline/inclusive_hours"
    final["observed_facts"] = [dict(result_id=result_id, pointer=pointer, value_json=compact(data["baseline"]["inclusive_hours"]))]
    final["follow_up_experiments"] = [window_comparison_proposal(data, result_id)]
    final["recommendation"].update(action="propose_follow_up", evidence=[dict(result_id=result_id, pointer=pointer)])
    return final


def test_read_only_tool_calls_exact_hours_cells_and_weather(reasoning_root, monkeypatch):
    from src.spatial_verification import spatial_anomaly
    from src.workflow import modern_spatial_input_adapter, stage2_runner
    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only Agent attempted scientific computation or network")
    monkeypatch.setattr(spatial_anomaly, "compute_hourly_spatial_anomalies", forbidden)
    monkeypatch.setattr(spatial_anomaly, "compute_spatial_anomalies", forbidden)
    monkeypatch.setattr(modern_spatial_input_adapter, "run_spatial_verification_from_modern_gim", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    root, declarations = reasoning_root
    tools = EvidenceTools(root, "post_spatial", reasoning_bindings=declarations)
    assert tools.status["window_sensitivity"] == tools.status["space_weather"] == "validated_snapshot"
    names = {t["name"] for t in tools.tool_definitions()}
    assert {"get_window_contribution_summary", "inspect_window_contribution_hours", "get_space_weather_summary"} <= names
    summary = tools.call("get_window_contribution_summary", "{}")
    assert summary["ok"], summary
    assert summary["data"]["additional_utc_hours"][0] == "2022-06-02T00:00:00Z"
    assert len(summary["data"]["additional_utc_hours"]) == 24
    cell = tools.call("inspect_window_contribution_cell", compact(dict(latitude=33.02, longitude=69.464)))["data"]
    assert cell["actual_grid"]["latitude"] == 32.5
    assert cell["segments"]["additional"]["negative"]["anomaly_grid_hours"] == 1
    hourly = tools.call("inspect_window_contribution_hours", compact(dict(start_utc="2022-06-02T00:00:00Z", end_utc="2022-06-02T23:00:00Z", latitude=30, longitude=70)))
    assert hourly["ok"], hourly
    assert hourly["data"]["rows"][0]["cell"]["negative"] == 1
    assert hourly["data"]["rows"][1]["cell"]["negative"] == 0
    weather = tools.call("inspect_space_weather_interval", compact(dict(start_utc="2022-05-28T00:00:00Z", end_utc="2022-05-28T03:00:00Z")))
    assert weather["data"]["rows"][0]["values"]["kp"] == 2.7
    assert weather["data"]["rows"][3]["values"]["kp"] is None
    assert tools.call("get_evidence_inventory", "{}")["data"]["external_indices"]["Kp"] == "validated_snapshot"


def test_bound_report_validation_and_mutation_detection(reasoning_root):
    root, declarations = reasoning_root
    corrupted = deepcopy(declarations)
    corrupted["window_sensitivity"]["sha256"] = "0" * 64
    tools = EvidenceTools(root, "post_spatial", reasoning_bindings=corrupted)
    assert tools.status["window_sensitivity"] == "unavailable_or_invalid"
    assert tools.call("get_window_contribution_summary", "{}")["error"] == "evidence_unavailable"
    tools = EvidenceTools(root, "post_spatial", reasoning_bindings=declarations)
    path = root / declarations["space_weather"]["artifact"]
    path.write_bytes(path.read_bytes() + b" ")
    assert tools.call("get_space_weather_summary", "{}")["error"] == "evidence_changed"


def test_consistent_hourly_report_still_must_match_accepted_spatial_arrays(reasoning_root):
    root, declarations = reasoning_root
    path = root / declarations["window_sensitivity"]["artifact"]
    report = strict_json(path.read_bytes())
    sidecar = path.parent / "hourly_snapshot.npz"
    a = load_hourly_snapshot(sidecar.read_bytes())
    a["negative"][121, 47 * 73 + 50] = 1
    np.savez_compressed(sidecar, **a)
    d = report["diagnostic"]
    report["diagnostic"] = build_window_diagnostic(a, d["baseline"], d["extended"], case_id=d["case_id"], selected_cells=d["selected_cells"])
    report["hourly_snapshot"].update(metadata(sidecar.read_bytes()))
    path.write_text(compact(report), encoding="utf-8")
    declarations["window_sensitivity"].update(metadata(path.read_bytes()))
    tools = EvidenceTools(root, "post_spatial", reasoning_bindings=declarations)
    assert tools.status["window_sensitivity"] == "unavailable_or_invalid"


def test_all_missing_indices_remain_missing_physical_evidence(reasoning_root):
    root, declarations = reasoning_root
    path = root / declarations["space_weather"]["artifact"]
    prior = strict_json(path.read_bytes())
    report = build_space_weather_report([], prior["window"], case_id=prior["case_id"], provenance=prior["provenance"])
    path.write_text(compact(report), encoding="utf-8")
    declarations["space_weather"].update(metadata(path.read_bytes()))
    tools = EvidenceTools(root, "post_spatial", reasoning_bindings=declarations)
    assert tools.status["space_weather"] == "validated_snapshot"
    assert tools.call("get_evidence_inventory", "{}")["data"]["external_indices"]["Kp"] == "no_observations"
    assert tools.call("compare_spatial_experiments", "{}")["data"]["missing_physical_evidence"] == ["Kp", "Dst", "F10.7"]


@pytest.mark.parametrize("kind,mutation", [
    ("window_sensitivity", "hours"), ("window_sensitivity", "source"),
    ("window_sensitivity", "original"), ("window_sensitivity", "aggregate"),
    ("space_weather", "summary"), ("space_weather", "case"),
])
def test_internally_inconsistent_reports_fail_even_with_fresh_pins(reasoning_root, kind, mutation):
    root, declarations = reasoning_root
    path = root / declarations[kind]["artifact"]
    report = strict_json(path.read_bytes())
    if mutation == "hours":
        report["diagnostic"]["additional_utc_hours"].pop()
    elif mutation == "source":
        next(iter(report["source_evidence"].values()))["sha256"] = "c" * 64
    elif mutation == "original":
        next(iter(report["original_inputs"].values()))["sha256"] = "c" * 64
    elif mutation == "aggregate":
        report["saved_comparison_checks"]["baseline"] = False
    elif mutation == "summary":
        report["summary"]["kp"]["maximum"] += 1
    else:
        report["case_id"] = "other_case"
    path.write_text(compact(report), encoding="utf-8")
    declarations[kind].update(metadata(path.read_bytes()))
    assert EvidenceTools(root, "post_spatial", reasoning_bindings=declarations).status[kind] == "unavailable_or_invalid"


def test_pre_mode_weather_is_independent_and_never_probes_spatial(reasoning_root, monkeypatch):
    root, declarations = reasoning_root
    with pytest.raises(ValueError, match="Post-Spatial"):
        EvidenceTools(root, "pre_spatial", reasoning_bindings=declarations)
    original = EvidenceTools._path
    def checked(self, identity):
        assert "comparison" not in identity and "selection" not in identity and "window.json" not in identity
        return original(self, identity)
    monkeypatch.setattr(EvidenceTools, "_path", checked)
    tools = EvidenceTools(root, "pre_spatial", reasoning_bindings={"space_weather": declarations["space_weather"]})
    assert tools.call("get_space_weather_summary", "{}")["ok"] is True
    assert tools.call("get_window_contribution_summary", "{}")["error"] == "tool_not_allowed"


@pytest.mark.parametrize("mutation", ["approval", "execution", "too_many", "uncited", "window", "empty", "numeric", "causal", "uninspected"])
def test_invalid_follow_up_proposals_are_rejected(reasoning_root, mutation):
    root, declarations = reasoning_root
    tools = EvidenceTools(root, "post_spatial", reasoning_bindings=declarations)
    result = tools.call("get_window_contribution_summary", "{}")
    final = assessment(result["data"])
    p = final["follow_up_experiments"][0]
    if mutation == "approval":
        p["human_approval_required"] = False
    elif mutation == "execution":
        p["execution_eligible"] = True
    elif mutation == "too_many":
        final["follow_up_experiments"] *= 4
    elif mutation == "uncited":
        p["supporting_evidence"] = []
    elif mutation == "window":
        p["proposed_windows"][0] = dict(start_utc="2022-05-29T00:00:00Z", end_utc="2022-06-01T23:00:00Z", inclusive_hours=96)
    elif mutation == "empty":
        final["follow_up_experiments"] = []
    elif mutation == "numeric":
        p["reason_for_investigation"] = "There were 99 observations."
    elif mutation == "causal":
        p["proposed_experiment"] = "This proves an earthquake precursor."
    else:
        p["supporting_evidence"][0]["result_id"] = "R9"
    with pytest.raises(ValueError):
        _check_assessment(final, {"R1": result}, tools, reasoning_enabled=True)


def test_valid_proposal_and_exact_space_weather_citations(reasoning_root):
    root, declarations = reasoning_root
    tools = EvidenceTools(root, "post_spatial", reasoning_bindings=declarations)
    result = tools.call("get_window_contribution_summary", "{}")
    weather = tools.call("inspect_space_weather_interval", compact(dict(start_utc="2022-05-28T00:00:00Z", end_utc="2022-05-28T00:00:00Z")))
    final = assessment(result["data"])
    final["observed_facts"].append(dict(result_id="R2", pointer="/data/rows/0/values/kp", value_json="2.7"))
    checked, flags = _check_assessment(final, {"R1": result, "R2": weather}, tools, reasoning_enabled=True)
    assert not flags
    assert checked["observed_facts"][-1]["value"] == 2.7
    assert checked["follow_up_experiments"][0]["execution_eligible"] is False
    assert "follow_up_experiments" not in _submission_tool("post_spatial")["parameters"]["properties"]


def test_offline_agent_workflow_and_saved_result_reassessment(reasoning_root, tmp_path, monkeypatch):
    root, declarations = reasoning_root
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline review attempted scientific execution")
    from src.spatial_verification import spatial_anomaly
    monkeypatch.setattr(spatial_anomaly, "compute_hourly_spatial_anomalies", forbidden)
    monkeypatch.setattr(spatial_anomaly, "compute_spatial_anomalies", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    path = offline_demo(root, declarations, tmp_path / "first")
    first = strict_json((path / "scientific_assessment.json").read_bytes())
    assert first["status"] == "submitted_for_researcher_review", first["flags"]
    assert len(first["assessment"]["follow_up_experiments"]) == 1
    assert first["model"]["live"] is False
    assert first["execution_eligible"] is False
    trace = strict_json((path / "agent_trace.json").read_bytes())
    names = [event["calls"][0]["name"] for event in trace]
    assert "inspect_window_contribution_hours" in names and "inspect_space_weather_interval" in names
    repeat = offline_demo(root, declarations, tmp_path / "second", reassessment_of=path / "scientific_assessment.json")
    second = strict_json((repeat / "scientific_assessment.json").read_bytes())
    assert second["assessment"] == first["assessment"]
    assert second["reassessment_of"]["sha256"] == metadata((path / "scientific_assessment.json").read_bytes())["sha256"]
    with pytest.raises(FileExistsError):
        offline_demo(root, declarations, path)


def test_agent_cli_binding_forwarding_and_invalid_pin_stops_before_model(reasoning_root, tmp_path, monkeypatch):
    from examples.run_afghanistan_mvp_agent import main
    from src.agent import scientific_review_agent as agent
    root, declarations = reasoning_root
    tools = EvidenceTools(root, "post_spatial", reasoning_bindings=declarations)
    final = assessment(tools.call("get_window_contribution_summary", "{}")["data"])
    script = tmp_path / "script.json"
    write_json(script, [[call("get_window_contribution_summary", identity="inspect")],
                        [call("submit_assessment", final, "submit")]])
    binding_path = tmp_path / "bindings.json"
    write_json(binding_path, declarations)
    target = tmp_path / "cli_review"
    args = ["--mode", "post_spatial", "--evidence-root", str(root), "--output-dir", str(target),
            "--reasoning-bindings", str(binding_path), "--fake-script", str(script), "--scientific-reasoning"]
    main(args)
    run = strict_json((target / "scientific_assessment.json").read_bytes())
    assert run["status"] == "submitted_for_researcher_review"
    binding_path.write_text(compact({"window_sensitivity": dict(declarations["window_sensitivity"], sha256="0" * 64)}), encoding="utf-8")
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid evidence reached model creation")
    monkeypatch.setattr(agent.FakeModel, "__init__", forbidden)
    args[args.index(str(target))] = str(tmp_path / "invalid_cli")
    with pytest.raises(SystemExit):
        main(args)


def test_reassessment_can_inspect_new_host_bound_weather_results(reasoning_root, tmp_path):
    root, declarations = reasoning_root
    first = offline_demo(root, {"window_sensitivity": declarations["window_sensitivity"]}, tmp_path / "before_weather")
    second = offline_demo(root, declarations, tmp_path / "with_weather", reassessment_of=first / "scientific_assessment.json")
    before = strict_json((first / "scientific_assessment.json").read_bytes())
    after = strict_json((second / "scientific_assessment.json").read_bytes())
    assert before["assessment"]["missing_evidence"]
    assert not after["assessment"]["missing_evidence"]
    assert any(f["pointer"] == "/data/summary/kp/maximum" and f["value"] == 2.7 for f in after["assessment"]["observed_facts"])
