"""MVP-02B: case-specific dual-window Modern D comparison, pending execution review.

`plan` only validates explicit selection records, source bindings and fresh output
paths. `run` is a proposed researcher-run entry point: do not invoke it until the
separate real-execution scope and applicable isolation requirements are approved.
Neither a subcommand nor a selection record authenticates human authorization.
No authorization/Store/Legacy Stage 2 operation is provided here.

The accepted Modern D calculation and canonical plotting/peak helpers are reused
lazily. Maps omit optional Cartopy boundaries, avoiding implicit downloads.
Input finite-value counts are availability diagnostics, NOT effective detector
sample counts: the existing D ratios retain the full target-hour denominator.
Failures retain the new partial directory and an explicit failure record when
possible. A comparison is complete only when its final summary and hashes exist.
"""

import argparse
import hashlib
from importlib.metadata import version
from pathlib import Path
import platform

import numpy as np

from examples import review_afghanistan_mvp as mvp01
from examples import select_afghanistan_mvp_window as handoff


_ROOT = Path(__file__).resolve().parents[1]
_EXPERIMENTS = ("experiment_a_reference_120h", "experiment_b_candidate_144h")
_SELECTION_FIELDS = set("record_type schema_version case_id event selection_mode cluster_id window "
    "scientific_rationale parent_review_bundle selected_candidate historical_reference_comparison "
    "candidate_comparisons modern_gim_inputs review_only execution_eligible framework_d_execution "
    "windows_local_isolation trusted_human_authorization".split())
_CODE_FILES = (*mvp01._CODE_PATHS, "examples/select_afghanistan_mvp_window.py",
    "examples/compare_afghanistan_mvp_spatial.py", "src/workflow/explicit_window.py",
    "src/workflow/temporal_window.py", "src/workflow/datetime_adapter.py",
    "src/workflow/modern_spatial_input_adapter.py", "src/spatial_verification/spatial_anomaly.py",
    "src/spatial_verification/spatial_grid.py", "src/spatial_verification/spatial_plot.py",
    "src/workflow/spatial_summary_export.py")
_VALIDITY_NOTE = ("Finite input values only; effective detector-valid sample counts are not exposed by "
                  "SpatialAnomalyResult. Ratios divide by all target hours, not by finite-input counts.")


def _state(status):
    return dict(framework_d_execution=status, execution_eligible=False,
                windows_local_isolation="NOT VERIFIED", trusted_human_authorization="NOT VERIFIED")


def _write(path, value):
    with path.open("xb") as handle:
        handle.write(handoff._json(value).encode("utf-8"))


def _selection(path, review_bundle, modern_data_dir, experiment):
    selected_path = Path(path)
    if selected_path.is_symlink():
        raise ValueError("Selection record must not be redirected.")
    selected_path = selected_path.resolve(strict=True)
    raw = selected_path.read_bytes()
    record = handoff._decode(raw)
    if type(record) is not dict or set(record) != _SELECTION_FIELDS:
        raise ValueError("Unsupported or incomplete selection record.")
    bundle = handoff.validate_bundle(review_bundle)
    for key, expected in dict(record_type="afghanistan_mvp_window_selection", schema_version=1,
        case_id=bundle["record"]["case_id"], event=bundle["record"]["confirmed_event"],
        parent_review_bundle=bundle["binding"], review_only=True, **_state("not_performed")).items():
        handoff._same(record[key], expected, f"selection {key}")
    if type(record["scientific_rationale"]) is not str or not record["scientific_rationale"].strip():
        raise ValueError("Selection requires a scientific rationale.")
    window = handoff._window(record["window"]["start_utc"], record["window"]["end_utc"])
    bounds = handoff._bounds(window)
    handoff._same(record["window"], bounds, "selection inclusive bounds/duration")
    reports = bundle["proposal"]["anchor_reports"]
    if experiment == 0:
        handoff._same([record["selection_mode"], record["cluster_id"], record["selected_candidate"]],
                      ["independent", None, None], "Experiment A selection mode")
        handoff._same(bounds, mvp01.REFERENCE_WINDOW, "Experiment A historical window")
    else:
        handoff._same([record["selection_mode"], record["cluster_id"]], ["candidate", 1], "Experiment B selection mode")
        candidate = next((r for r in reports if r["anchor"]["cluster_id"] == 1), None)
        if candidate is None or candidate["status"] != "candidate":
            raise ValueError("Experiment B requires the eligible saved cluster 1 candidate.")
        handoff._same(record["selected_candidate"], candidate, "selected candidate/proposal")
        handoff._same(bounds, {key: candidate["candidate_window"][key] for key in bounds}, "candidate bounds")
        handoff._same(bounds, dict(start_utc="2022-05-28T00:00:00Z", end_utc="2022-06-02T23:00:00Z",
                                  inclusive_hours=144), "researcher-selected Experiment B window")
    handoff._same(record["historical_reference_comparison"], dict(
        reference=bundle["record"]["historical_research_reference"], matches_selected_window=bounds == mvp01.REFERENCE_WINDOW,
        duration_difference_hours=bounds["inclusive_hours"] - 120), "historical comparison")
    handoff._same(record["candidate_comparisons"], [dict(cluster_id=r["anchor"]["cluster_id"], status=r["status"],
        candidate_window=r["candidate_window"], matches_selected_window=(None if r["candidate_window"] is None else
            all(r["candidate_window"][key] == bounds[key] for key in bounds))) for r in reports], "candidate comparisons")
    inventory = handoff._inventory(modern_data_dir, window, bundle["record"]["inputs"]["modern_daily_files"])
    if not inventory["source_integrity_ready"]:
        raise ValueError("Required Modern inputs are missing, ambiguous, invalid or differ from original hashes.")
    handoff._same(record["modern_gim_inputs"], inventory, "saved/current input inventory")
    handoff._unchanged(bundle["binding"])
    return dict(path=selected_path, raw=raw, record=record, window=window,
        pin=dict(path=str(selected_path), **handoff._metadata(raw)),
        files=tuple(Path(item["path"]) for item in inventory["required_daily_files"]))


def _prepare(selection_a, selection_b, review_bundle, modern_data_dir, output_dir):
    target = Path(output_dir)
    if target.exists() or target.is_symlink():
        raise FileExistsError("Comparison requires a new output directory; no overwrite is permitted.")
    destination = target.resolve()
    forbidden = [Path(review_bundle).resolve(), Path(modern_data_dir).resolve(),
                 Path(selection_a).resolve().parent, Path(selection_b).resolve().parent]
    if any(destination.is_relative_to(root) for root in forbidden):
        raise ValueError("Comparison output must be outside source bundle, selections and data directories.")
    selected = [_selection(path, review_bundle, modern_data_dir, index)
                for index, path in enumerate((selection_a, selection_b))]
    plan = dict(record_type="afghanistan_mvp_dual_window_plan", schema_version=1,
        case_id=mvp01.CASE_ID, output_directory=str(destination), parameters=dict(reference_days=15, k=3.0,
        grid_orientation="canonical", show_boundaries=False), **_state("not_performed"),
        experiments={name: dict(selection=s["pin"], window=s["record"]["window"],
            parent_review_bundle=s["record"]["parent_review_bundle"],
            input_files=s["record"]["modern_gim_inputs"]["required_daily_files"],
            output_directory=str(destination / name)) for name, s in zip(_EXPERIMENTS, selected)},
        cluster_0_status="valid_candidate_not_selected_for_this_comparison",
        input_validity_scope=_VALIDITY_NOTE,
        execution_requirement="Separate explicit researcher approval and applicable isolation prerequisites; not a software authorization gate.")
    return plan, selected


def plan_comparison(selection_a, selection_b, *, review_bundle, modern_data_dir, output_dir):
    """Non-executing validation; creates no files or selections."""
    return _prepare(selection_a, selection_b, review_bundle, modern_data_dir, output_dir)[0]


def _input_validity(window, files):
    from src.data.modern_gim_bridge import load_modern_gim_window

    data = load_modern_gim_window(files, window.start_time.replace(tzinfo=None),
                                 window.end_time.replace(tzinfo=None), reference_days=15)
    # Diagnostics only: do not recreate percentile thresholds or anomaly decisions.
    return dict(target_input_finite_counts=np.isfinite(data.tec[360:]).sum(axis=0),
                initial_reference_input_finite_counts=np.isfinite(data.tec[:360]).sum(axis=0))


def _run_modern_d(window, files):
    from src.workflow.modern_spatial_input_adapter import run_spatial_verification_from_modern_gim

    return run_spatial_verification_from_modern_gim(window, files, reference_days=15, k=3.0), "executed"


def _peaks(result):
    from src.workflow.spatial_summary_export import _maximum_anomaly

    return {polarity: _maximum_anomaly(getattr(result, polarity + "_ratio"), result.latitudes,
            result.longitudes, grid_orientation="canonical") for polarity in ("positive", "negative")}


def _write_maps(result, window, directory):
    from src.spatial_verification.spatial_plot import save_spatial_anomaly_plot

    for polarity in ("positive", "negative"):
        save_spatial_anomaly_plot(result, polarity=polarity, output_path=directory / f"{polarity}.png",
            start_time=window.start_time, end_time=window.end_time,
            epicenter_latitude=mvp01.EVENT["latitude"], epicenter_longitude=mvp01.EVENT["longitude"],
            magnitude=mvp01.EVENT["magnitude"], grid_orientation="canonical", show_boundaries=False)


def _arrays(result, window, validity):
    hours = handoff._bounds(window)["inclusive_hours"]
    if type(result.window_steps) is not int or result.window_steps != hours:
        raise ValueError("Spatial result duration differs from the explicit selection.")
    if (not np.array_equal(result.latitudes, np.linspace(-87.5, 87.5, 71)) or
            not np.array_equal(result.longitudes, np.linspace(-180.0, 180.0, 73))):
        raise ValueError("Modern results require canonical ascending latitude/longitude coordinates.")
    arrays = {key: np.asarray(getattr(result, key)).copy() for key in
              ("positive_counts", "negative_counts", "positive_ratio", "negative_ratio", "latitudes", "longitudes")}
    for polarity in ("positive", "negative"):
        counts, ratio = arrays[polarity + "_counts"], arrays[polarity + "_ratio"]
        if (counts.shape != (71, 73) or ratio.shape != (71, 73) or not np.isfinite(counts).all() or
                not np.isfinite(ratio).all() or np.any((counts < 0) | (counts > hours)) or
                not np.equal(counts, np.floor(counts)).all() or not np.array_equal(ratio, counts / hours * 100.0)):
            raise ValueError("Inconsistent spatial count/ratio result.")
    if set(validity) != {"target_input_finite_counts", "initial_reference_input_finite_counts"}:
        raise ValueError("Missing input availability diagnostics.")
    for key, maximum in (("target_input_finite_counts", hours), ("initial_reference_input_finite_counts", 360)):
        value = np.asarray(validity[key])
        if (value.shape != (71, 73) or value.dtype.kind not in "iu" or np.any((value < 0) | (value > maximum))):
            raise ValueError("Invalid finite-input counts.")
        arrays[key] = value.copy()
    arrays.update(window_steps=np.array(hours), ratio_denominator=np.array(hours))
    return arrays


def _reference_checks(arrays, peaks):
    expected = dict(window_steps=120, finite_cells=5183, positive_maximum=10.0, negative_maximum=85.0,
        positive_points=[dict(latitude=-22.5, longitude=-155.0), dict(latitude=-22.5, longitude=-150.0)],
        negative_points=[dict(latitude=30.0, longitude=70.0)])
    checks = dict(window_steps=int(arrays["window_steps"]) == 120,
        finite_cells=all(np.isfinite(arrays[key]).sum() == 5183 for key in ("positive_ratio", "negative_ratio")),
        positive_maximum=bool(np.isclose(peaks["positive"]["maximum_ratio_percent"], 10.0)),
        negative_maximum=bool(np.isclose(peaks["negative"]["maximum_ratio_percent"], 85.0)),
        positive_points=peaks["positive"]["maximum_grid_points"] == expected["positive_points"],
        negative_points=peaks["negative"]["maximum_grid_points"] == expected["negative_points"])
    return dict(expected=expected, checks=checks, all_match=all(checks.values()))


def _experiment(selected, index, directory, review_bundle, modern_data_dir, code, environment):
    directory.mkdir()
    status = "not_performed"
    try:
        with (directory / "selection_record.json").open("xb") as handle:
            handle.write(selected["raw"])
        validity = _input_validity(selected["window"], selected["files"])
        # Final bundle, selection and original input hash checks, immediately before D.
        current = _selection(selected["path"], review_bundle, modern_data_dir, index)
        handoff._same(current["pin"], selected["pin"], "selection changed before computation")
        status = "failed_or_interrupted"
        result, status = _run_modern_d(current["window"], current["files"])
        if status not in ("executed", "test_double_only"):
            raise ValueError("Unknown computation status.")
        _write(directory / "execution_status.json", _state(status))
        after = _selection(selected["path"], review_bundle, modern_data_dir, index)
        handoff._same(after["pin"], selected["pin"], "selection changed during computation")
        arrays = _arrays(result, current["window"], validity)
        with (directory / "spatial_arrays.npz").open("xb") as handle:
            np.savez_compressed(handle, **arrays)
        _write_maps(result, current["window"], directory)
        peaks = _peaks(result)
        summary = dict(record_type="afghanistan_mvp_spatial_experiment", schema_version=1,
            experiment=_EXPERIMENTS[index], **_state(status), event=mvp01.EVENT,
            selection=current["pin"], parent_review_bundle=current["record"]["parent_review_bundle"],
            window=current["record"]["window"], parameters=dict(reference_days=15, k=3.0,
            grid_orientation="canonical", show_boundaries=False),
            input_files=current["record"]["modern_gim_inputs"]["required_daily_files"],
            source_hashes_rechecked_before_and_after_computation=True, environment=environment, code_sha256=code,
            spatial_anomalies=peaks, ratio_denominator=int(arrays["ratio_denominator"]),
            input_validity_scope=_VALIDITY_NOTE, effective_detector_valid_counts=None,
            historical_reference_checks=_reference_checks(arrays, peaks) if index == 0 else None,
            artifacts={name: mvp01._record(directory / name) for name in
                ("selection_record.json", "execution_status.json", "spatial_arrays.npz", "positive.png", "negative.png")})
        # Store artifact paths relative to this experiment for portable comparison.
        for name, artifact in summary["artifacts"].items():
            artifact["path"] = name
        _write(directory / "experiment_summary.json", summary)
        return arrays, summary
    except Exception as exc:
        try:
            _write(directory / "failure.json", dict(**_state(status), error_type=type(exc).__name__, error=str(exc)))
        except OSError:
            pass
        raise


def _differences(a, b):
    if not np.array_equal(a["latitudes"], b["latitudes"]) or not np.array_equal(a["longitudes"], b["longitudes"]):
        raise ValueError("Cannot compare different physical grids.")
    keys = ("positive_counts", "negative_counts", "positive_ratio", "negative_ratio",
            "target_input_finite_counts", "initial_reference_input_finite_counts", "ratio_denominator")
    return {**{key + "_b_minus_a": (np.asarray(b[key], dtype=np.int64) - np.asarray(a[key], dtype=np.int64)
                if key.endswith("_counts") or key == "ratio_denominator" else b[key] - a[key]) for key in keys},
            "latitudes": a["latitudes"].copy(), "longitudes": a["longitudes"].copy()}


def _report(summaries, statistics):
    lines = ["# Afghanistan dual-window comparison", "",
        f"Framework D status: **{summaries[0]['framework_d_execution']}**.", "",
        "| Experiment | Target hours / ratio denominator | Positive peak (%) | Negative peak (%) |",
        "| --- | ---: | ---: | ---: |"]
    for summary in summaries:
        peaks = summary["spatial_anomalies"]
        lines.append(f"| {summary['experiment']} | {summary['ratio_denominator']} | "
            f"{peaks['positive']['maximum_ratio_percent']} | {peaks['negative']['maximum_ratio_percent']} |")
        for polarity in ("positive", "negative"):
            lines.append(f"\n{summary['experiment']} {polarity} peak coordinates: "
                         f"{peaks[polarity]['maximum_grid_points']}.")
    lines += ["", "Cell-wise differences are B minus A; ratio differences are percentage points.",
        "Full count/ratio and input-availability differences are in `cellwise_differences.npz`.", ""]
    for key, value in statistics.items():
        lines.append(f"- {key}: min={value['minimum']}, max={value['maximum']}, "
                     f"mean={value['mean']}, changed cells={value['changed_cells']}.")
    lines += ["", f"Experiment A historical reference checks: {summaries[0]['historical_reference_checks']['all_match']}.",
        "The 144-hour result is not required to match the 120-hour reference.", _VALIDITY_NOTE,
        "Cluster 0 remains unexecuted. This retrospective comparison establishes no precursor or causal finding.",
        "Windows Local Isolation: NOT VERIFIED", "Trusted Human Authorization: NOT VERIFIED",
        "Execution Eligibility: FALSE", ""]
    return "\n".join(lines)


def run_comparison(selection_a, selection_b, *, review_bundle, modern_data_dir, output_dir):
    """PROTECTED scientific execution proposal; requires separate scope approval.

    Tests replace the fixed private D/plot/data helpers with harmless doubles.
    There is no caller-provided executor, signing capability or trust override.
    """
    plan, selected = _prepare(selection_a, selection_b, review_bundle, modern_data_dir, output_dir)
    destination = Path(plan["output_directory"])
    code = {name: mvp01._record(_ROOT / name)["sha256"] for name in _CODE_FILES}
    environment = dict(python=platform.python_version(), numpy=version("numpy"), matplotlib=version("matplotlib"))
    destination.mkdir(parents=True, exist_ok=False)
    _write(destination / "comparison_plan.json", plan)
    arrays, summaries = [], []
    for index, (name, selection) in enumerate(zip(_EXPERIMENTS, selected)):
        values, summary = _experiment(selection, index, destination / name, review_bundle, modern_data_dir, code, environment)
        arrays.append(values)
        summaries.append(summary)
    if summaries[0]["framework_d_execution"] != summaries[1]["framework_d_execution"]:
        raise ValueError("Cannot mix actual and test-double computations.")
    differences = _differences(*arrays)
    with (destination / "cellwise_differences.npz").open("xb") as handle:
        np.savez_compressed(handle, **differences)
    statistics = {key: dict(minimum=float(value.min()), maximum=float(value.max()),
        mean=float(value.mean()), changed_cells=int(np.count_nonzero(value)))
        for key, value in differences.items() if key.endswith("_b_minus_a") and value.ndim == 2}
    with (destination / "comparison_report.md").open("xb") as handle:
        handle.write(_report(summaries, statistics).encode("utf-8"))
    comparison = dict(record_type="afghanistan_mvp_dual_window_comparison", schema_version=1,
        **_state(summaries[0]["framework_d_execution"]), difference_direction="B minus A; ratios in percentage points",
        experiments={name: summary for name, summary in zip(_EXPERIMENTS, summaries)},
        cluster_0_status=plan["cluster_0_status"], input_validity_scope=_VALIDITY_NOTE,
        ratio_denominator_change=int(differences["ratio_denominator_b_minus_a"]),
        cellwise_statistics=statistics,
        limitations=["Retrospective comparison; no precursor identification or causal inference.",
            "Extra target hours can change both counts and fixed-duration ratios.", _VALIDITY_NOTE,
            "Source hash snapshots do not establish OS custody or trusted human authorization."],
        artifacts={name: handoff._metadata((destination / name).read_bytes()) for name in
            ("cellwise_differences.npz", "comparison_report.md")} |
            {name + "/experiment_summary.json": handoff._metadata((destination / name / "experiment_summary.json").read_bytes())
             for name in _EXPERIMENTS})
    _write(destination / "comparison_summary.json", comparison)
    return destination / "comparison_summary.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "run"), help="run requires separately approved real-execution scope.")
    parser.add_argument("--selection-a", type=Path, required=True)
    parser.add_argument("--selection-b", type=Path, required=True)
    parser.add_argument("--review-bundle", type=Path, required=True)
    parser.add_argument("--modern-data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    keywords = dict(review_bundle=args.review_bundle, modern_data_dir=args.modern_data_dir, output_dir=args.output_dir)
    try:
        if args.operation == "plan":
            print(handoff._json(plan_comparison(args.selection_a, args.selection_b, **keywords)), end="")
        else:
            print(run_comparison(args.selection_a, args.selection_b, **keywords))
    except FileExistsError as exc:
        parser.exit(3, f"Output conflict: {exc}\n")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Comparison failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
