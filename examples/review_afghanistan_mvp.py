"""MVP-01: researcher-run Modern A -> saved B+C context -> review-only bundle.

Run ``python -m examples.review_afghanistan_mvp --help``. Supply explicit daily
NPZ paths, the original saved B+C summary and --cluster-ids (no default; the
flag without values explicitly requests abstention). The fixed analysis is
2022-05-22..2022-06-21 inclusive, with 15 reference days and multiplier 3.

This local example is not an Agent service or an authorization interface. It
does not recompute B/C, run D/Stage 2, plot, sign, access a Store, or select a
window for execution. Input hash rechecks detect ordinary changes, not hostile
concurrent replacement or authenticated source custody. Historical summary
paths/provenance and detailed TEC remain local; review before sharing outputs.

Output requires a new directory. Files are exclusively created, with the run
record last. On a write failure, retain the incomplete directory for inspection
and use a different destination; there is no overwrite, resume or cleanup mode.
Only a valid run record whose artifact hashes match describes a complete bundle.
"""

import argparse
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

from src.workflow.modern_temporal_input_adapter import load_temporal_tec_from_modern_gim
from src.workflow.planning_evidence import evidence_to_json
from src.workflow.scientific_request import dispatch_scientific_request


CASE_ID = "afghanistan_2022"
START = datetime(2022, 5, 22)
END = datetime(2022, 6, 21, 23)
REFERENCE_DAYS = 15
THRESHOLD_MULTIPLIER = 3.0
# Preserve the existing Framework A inputs independently of the USGS event.
INPUT_LATITUDE, INPUT_LONGITUDE = 33.02, 69.46
EVENT = dict(
    event_id="us7000hj3u", time_utc="2022-06-21T20:54:34Z", magnitude=6.0,
    latitude=33.020, longitude=69.464, depth_km=4.0,
    source_reference="https://earthquake.usgs.gov/earthquakes/eventpage/us7000hj3u/executive",
)
REFERENCE_WINDOW = dict(start_utc="2022-05-28T00:00:00Z",
                        end_utc="2022-06-01T23:00:00Z", inclusive_hours=120)
_ROOT = Path(__file__).resolve().parents[1]
_CODE_PATHS = (
    "examples/review_afghanistan_mvp.py", "src/workflow/scientific_request.py",
    "src/workflow/temporal_workflow.py", "src/workflow/planning_evidence.py",
    "src/workflow/window_planning.py", "src/workflow/modern_temporal_input_adapter.py",
    "src/data/modern_gim_bridge.py", "src/data/modern_gim_series.py",
    "src/data/modern_gim_loader.py", "src/temporal_anomaly/temporal_anomaly.py",
    "src/temporal_anomaly/tec_timeseries.py",
)


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"


def _record(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return dict(path=str(path), size_bytes=size, sha256=digest.hexdigest())


def build_request(selected_cluster_ids, *, provenance=None):
    """Fixed confirmed case; selections must be supplied explicitly, even []."""
    if (type(selected_cluster_ids) is not list or
            any(type(item) is not int or item < 0 for item in selected_cluster_ids) or
            len(set(selected_cluster_ids)) != len(selected_cluster_ids)):
        raise ValueError("Supply an explicit list of unique nonnegative integer cluster IDs.")
    return dict(
        schema_version=1, operation="temporal_review", case_id=CASE_ID,
        resources=dict(time_series="modern_case_tec", historical_summary="historical_bc"),
        analysis=dict(start_utc=START.isoformat() + "Z", end_utc=END.isoformat() + "Z"),
        input_time_convention="naive_utc", mode="retrospective",
        case_event=dict(case_id=CASE_ID, **{key: EVENT[key] for key in (
            "event_id", "time_utc", "source_reference")}),
        selected_cluster_ids=selected_cluster_ids.copy(),
        detector=dict(reference_days=REFERENCE_DAYS, threshold_multiplier=THRESHOLD_MULTIPLIER,
                      min_reference_samples=None), provenance=provenance,
    )


def _comparisons(proposal):
    return [dict(
        cluster_id=report["anchor"]["cluster_id"], selected=report["selected"],
        status=report["status"], reason=report["reason"],
        candidate_window=report["candidate_window"],
        differs_from_historical_reference=(None if report["candidate_window"] is None else
            any(report["candidate_window"][key] != REFERENCE_WINDOW[key] for key in REFERENCE_WINDOW)),
        framework_d_execution="not_performed",
    ) for report in proposal["anchor_reports"]]


def _note(proposal, comparisons):
    lines = ["# Afghanistan MVP-01 — review only", "",
             "Confirmed event: us7000hj3u, 2022-06-21T20:54:34Z, M6.0, "
             "(33.020, 69.464), depth 4.0 km.",
             "Framework A input coordinates remain (33.02, 69.46); see temporal evidence for the selected grid.", "",
             "Historical research reference: **2022-05-28T00:00:00Z to "
             "2022-06-01T23:00:00Z (120 hours)**, selected by the **Vision Model and Selected Window Rule**.",
             "This prior methodological output is retained independently of the current daily planner.", "",
             f"Current proposal status: {proposal['status']}. Explicit cluster IDs: "
             f"{[item['cluster_id'] for item in comparisons if item['selected']]}", ""]
    for item in comparisons:
        window = item["candidate_window"]
        if window is None:
            detail = f"{item['status']} ({item['reason']})"
        else:
            detail = (f"{window['start_utc']} to {window['end_utc']} "
                      f"({window['inclusive_hours']} hours); "
                      f"differs from historical reference: {item['differs_from_historical_reference']}")
        lines.append(f"- Cluster {item['cluster_id']}: {detail}.")
    lines += ["", "Differences are reported without changing the daily policy or truncating June 2.",
              "Candidates and the historical reference are separate methodological outputs, not selected execution windows.",
              "Framework D / Stage 2 was not executed; no six-day spatial result is predicted.",
              "Saved historical context was loaded, not newly recomputed. No precursor/causal finding is claimed.", "",
              "Windows Local Isolation: NOT VERIFIED",
              "Trusted Human Authorization: NOT VERIFIED", "Execution Eligibility: FALSE", ""]
    return "\n".join(lines)


def review(modern_files, historical_summary, output_dir, *, selected_cluster_ids):
    """Acquire explicit local inputs, dispatch once, and export unchanged V1 artifacts."""
    request = build_request(selected_cluster_ids)
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError("Use a new output directory; existing bundles are never overwritten.")
    files = sorted((Path(path).resolve(strict=True) for path in modern_files), key=str)
    if not files or len(set(files)) != len(files):
        raise ValueError("Supply a nonempty list of distinct Modern daily files.")
    summary_path = Path(historical_summary).resolve(strict=True)
    if summary_path in files:
        raise ValueError("The historical summary must be distinct from Modern files.")
    records = [_record(path) for path in files]
    summary_record = _record(summary_path)
    request["provenance"] = dict(
        sources=[dict(identity=record["path"], sha256=record["sha256"]) for record in records],
        processing_history="Explicit Modern daily NPZ inputs; existing bridge owns each day's 00..23 UTC maps; "
                           "existing nearest-grid adapter and detector unchanged. No B/C recomputation.",
    )
    series = load_temporal_tec_from_modern_gim(
        files, START, END, latitude=INPUT_LATITUDE, longitude=INPUT_LONGITUDE,
        reference_days=REFERENCE_DAYS,
    )
    temporal, historical, proposal = dispatch_scientific_request(
        request, time_series_id="modern_case_tec", time_series=series,
        historical_summary_id="historical_bc", historical_summary_path=summary_path,
    )
    if ([_record(path) for path in files] != records or _record(summary_path) != summary_record or
            historical["summary_artifact"]["sha256"] != summary_record["sha256"]):
        raise ValueError("An input changed during review; no complete bundle was published.")
    comparisons = _comparisons(proposal)
    artifacts = {
        "scientific_request.json": _json(request),
        "temporal_evidence.json": evidence_to_json(temporal),
        "historical_context.json": evidence_to_json(historical),
        "window_proposal.json": _json(proposal),
        "review_note.md": _note(proposal, comparisons),
    }
    run_record = dict(
        record_type="afghanistan_mvp_review_run", schema_version=1, case_id=CASE_ID,
        review_only=True, execution_eligible=False, windows_local_isolation="NOT VERIFIED",
        trusted_human_authorization="NOT VERIFIED", framework_d_execution="not_performed",
        confirmed_event=dict(EVENT), event_metadata_basis="researcher_confirmed_record; not identity authentication",
        scientific_input_coordinates=dict(latitude=INPUT_LATITUDE, longitude=INPUT_LONGITUDE),
        selected_cluster_ids=selected_cluster_ids.copy(),
        historical_research_reference=dict(method="Vision Model and Selected Window Rule",
                                           window=dict(REFERENCE_WINDOW), selected_for_execution=False),
        candidate_comparisons=comparisons, selected_execution_window=None,
        inputs=dict(modern_daily_files=records, historical_summary=summary_record),
        input_hashes_rechecked_after_review=True,
        environment=dict(python=platform.python_version(), numpy=version("numpy")),
        code_sha256={name: _record(_ROOT / name)["sha256"] for name in _CODE_PATHS},
        artifacts={name: dict(size_bytes=len(text.encode("utf-8")),
                              sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
                   for name, text in artifacts.items()},
    )
    # Serialize before acquiring the fresh output directory; publish the index last.
    artifacts["run_record.json"] = _json(run_record)
    destination.mkdir(parents=True, exist_ok=False)
    for name, text in artifacts.items():
        with (destination / name).open("xb") as handle:
            handle.write(text.encode("utf-8"))
    return destination / "run_record.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modern-files", type=Path, nargs="+", required=True)
    parser.add_argument("--historical-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New local-only output directory.")
    parser.add_argument("--cluster-ids", type=int, nargs="*", required=True,
                        help="Explicit researcher selection; flag with no values requests abstention.")
    args = parser.parse_args(argv)
    try:
        result = review(args.modern_files, args.historical_summary, args.output_dir,
                        selected_cluster_ids=args.cluster_ids)
    except FileExistsError as exc:
        parser.exit(3, f"Output conflict: {exc}\n")
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"Review failed: {exc}\n")
    print(f"Saved review-only bundle: {result}")
    print("Windows Local Isolation: NOT VERIFIED\nTrusted Human Authorization: NOT VERIFIED\nExecution Eligibility: FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
