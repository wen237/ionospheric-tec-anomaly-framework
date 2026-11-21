"""Researcher-invoked offline diagnostics; Agent tools only read saved results.

window derives actual hourly observations from hash-matched approved originals.
space-weather adapts existing toolkit exports or saved responses without retrieval.
demo uses FakeModel to exercise retrieval, proposals and saved-result reassessment.
All outputs require fresh destinations. No Framework D/Stage 2 entry point is run.
"""

import argparse
from importlib.metadata import version
from pathlib import Path
import platform

import numpy as np

from src.agent.scientific_evidence_tools import EvidenceTools, compact, strict_json
from src.workflow.space_weather_evidence import metadata, prepare_space_weather_report
from src.workflow.window_sensitivity import build_window_diagnostic, compare_saved_counts, make_hourly_snapshot


def write_json(path, value):
    raw = (compact(value) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(raw)
    return metadata(raw)


def derive_window_investigation(evidence_root, modern_data_dir, output_dir):
    """Explicit offline diagnostic command, never an Agent-dispatched operation."""
    from src.agent.scientific_review_agent import validate_output_dir
    from src.data.modern_gim_bridge import load_modern_gim_window
    from src.spatial_verification.spatial_anomaly import compute_hourly_spatial_anomalies
    from src.workflow.window_sensitivity import bounds

    evidence = EvidenceTools(evidence_root, "post_spatial")
    if evidence.status.get("spatial") != "validated_snapshot":
        raise ValueError("Validated saved spatial experiments are required")
    target = validate_output_dir(output_dir, evidence)
    if not target.is_relative_to(evidence.root):
        raise ValueError("Window diagnostic output must be beneath the evidence root")
    data_root = Path(modern_data_dir).resolve(strict=True)
    if target.is_relative_to(data_root):
        raise ValueError("Output must be outside original inputs")
    baseline, extended = (bounds(evidence.summaries[label]["window"]) for label in ("A", "B"))
    sources = evidence.summaries["B"]["input_files"]
    files, pins = [], {}
    for source in sources:
        name = source["filename"]
        if Path(name).name != name:
            raise ValueError("Source identity must be a basename")
        path = data_root / name
        pin = metadata(path.read_bytes())
        if pin != {key: source[key] for key in ("sha256", "size_bytes")}:
            raise ValueError("Original input differs from the accepted saved source hashes")
        files.append(path)
        pins[name] = pin
    start, end = (datetime_utc(extended[key]) for key in ("start_utc", "end_utc"))
    data = load_modern_gim_window(files, start, end, reference_days=15)
    hourly = compute_hourly_spatial_anomalies(data.tec.reshape(len(data.tec), -1), 24, 15, data.window_steps,
                                              3.0, data.lat, data.lon)
    a = make_hourly_snapshot(hourly, data.timestamps[-data.window_steps:], data.lat, data.lon)
    event = evidence.bundle["record"]["confirmed_event"]
    selected = [dict(latitude=event["latitude"], longitude=event["longitude"])]
    d = build_window_diagnostic(a, baseline, extended, case_id=evidence.bundle["record"]["case_id"], selected_cells=selected)
    checks = compare_saved_counts(a, baseline, extended, {"baseline": evidence.arrays["A"], "extended": evidence.arrays["B"]})
    if not all(checks.values()):
        raise ValueError("Derived hourly observations differ from accepted A/B counts; accepted outputs were not changed")
    for path in files:
        if metadata(path.read_bytes()) != pins[path.name]:
            raise ValueError("Original input changed during diagnostics")
    evidence.recheck()
    target.mkdir(parents=True, exist_ok=False)
    with (target / "hourly_snapshot.npz").open("xb") as stream:
        np.savez_compressed(stream, **a)
    root = Path(__file__).resolve().parents[1]
    code_files = ("examples/investigate_scientific_reasoning.py", "src/workflow/window_sensitivity.py",
                  "src/spatial_verification/spatial_anomaly.py", "src/data/modern_gim_bridge.py",
                  "src/data/modern_gim_loader.py", "src/data/modern_gim_series.py")
    report = dict(record_type="saved_window_investigation", schema_version=1, case_id=d["case_id"], event=event,
                  diagnostic=d, original_inputs=pins, source_evidence=dict(evidence.sources),
                  saved_comparison_checks=checks,
                  hourly_snapshot=dict(artifact="hourly_snapshot.npz", **metadata((target / "hourly_snapshot.npz").read_bytes())),
                  code={name: metadata((root / name).read_bytes()) for name in code_files},
                  environment=dict(python=platform.python_version(), numpy=version("numpy")),
                  authorization_scope="User-requested offline hourly diagnostics from approved original inputs; no new Framework D execution or future-experiment approval")
    pin = write_json(target / "window_diagnostic.json", report)
    identity = (target / "window_diagnostic.json").relative_to(evidence.root).as_posix()
    write_json(target / "binding_candidates.json", {"window_sensitivity": dict(artifact=identity, **pin)})
    return target / "window_diagnostic.json"


def datetime_utc(value):
    from datetime import datetime
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def offline_demo(evidence_root, declarations, output_dir, *, reassessment_of=None):
    """A scripted offline integration demonstration, explicitly not an LLM study.

    New approved saved reports can be rebound for a new review. A prior review
    reference is recorded for traceability; its prose is not injected as evidence.
    """
    from src.agent.follow_up_experiments import window_comparison_proposal
    from src.agent.scientific_review_agent import FakeModel, _abstention, run_agent, save_run

    evidence = EvidenceTools(evidence_root, "post_spatial", reasoning_bindings=declarations)
    if "window_sensitivity" not in declarations:
        raise ValueError("The window investigation demo requires bound hourly window evidence")
    if any(evidence.status.get(kind) != "validated_snapshot" for kind in declarations):
        raise ValueError("All declared saved results must validate")
    sequence = [("get_evidence_inventory", {}), ("get_temporal_summary", {}), ("get_historical_context", {}),
                ("compare_spatial_experiments", {}), ("get_window_contribution_summary", {})]
    if "window_sensitivity" in declarations:
        d = evidence.reasoning_views["window_sensitivity"]["report"]
        extra = d["additional_utc_hours"]
        day = extra[0][:10]
        on_day = [s for s in extra if s.startswith(day)]
        sequence.append(("inspect_window_contribution_hours", dict(start_utc=on_day[0], end_utc=on_day[-1],
                                                                  latitude=evidence.bundle["record"]["confirmed_event"]["latitude"],
                                                                  longitude=evidence.bundle["record"]["confirmed_event"]["longitude"])))
    if "space_weather" in declarations:
        sequence.append(("get_space_weather_summary", {}))
        w = evidence.reasoning_views["space_weather"]["report"]["window"]
        first_day = w["start_utc"][:10] + "T23:00:00Z"
        sequence.append(("inspect_space_weather_interval", dict(start_utc=w["start_utc"], end_utc=min(w["end_utc"], first_day))))

    def model(history, available):
        outputs = [strict_json(item["output"]) for item in history if item.get("type") == "function_call_output"]
        if len(outputs) < len(sequence):
            name, args = sequence[len(outputs)]
            return [dict(name=name, arguments=compact(args), call_id="inspect_" + str(len(outputs)))]
        final = _abstention("Evidence supports a bounded investigation for human review; neither window is selected.")
        final["follow_up_experiments"] = []
        window = next((r for r in outputs if r.get("ok") and r.get("data", {}).get("record_type") == "window_sensitivity_diagnostic"), None)
        if window is not None:
            data, rid = window["data"], window["result_id"]
            pointers = ["/data/baseline/inclusive_hours", "/data/extended/inclusive_hours",
                        "/data/contribution/negative/lower_additional_anomaly_rate_than_baseline",
                        "/data/contribution/negative/additional_anomaly_share_of_extended"]
            from src.agent.scientific_review_agent import _resolve
            for pointer in pointers:
                ref = dict(result_id=rid, pointer=pointer)
                value = _resolve(ref, {rid: window})
                final["observed_facts"].append(dict(**ref, value_json=compact(value)))
            final["follow_up_experiments"] = [window_comparison_proposal(data, rid)]
            final["recommendation"].update(action="propose_follow_up", evidence=[dict(result_id=rid, pointer=pointers[0])])
        weather = next((r for r in outputs if r.get("ok") and "summary" in r.get("data", {}) and "resolution" in r["data"]), None)
        if weather is None:
            final["missing_evidence"] = ["No validated Kp, Dst or F10.7 observations were supplied; physical context remains unknown."]
        else:
            for key in ("kp", "dst", "f107"):
                final["observed_facts"].append(dict(result_id=weather["result_id"], pointer=f"/data/summary/{key}/maximum",
                                                     value_json=compact(weather["data"]["summary"][key]["maximum"])))
            final["limitations"].append("Hourly export rows do not imply independent hourly geomagnetic and solar measurements.")
        return [dict(name="submit_assessment", arguments=compact(final), call_id="submit_review")]

    run = run_agent(FakeModel(model), evidence,
                    "Investigate added-hour contributions and available space-weather context, then propose a controlled follow-up without selecting a window.",
                    reasoning_enabled=True)
    if reassessment_of is not None:
        prior = Path(reassessment_of)
        prior_raw = prior.read_bytes()
        prior_record = strict_json(prior_raw)
        if prior_record.get("case_id") != run["case_id"]:
            raise ValueError("Prior review case differs from reassessment")
        run["reassessment_of"] = dict(identity=prior.name, **metadata(prior_raw),
                                       scope="New host-bound saved evidence inspected; no prior narrative treated as a scientific result")
    return save_run(output_dir, run, evidence)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    window = commands.add_parser("window", help="Explicitly derive hourly diagnostics from accepted original GIM files")
    window.add_argument("--evidence-root", type=Path, required=True)
    window.add_argument("--modern-data-dir", type=Path, required=True)
    window.add_argument("--output-dir", type=Path, required=True)
    weather = commands.add_parser("space-weather", help="Offline adapter; never downloads data")
    weather.add_argument("--input", type=Path, required=True)
    weather.add_argument("--toolkit-module", type=Path, required=True)
    weather.add_argument("--source-format", choices=("csv", "omni_response"), default="csv")
    weather.add_argument("--case-id", required=True)
    weather.add_argument("--start-utc", required=True)
    weather.add_argument("--end-utc", required=True)
    weather.add_argument("--output", type=Path, required=True)
    demo = commands.add_parser("demo", help="Offline FakeModel demonstration; no paid LLM calls")
    demo.add_argument("--evidence-root", type=Path, required=True)
    demo.add_argument("--bindings", type=Path, required=True)
    demo.add_argument("--output-dir", type=Path, required=True)
    demo.add_argument("--reassessment-of", type=Path, help="Prior saved scientific_assessment.json; reference only")
    args = parser.parse_args(argv)
    if args.command == "window":
        print(derive_window_investigation(args.evidence_root, args.modern_data_dir, args.output_dir))
    elif args.command == "space-weather":
        if args.output.exists():
            raise FileExistsError("Space-weather output must be fresh")
        report = prepare_space_weather_report(args.input, args.toolkit_module,
                    dict(start_utc=args.start_utc, end_utc=args.end_utc), case_id=args.case_id, source_format=args.source_format)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        pin = write_json(args.output, report)
        print(compact(dict(artifact=args.output.name, **pin)))
    else:
        print(offline_demo(args.evidence_root, strict_json(args.bindings.read_bytes()), args.output_dir, reassessment_of=args.reassessment_of))


if __name__ == "__main__":
    main()
