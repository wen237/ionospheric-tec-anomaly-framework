"""Synthetic saved evidence and FakeModel only; no EPZ generator or live model."""

import builtins
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import stat
import sys
from types import SimpleNamespace

import pytest

from examples import run_afghanistan_mvp_agent as cli
from src.agent import scientific_evidence_tools as evidence_module
from src.agent.scientific_evidence_tools import EvidenceTools, PRE_ROOT, POST_ROOT, compact, definitions
from src.agent.scientific_review_agent import (
    FakeModel, run_agent, save_run, validate_output_dir, _check_assessment, AssessmentValidationError,
)
from tests.agent.test_scientific_review_agent import pre_root, post_root, call, submission, load, pin
from tests.workflow.test_select_afghanistan_mvp_window import bundle_factory, modern_dir
from tests.workflow.test_planning_evidence import historical
from tests.workflow.test_scientific_review_integration import prohibit_protected_calls


IDENTITY = "epz/diagnostic.json"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch, prohibit_protected_calls):
    def forbidden(*args, **kwargs):
        raise AssertionError("Scientific/model/network execution is forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(cli, "OpenAIModel", forbidden)
    original = builtins.__import__
    def imports(name, *args, **kwargs):
        if name.split(".")[0] == "openai":
            forbidden()
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", imports)
    previous = sys.getprofile()
    def check(frame, event, arg):
        if event == "call":
            name = frame.f_globals.get("__name__", "")
            if (name == "examples.diagnose_afghanistan_epicentral_zone"
                    or name.startswith("src.statistical_clustering.")
                    or (name == "src.temporal_anomaly.temporal_anomaly" and frame.f_code.co_name == "detect_temporal_anomalies")
                    or (name == "examples.compare_afghanistan_mvp_spatial" and frame.f_code.co_name in {"run_comparison", "_run_modern_d", "_input_validity"})):
                forbidden()
        if previous:
            previous(frame, event, arg)
    sys.setprofile(check)
    try:
        yield
    finally:
        sys.setprofile(previous)


@pytest.fixture
def approved(post_root):
    """Hand-authored V1 geometry and synthetic observations, not Afghanistan results.

    Geometry is copied from the accepted convention; counts belong to the existing
    synthetic fixture (negative 6/4/0 vs 7/5/0), not real scientific evidence.
    No diagnostic generator or distance/membership algorithm builds this fixture.
    """
    e = EvidenceTools(post_root, "post_spatial")
    centers = [dict(row_index=i, column_index=50, latitude=lat, longitude=70.0,
        distance_km=distance, signed_boundary_margin_km=margin) for i, lat, distance, margin in (
        (47, 30.0, 339.62980257646694, -40.55959374409434),
        (48, 32.5, 76.52036812467, -303.6690281958913),
        (49, 35.0, 225.64016431002625, -154.54923201053504))]
    reference = dict(relation="R_km = 10 ** (0.43 * M)", doi="10.1007/BF00876083", magnitude=6.0,
        epz_radius_km=380.1893963205613, earth_radius_km=6371.0088, distance_method="wrapped spherical haversine",
        membership_rule="grid_center_distance_km <= epz_radius_km", radius_tolerance_km=0.0,
        interpretation="literature-motivated retrospective spatial reference; no validated TEC influence boundary",
        historical_spatial_decision_rule="visual overlap of anomaly grid cells with the plotted EPZ circle",
        diagnostic_spatial_decision_rule="great-circle grid-center membership", historical_visual_overlap_reproduced=False,
        grid_cell_intersection_computed=False, physical_areal_coverage_computed=False)
    # Contract text is a hand-authored fixture, independent of reader constants.
    limitations = [
        "EPZ membership is descriptive geometry, not a physically validated TEC influence boundary.",
        "Only grid centers are tested; nominal cells may cross the EPZ boundary.",
        "Historical visual grid-cell/circle overlap and great-circle center membership are different decision rules; exact historical overlap is not reproduced.",
        "Grid-cell intersection is a future sensitivity analysis and was not calculated.",
        "No physical EPZ areal coverage was calculated; the coarse GIM grid resolves only sampled centers.",
        "Grid-center observations are spatially correlated; regional statistics have no spatial significance interpretation.",
        "Grid-hour count sums are not unique UTC anomaly hours.",
        "Regional unweighted mean percentages are descriptive, not area coverage or earthquake association probabilities.",
        "Finite-input counts are availability diagnostics, not effective detector-valid counts; effective detector-valid counts are unavailable.",
        "Initial-reference availability does not describe every later rolling reference; zero anomaly counts do not prove valid normal observations.",
        "Original full-window percentage denominators are preserved despite input missingness.",
        "Kp, Dst and F10.7 are not evaluated.",
        "No earthquake causality, association significance or precursor is established.",
        "Snapshot hashes do not authenticate origin, OS isolation or trusted human authorization."]
    code_names = ["examples/diagnose_afghanistan_epicentral_zone.py", "src/agent/scientific_evidence_tools.py",
        "examples/compare_afghanistan_mvp_spatial.py", "examples/select_afghanistan_mvp_window.py",
        "examples/review_afghanistan_mvp.py", "src/spatial_verification/spatial_grid.py", "src/workflow/spatial_summary_export.py"]
    report = dict(record_type="afghanistan_epicentral_zone_diagnostic", schema_version=1, case_id="afghanistan_2022",
        event=e.bundle["record"]["confirmed_event"], scientific_reference=reference,
        grid=dict(shape=[71, 73], orientation="canonical", coordinates="grid centers",
            latitudes=e.arrays["A"]["latitudes"].tolist(), longitudes=e.arrays["A"]["longitudes"].tolist(),
            latitude_spacing_degrees=2.5, longitude_spacing_degrees=5.0,
            endpoint_meridian="-180 and +180 duplicate one physical meridian; neither is included"),
        mask=dict(included_center_count=3, status="nonempty", centers=centers,
            sha256="7644ce22be563963c99ed349737aa4a7ac582a5d4d2495f0fa49512ba89063c3",
            hash_encoding="uint8 0/1, shape (71,73), C row-major order, 5183 bytes",
            boundary_margin_sign="distance minus radius; negative inside",
            closest_included_center_to_boundary=deepcopy(centers[0]),
            closest_excluded_center_to_boundary=dict(row_index=48, column_index=49, latitude=32.5, longitude=65.0,
                distance_km=421.3755927948287, signed_boundary_margin_km=41.18619647426743)),
        summary_semantics=dict(count_sum_unit="grid-hour occurrences",
            regional_mean="unweighted mean of included grid-center occurrence percentages", interpretation="descriptive summaries only",
            excluded_interpretations=["unique anomaly hours", "EPZ areal coverage", "spatial statistical significance", "earthquake association probability"]),
        limitations=limitations, experiments={}, comparison=dict(direction="B minus A", ratio_difference_unit="percentage_points",
            mask_identity="shared mask for A and B", denominators=dict(A=120, B=144), included_centers=[], polarities={}),
        provenance=dict(validated_source_artifacts=deepcopy(e.sources), current_direct_code_artifacts={
            name:dict(sha256="a"*64, size_bytes=123) for name in code_names}, environment=dict(python="historical", numpy="historical"),
            original_input_files_opened=False, source_integrity="SYNTHETIC snapshot fixture", code_scope="historical declared generator"),
        review_state=dict(stop_point="Scientific & Security Review", researcher_review="pending", agent_integration="not_authorized",
            windows_local_isolation="NOT VERIFIED", trusted_human_authorization="NOT VERIFIED", execution_eligible=False,
            framework_execution="not_performed", llm_execution="not_performed"))
    fields = ("positive_counts", "negative_counts", "positive_ratio", "negative_ratio", "target_input_finite_counts", "initial_reference_input_finite_counts")
    for label, hours, negatives in (("A", 120, [6, 4, 0]), ("B", 144, [7, 5, 0])):
        s, selection = e.summaries[label], e.selections[label]
        rows = [dict(row_index=47+n, column_index=50, positive_counts=0, negative_counts=count,
            positive_ratio=0.0, negative_ratio=count/hours*100, target_input_finite_counts=hours,
            initial_reference_input_finite_counts=360) for n, count in enumerate(negatives)]
        polarities = {}
        for polarity, counts in (("positive", [0, 0, 0]), ("negative", negatives)):
            ratios = [count/hours*100 for count in counts]
            point = deepcopy(centers[0]) if polarity == "negative" else dict(row_index=26, column_index=6, latitude=-22.5,
                longitude=-150.0, distance_km=15985.844341923244, signed_boundary_margin_km=15605.654945602682)
            peak_count = negatives[0] if polarity == "negative" else (3 if label == "A" else 4)
            point.update(count=peak_count, ratio_percent=peak_count/hours*100, grid_center_inside_epz=polarity == "negative")
            polarities[polarity] = dict(global_maximum_ratio_percent=peak_count/hours*100, global_peak_centers=[point],
                regional=dict(grid_hour_occurrence_count_sum=sum(counts), unweighted_mean_ratio_percent=sum(ratios)/3,
                    count_minimum=min(counts), count_maximum=max(counts), ratio_minimum_percent=min(ratios), ratio_maximum_percent=max(ratios)))
        report["experiments"][label] = dict(experiment=s["experiment"], window=s["window"], selection_mode=selection["selection_mode"],
            cluster_id=selection["cluster_id"], selection_artifact=f"afghanistan_mvp02b_selections/{s['experiment']}/selection_record.json",
            parameters=s["parameters"], window_steps=hours, ratio_denominator=hours, nominal_grid_hour_denominator=3*hours,
            included_centers=rows, polarities=polarities, effective_detector_valid_counts=None,
            input_availability={f:dict(global_minimum=value, global_maximum=value, included_minimum=value, included_maximum=value)
                for f, value in (("target_input_finite_counts", hours), ("initial_reference_input_finite_counts", 360))})
    a, b = (report["experiments"][label] for label in ("A", "B"))
    for first, second in zip(a["included_centers"], b["included_centers"]):
        report["comparison"]["included_centers"].append(dict(row_index=first["row_index"], column_index=50,
            **{f+"_b_minus_a":second[f]-first[f] for f in fields}))
    for polarity in ("positive", "negative"):
        changes = report["comparison"]["included_centers"]
        report["comparison"]["polarities"][polarity] = dict(
            grid_hour_occurrence_count_sum_b_minus_a=sum(c[polarity+"_counts_b_minus_a"] for c in changes),
            mean_cell_ratio_difference_percentage_points=sum(c[polarity+"_ratio_b_minus_a"] for c in changes)/3)
    path = post_root / IDENTITY
    path.parent.mkdir()
    path.write_text(compact(report), encoding="utf-8")
    return post_root, path


def bind(root, path):
    return dict(epz_diagnostic=path.relative_to(root).as_posix(), epz_sha256=pin(path)["sha256"], epz_size_bytes=pin(path)["size_bytes"])


def tools_for(approved):
    root, path = approved
    return EvidenceTools(root, "post_spatial", **bind(root, path))


def test_approved_projection_and_scientific_distinctions(approved):
    tools = tools_for(approved)
    assert tools.status["epz_diagnostic"] == "validated_snapshot"
    result = tools.call("get_epz_diagnostic_summary", "{}")
    assert result["ok"] and len(compact(result).encode()) <= 24*1024
    d = result["data"]
    assert d["shared_mask"]["included_center_count"] == 3
    assert [(p["latitude"],p["longitude"]) for p in d["shared_mask"]["centers"]] == [(30.0,70.0),(32.5,70.0),(35.0,70.0)]
    a, b = d["experiments"]["A"], d["experiments"]["B"]
    assert (a["ratio_denominator"],b["ratio_denominator"]) == (120,144)
    assert a["polarities"]["negative"]["regional"]["grid_hour_occurrence_count_sum"] == 10
    assert b["polarities"]["negative"]["regional"]["grid_hour_occurrence_count_sum"] == 12
    assert d["comparison"]["polarities"]["negative"]["grid_hour_occurrence_count_sum_b_minus_a"] == 2
    assert a["polarities"]["positive"]["global_peak_centers"][0]["grid_center_inside_epz"] is False
    assert a["effective_detector_valid_counts"] is None
    assert d["epz_definition"]["historical_visual_overlap_reproduced"] is False
    assert d["missing_physical_evidence"] == ["Kp","Dst","F10.7"]
    assert d["diagnostic_identity"] == dict(artifact=IDENTITY, **pin(approved[1]))
    assert result["sources"][0] == d["diagnostic_identity"]
    assert not any(k in d for k in ("recommendation", "approval", "association_score"))
    assert "C:/" not in compact(result) and str(approved[0]) not in compact(result)


def test_one_new_post_tool_and_no_pre_visibility(approved, monkeypatch):
    assert len(definitions("post_spatial")) == 8
    assert len(tools_for(approved).tool_definitions()) == 9
    assert len(definitions("pre_spatial")) == 5
    assert "get_epz_diagnostic_summary" not in {t["name"] for t in definitions("pre_spatial")}
    original = EvidenceTools._path
    def pre_paths(self, identity):
        assert identity.startswith(PRE_ROOT+"/")
        return original(self, identity)
    monkeypatch.setattr(EvidenceTools, "_path", pre_paths)
    pre = EvidenceTools(approved[0], "pre_spatial")
    assert len(pre.sources) == 6
    assert "epz" not in compact(pre.call("get_evidence_inventory", "{}")).lower()
    for name in ("get_epz_diagnostic_summary", "compare_spatial_experiments", "get_spatial_experiment_summary", "inspect_spatial_grid_cell"):
        assert pre.call(name, "{}")["error"] == "tool_not_allowed"
    assert all(identity.startswith(PRE_ROOT+"/") for identity in pre.sources)


@pytest.mark.parametrize("state", ["pre", "unbound", "valid", "wrong_hash", "wrong_size",
                                  "missing", "invalid_report", "invalid_spatial"])
def test_model_adapter_receives_only_available_evidence_tools(approved, state):
    root, path = approved
    args = {} if state in ("pre", "unbound") else bind(root, path)
    if state == "wrong_hash":
        args["epz_sha256"] = "0" * 64
    elif state == "wrong_size":
        args["epz_size_bytes"] = 1
    elif state == "missing":
        path.unlink()
    elif state == "invalid_report":
        report = load(path)
        report["schema_version"] = 99
        path.write_text(compact(report), encoding="utf-8")
        args = bind(root, path)
    elif state == "invalid_spatial":
        (root / POST_ROOT / "experiment_a_reference_120h" / "spatial_arrays.npz").write_bytes(b"invalid synthetic source")
    mode = "pre_spatial" if state == "pre" else "post_spatial"
    evidence = EvidenceTools(root, mode, **args)
    seen = []
    def adapter(history, available):
        seen.append(deepcopy(available))
        if len(seen) == 1:
            # An unadvertised call is deliberately attempted to check safe dispatch.
            return [call("get_epz_diagnostic_summary")]
        if len(seen) == 2:
            return [call("submit_assessment", submission([("R1", "/data/not_here", 1)]), "bad")]
        return [call("submit_assessment", submission(), "finish")]
    run = run_agent(FakeModel(adapter), evidence, "Review only available evidence.")
    expected = ["get_evidence_inventory", "get_temporal_summary", "inspect_anomaly_interval",
                "get_historical_context", "list_candidate_windows"]
    if mode == "post_spatial":
        expected += ["get_spatial_experiment_summary", "compare_spatial_experiments", "inspect_spatial_grid_cell"]
    if state == "valid":
        expected += ["get_epz_diagnostic_summary"]
    assert len(seen) == 3
    assert [t["name"] for t in seen[0]] == expected + ["submit_assessment"]
    assert seen[1] == seen[0]
    assert [t["name"] for t in seen[2]] == ["submit_assessment"]
    result = run["evidence_actually_inspected"][0]
    if state == "valid":
        assert result["ok"] is True
    else:
        assert result["error"] == ("tool_not_allowed" if state == "pre" else "evidence_unavailable")
    assert run["assessment_outcome"] == "valid_corrected_submission"
    assert run["model"]["live"] is False and run["execution_eligible"] is False


@pytest.mark.parametrize("binding", [dict(epz_diagnostic="epz/missing.json"), dict(epz_sha256="a"*64),
    dict(epz_size_bytes=1), dict(epz_diagnostic="epz/missing.json",epz_sha256="a"*64,epz_size_bytes=1)])
def test_pre_rejects_binding_before_any_path_probe(binding, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Pre binding probed a filesystem path")
    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    with pytest.raises(ValueError, match="Post-Spatial"):
        EvidenceTools("must-not-open", "pre_spatial", **binding)


def test_post_without_binding_is_backward_compatible(approved, monkeypatch):
    original = EvidenceTools._path
    def no_epz(self, identity):
        assert identity != IDENTITY
        return original(self, identity)
    monkeypatch.setattr(EvidenceTools,"_path",no_epz)
    tools = EvidenceTools(approved[0],"post_spatial")
    assert tools.status == dict(temporal_historical="validated_snapshot",spatial="validated_snapshot")
    assert len(tools.sources) == 23
    assert tools.call("get_epz_diagnostic_summary","{}") == dict(ok=False,error="evidence_unavailable")
    assert tools.call("compare_spatial_experiments","{}")["ok"]


@pytest.mark.parametrize("identity", ["../epz.json","epz/../a.json","/a.json","C:/a.json","epz\\a.json",
    "epz//a.json","epz/./a.json","epz/a.json:stream","epz/a.npz","NUL.json","dir./a.json"])
def test_invalid_host_paths_rejected(identity):
    with pytest.raises(ValueError):
        EvidenceTools("not-opened","post_spatial",epz_diagnostic=identity,epz_sha256="a"*64,epz_size_bytes=1)


@pytest.mark.parametrize("override", [dict(epz_sha256=None),dict(epz_size_bytes=None),dict(epz_sha256="NOT-A-HASH"),dict(epz_size_bytes=True)])
def test_incomplete_or_unapproved_binding_rejected(override):
    args=dict(epz_diagnostic=IDENTITY,epz_sha256="a"*64,epz_size_bytes=1)
    args.update(override)
    with pytest.raises(ValueError):
        EvidenceTools("not-opened","post_spatial",**args)


@pytest.mark.parametrize("key,value", [("epz_sha256","0"*64),("epz_size_bytes",1)])
def test_wrong_independent_pin_fails_closed(approved,key,value):
    args=bind(*approved)
    args[key]=value
    e=EvidenceTools(approved[0],"post_spatial",**args)
    assert e.status["epz_diagnostic"] == "unavailable_or_invalid"
    assert e.call("get_epz_diagnostic_summary","{}")["error"] == "evidence_unavailable"


def change(report,path,value):
    parts=path.split("/")
    for part in parts[:-1]:
        report=report[int(part)] if isinstance(report,list) else report[part]
    if isinstance(report,list):
        report[int(parts[-1])]=value
    else:
        report[parts[-1]]=value


@pytest.mark.parametrize("field,value", [
    ("record_type","wrong"),("schema_version",2),("case_id","other"),("event/event_id","other"),
    ("grid/orientation","legacy"),("scientific_reference/epz_radius_km",400.0),
    ("experiments/B/window/end_utc","2022-06-01T23:00:00Z"),("experiments/B/ratio_denominator",120),
    ("experiments/A/parameters/k",2.0),("experiments/B/selection_mode","independent"),
    ("provenance/validated_source_artifacts",{}),("mask/sha256","0"*64),
    ("mask/centers/0/row_index",46),("mask/centers/0/distance_km",999.0),
    ("experiments/A/included_centers/0/negative_counts",7),("experiments/A/included_centers/0/negative_ratio",99.0),
    ("experiments/A/polarities/negative/regional/grid_hour_occurrence_count_sum",11),
    ("experiments/B/polarities/negative/global_peak_centers/0/grid_center_inside_epz",False),
    ("comparison/included_centers/0/negative_counts_b_minus_a",-1),
    ("comparison/polarities/negative/mean_cell_ratio_difference_percentage_points",9.0),
    ("experiments/A/effective_detector_valid_counts",120),("limitations",[]),
    ("review_state/execution_eligible",True),
])
def test_inconsistent_report_rejected_even_when_host_repin_supplied(approved,field,value):
    report=load(approved[1])
    change(report,field,value)
    approved[1].write_text(compact(report),encoding="utf-8")
    tools=tools_for(approved)
    assert tools.status["epz_diagnostic"] == "unavailable_or_invalid"
    assert tools.call("get_epz_diagnostic_summary","{}")["error"] == "evidence_unavailable"


@pytest.mark.parametrize("raw", [b'{',b'{"record_type":1,"record_type":2}',b'{"x":NaN}',b'{"x":Infinity}',b'[]'])
def test_invalid_json_is_not_repaired(approved,raw):
    approved[1].write_bytes(raw)
    assert tools_for(approved).call("get_epz_diagnostic_summary","{}")["error"] == "evidence_unavailable"


def test_stale_spatial_source_rejected(approved):
    root,path=approved
    source=root/POST_ROOT/"experiment_a_reference_120h"/"spatial_arrays.npz"
    source.write_bytes(b"modified synthetic array")
    tools=tools_for(approved)
    assert tools.status["spatial"] == "unavailable_or_invalid"
    assert tools.status["epz_diagnostic"] == "unavailable_or_invalid"
    assert tools.call("get_epz_diagnostic_summary","{}")["error"] == "evidence_unavailable"


@pytest.mark.parametrize("target", [IDENTITY,POST_ROOT+"/experiment_a_reference_120h/spatial_arrays.npz"])
def test_changed_snapshot_never_served(approved,target):
    tools=tools_for(approved)
    (approved[0]/target).write_bytes(b"changed after loading")
    assert tools.call("get_epz_diagnostic_summary","{}")["error"] == "evidence_changed"


def test_historical_generator_code_is_not_compared_to_current_reader(approved):
    # Fixture intentionally records seven non-current fingerprints.
    assert all(p["sha256"] == "a"*64 for p in load(approved[1])["provenance"]["current_direct_code_artifacts"].values())
    assert tools_for(approved).call("get_epz_diagnostic_summary","{}")["ok"]


def test_missing_file_and_oversized_file_fail_closed(approved):
    root,path=approved
    args=bind(root,path)
    path.unlink()
    assert EvidenceTools(root,"post_spatial",**args).call("get_epz_diagnostic_summary","{}")["error"] == "evidence_unavailable"
    path.write_bytes(b" "*(evidence_module.MAX_FILE_BYTES+1))
    args.update(epz_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),epz_size_bytes=evidence_module.MAX_FILE_BYTES)
    assert EvidenceTools(root,"post_spatial",**args).status["epz_diagnostic"] == "unavailable_or_invalid"


def test_symlink_rejected(approved):
    root,path=approved
    args=bind(root,path)
    target=path.with_name("original.json")
    path.rename(target)
    try:
        path.symlink_to(target)
    except OSError as exc:
        pytest.skip("Local account cannot create symlinks: "+str(exc.winerror if hasattr(exc,"winerror") else exc.errno))
    assert EvidenceTools(root,"post_spatial",**args).status["epz_diagnostic"] == "unavailable_or_invalid"


def test_windows_reparse_attribute_rejected(approved,monkeypatch):
    root,path=approved
    args=bind(root,path)
    original=Path.lstat
    def redirected(p,*a,**kw):
        if p == path:
            return SimpleNamespace(st_file_attributes=0x400,st_mode=stat.S_IFREG)
        return original(p,*a,**kw)
    monkeypatch.setattr(Path,"lstat",redirected)
    assert EvidenceTools(root,"post_spatial",**args).status["epz_diagnostic"] == "unavailable_or_invalid"


def test_tool_arguments_and_output_budget(approved,monkeypatch):
    tools=tools_for(approved)
    assert tools.call("get_epz_diagnostic_summary",'{"path":"secret"}')["error"] == "invalid_arguments"
    assert tools.call("get_epz_diagnostic_summary",'{"radius":900}')["error"] == "invalid_arguments"
    monkeypatch.setattr(evidence_module,"MAX_TOOL_BYTES",100)
    assert tools.call("get_epz_diagnostic_summary","{}")["error"] == "tool_output_limit"


def test_fake_loop_exact_citations_and_saved_provenance_without_mutation(approved,tmp_path):
    root,path=approved
    before={p.relative_to(root):p.read_bytes() for p in root.rglob("*") if p.is_file()}
    tools=tools_for(approved)
    ref=dict(result_id="R1",pointer="/data/experiments/A/ratio_denominator")
    assessment=submission([("R1",ref["pointer"],120), ("R1","/data/experiments/A/included_centers/0/negative_counts",6)],
        action="review_spatial_comparison",refs=[ref])
    model=FakeModel([[call("get_epz_diagnostic_summary")],[call("submit_assessment",assessment,"finish")]])
    run=run_agent(model,tools,"Review the descriptive spatial evidence.")
    assert run["status"] == "submitted_for_researcher_review" and run["model"]["live"] is False
    assert run["execution_eligible"] is False and run["assessment_outcome"] == "valid_first_submission"
    assert run["budgets"]["tool_calls"] == 8 and run["budgets"]["turns"] == 10
    destination=save_run(tmp_path/"fake-agent",run,tools)
    record=load(destination/"run_record.json")
    assert record["epz_binding"] == dict(artifact=IDENTITY,**pin(path))
    assert record["source_snapshots"][IDENTITY] == pin(path)
    assert len(record["source_snapshots"]) == 24 and "src/agent/epz_evidence.py" in record["code"]
    assert before == {p.relative_to(root):p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(ValueError):
        validate_output_dir(path.parent/"nested-run",tools)


@pytest.mark.parametrize("pointer,value", [("/data/not_here",120),("/data/experiments/A/ratio_denominator",120.0),
    ("/data/experiments/A/ratio_denominator",144)])
def test_bad_epz_facts_rejected(approved,pointer,value):
    tools=tools_for(approved)
    result=tools.call("get_epz_diagnostic_summary","{}")
    with pytest.raises(AssessmentValidationError):
        _check_assessment(submission([("R1",pointer,value)]),{"R1":result},tools)


def test_cli_pre_binding_rejected_before_paths_or_client(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError("CLI probed a path before rejecting Pre binding")
    monkeypatch.setattr(Path,"exists",forbidden)
    with pytest.raises(SystemExit) as exc:
        cli.main(["--mode","pre_spatial","--evidence-root","not-opened","--output-dir","not-created", "--fake-script","not-read",
            "--epz-diagnostic",IDENTITY,"--epz-sha256","a"*64,"--epz-size-bytes","1"])
    assert exc.value.code == 2


def test_cli_invalid_bound_file_never_creates_live_client(approved,tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--mode","post_spatial","--live","--model","explicit-test-model","--evidence-root",str(approved[0]),
            "--output-dir",str(tmp_path/"no-run"),"--epz-diagnostic",IDENTITY,"--epz-sha256","0"*64,"--epz-size-bytes","1"])
    assert exc.value.code == 2 and not (tmp_path/"no-run").exists()


def test_cli_fake_binding(approved,tmp_path):
    script=tmp_path/"fake.json"
    script.write_text(compact([[call("get_epz_diagnostic_summary")],
        [call("submit_assessment",submission([("R1","/data/shared_mask/included_center_count",3)]),"finish")]]),encoding="utf-8")
    pin_args=bind(*approved)
    cli.main(["--mode","post_spatial","--evidence-root",str(approved[0]),"--output-dir",str(tmp_path/"cli-fake"),"--fake-script",str(script),
        "--epz-diagnostic",IDENTITY,"--epz-sha256",pin_args["epz_sha256"],"--epz-size-bytes",str(pin_args["epz_size_bytes"])])
    record=load(tmp_path/"cli-fake/run_record.json")
    assert record["live_model_called"] is False and record["availability"]["epz_diagnostic"] == "validated_snapshot"
