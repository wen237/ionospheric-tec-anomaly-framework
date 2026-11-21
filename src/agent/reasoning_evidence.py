"""Host-bound, read-only views of saved scientific investigation results."""

from pathlib import PurePosixPath

from src.agent.epz_evidence import host_binding
from src.workflow.space_weather_evidence import validate_space_weather_report
from src.workflow.window_sensitivity import (
    build_window_diagnostic, cell_summary, compare_saved_counts, hourly_rows,
    load_hourly_snapshot, masks,
)


KINDS = ("window_sensitivity", "space_weather")


def bindings(mode, declarations, maximum_bytes):
    """File identities/pins come from the host, never model tool arguments."""
    if declarations is None:
        return {}
    if type(declarations) is not dict or not set(declarations) <= set(KINDS):
        raise ValueError("Unsupported reasoning evidence binding")
    result = {}
    for kind, pin in declarations.items():
        if type(pin) is not dict or set(pin) != {"artifact", "sha256", "size_bytes"}:
            raise ValueError("Reasoning bindings require artifact, sha256 and size_bytes")
        if kind == "window_sensitivity" and mode != "post_spatial":
            raise ValueError("Window sensitivity requires Post-Spatial mode")
        # Reuse the existing relative-identity/pin rules. Space weather can be
        # inspected before spatial verification; no spatial path is probed.
        bound = host_binding("post_spatial", pin["artifact"], pin["sha256"], pin["size_bytes"], maximum_bytes)
        if bound is None:
            raise ValueError("A declared reasoning source requires complete pins")
        result[kind] = bound
    return result


def load_bound(evidence, kind, pin):
    from src.agent.scientific_evidence_tools import compact, strict_json
    from src.workflow.space_weather_evidence import metadata

    raw = evidence._bytes(pin["artifact"])
    if metadata(raw) != {key: pin[key] for key in ("sha256", "size_bytes")}:
        raise ValueError("Reasoning evidence pin mismatch")
    report = strict_json(raw)
    if report["case_id"] != evidence.bundle["record"]["case_id"]:
        raise ValueError("Reasoning case differs from the review bundle")
    if kind == "space_weather":
        if compact(report) != compact(validate_space_weather_report(report)):
            raise ValueError("Inconsistent space-weather report")
        provenance = report["provenance"]
        if (provenance["provider"] != "NASA OMNIWeb" or provenance["product"] != "OMNI2 hourly"
                or provenance["retrieval_performed"] is not False):
            raise ValueError("Unsupported space-weather provenance")
        projection = dict(report=report)
        additions = {pin["artifact"]: raw}
    else:
        if evidence.status.get("spatial") != "validated_snapshot":
            raise ValueError("Saved spatial comparison is required")
        record = report["diagnostic"]
        if (report["record_type"] != "saved_window_investigation" or report["schema_version"] != 1
                or report["event"] != evidence.bundle["record"]["confirmed_event"]):
            raise ValueError("Unsupported window investigation")
        sidecar = report["hourly_snapshot"]
        if set(sidecar) != {"artifact", "sha256", "size_bytes"} or sidecar["artifact"] != "hourly_snapshot.npz":
            raise ValueError("Unexpected hourly sidecar")
        identity = str(PurePosixPath(pin["artifact"]).parent / sidecar["artifact"])
        hourly_raw = evidence._bytes(identity)
        if metadata(hourly_raw) != {key: sidecar[key] for key in ("sha256", "size_bytes")}:
            raise ValueError("Hourly snapshot pin mismatch")
        a = load_hourly_snapshot(hourly_raw)
        # Recompute saved-observation summaries only. No detector is called.
        recomputed = build_window_diagnostic(a, record["baseline"], record["extended"],
                                            case_id=report["case_id"], selected_cells=record["selected_cells"])
        if compact(record) != compact(recomputed):
            raise ValueError("Inconsistent window diagnostic")
        for segment, label in (("baseline", "A"), ("extended", "B")):
            if record[segment] != evidence.summaries[label]["window"]:
                raise ValueError("Diagnostic/saved experiment window mismatch")
        checks = compare_saved_counts(a, record["baseline"], record["extended"],
                                      {"baseline": evidence.arrays["A"], "extended": evidence.arrays["B"]})
        if checks != report["saved_comparison_checks"] or not all(checks.values()):
            raise ValueError("Hourly evidence differs from saved spatial counts")
        sources = report["source_evidence"]
        if not sources or any(identity not in evidence.sources or evidence.sources[identity] != meta
                              for identity, meta in sources.items()):
            raise ValueError("Diagnostic source evidence differs from the review snapshot")
        originals = evidence.summaries["B"]["input_files"]
        original_pins = {s["filename"]: {k: s[k] for k in ("sha256", "size_bytes")} for s in originals}
        if report["original_inputs"] != original_pins:
            raise ValueError("Hourly evidence does not declare the approved original input hashes")
        projection = dict(report=record, snapshot=a, binding_report=report)
        additions = {pin["artifact"]: raw, identity: hourly_raw}
    # Register atomically only once the complete result validated.
    for identity, data in additions.items():
        evidence.raw[identity], evidence.sources[identity] = data, metadata(data)
    return projection


def dispatch(evidence, name, args):
    if name.startswith("get_space_weather") or name == "inspect_space_weather_interval":
        view = evidence.reasoning_views["space_weather"]["report"]
        refs = evidence._refs(evidence.reasoning_bindings["space_weather"]["artifact"])
        if name == "get_space_weather_summary":
            return {key: view[key] for key in ("case_id", "window", "provenance", "resolution", "summary", "absent_utc_rows", "limitations")}, refs
        from src.workflow.window_sensitivity import bounds
        interval = bounds(args)
        if (interval["inclusive_hours"] > 24 or interval["start_utc"] < view["window"]["start_utc"]
                or interval["end_utc"] > view["window"]["end_utc"]):
            raise ValueError("Space-weather interval must be within coverage and at most 24 hours")
        rows = [r for r in view["rows"] if interval["start_utc"] <= r["timestamp_utc"] <= interval["end_utc"]]
        return dict(window=interval, rows=rows, resolution=view["resolution"], provenance=view["provenance"]), refs
    view = evidence.reasoning_views["window_sensitivity"]
    d, a = view["report"], view["snapshot"]
    pin = evidence.reasoning_bindings["window_sensitivity"]
    refs = evidence._refs(pin["artifact"], str(PurePosixPath(pin["artifact"]).parent / "hourly_snapshot.npz"))
    if name == "get_window_contribution_summary":
        return {key: value for key, value in d.items() if key not in ("additional_hourly", "selected_cells")}, refs
    if name == "inspect_window_contribution_cell":
        return cell_summary(a, masks(a, d["baseline"], d["extended"]), **args), refs
    rows = hourly_rows(a, d["baseline"], d["extended"], **args)
    return dict(rows=rows, requested_coordinates={key: args[key] for key in ("latitude", "longitude")},
                actual_grid=cell_summary(a, masks(a, d["baseline"], d["extended"]), args["latitude"], args["longitude"])["actual_grid"],
                decision_codes={"missing_or_unevaluated": -1, "non_anomalous": 0, "anomalous": 1}), refs
