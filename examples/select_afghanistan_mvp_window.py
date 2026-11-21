"""MVP-02A: explicit researcher window selection and non-executing Modern handoff.

Use --review-bundle DIR --modern-data-dir DIR with exactly one of:
  --cluster-id N [--justification TEXT] --output-dir NEW_DIR
  --start-utc UTC --end-utc UTC --justification TEXT --output-dir NEW_DIR
  --inspect

--inspect validates the bundle and inventories all candidates plus the historical
reference without choosing or saving a selection. Required daily files must match
unambiguous original MVP-01 source filenames and SHA-256 pins. Missing, ambiguous
or mismatched sources cannot pass source-integrity readiness. This is separate
from NPZ content validation and numerical correctness, which are not performed.
Future execution must recheck source integrity immediately before computation.
Independent target bounds must remain within saved temporal analysis coverage.

Only the six fixed bundle files and required daily filenames under the supplied
Modern directory are read. Recorded source/code paths remain inert provenance.
Hash/contract consistency is not authenticated origin, human authorization or OS
isolation. The existing pure planner revalidates saved evidence/proposal without
rerunning a detector. No D, Stage 2, plotting, signing or Store API is imported.
"""

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re

from examples import review_afghanistan_mvp as mvp01
from src.workflow.explicit_window import select_explicit_window
from src.workflow.planning_evidence import _provenance, _strict_copy
from src.workflow.window_planning import plan_anchor_based_daily_windows


_ARTIFACTS = ("scientific_request.json", "temporal_evidence.json", "historical_context.json",
              "window_proposal.json", "review_note.md")
_RUN_FIELDS = set("artifacts candidate_comparisons case_id code_sha256 confirmed_event environment "
                  "event_metadata_basis execution_eligible framework_d_execution historical_research_reference "
                  "input_hashes_rechecked_after_review inputs record_type review_only schema_version "
                  "scientific_input_coordinates selected_cluster_ids selected_execution_window "
                  "trusted_human_authorization windows_local_isolation".split())
_COMPUTED_SOURCE = "computed:temporal-review-input-series-v1"


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n"


def _same(actual, expected, name):
    if _json(actual) != _json(expected):
        raise ValueError(f"Mismatched {name}.")


def _metadata(raw):
    return dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}.")
            result[key] = value
        return result

    def reject(value):
        raise ValueError(f"Invalid JSON constant: {value}.")

    return _strict_copy(json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject))


def _read(root, name):
    path = root / name  # name is always one of the fixed local artifact names.
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing or redirected bundle file: {name}.")
    return path.read_bytes()


def _source_record(value):
    if (type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"} or
            type(value["path"]) is not str or not value["path"].strip() or
            type(value["size_bytes"]) is not int or value["size_bytes"] < 0 or
            type(value["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])):
        raise ValueError("Malformed scientific source record.")


def validate_bundle(review_bundle):
    """Verify all five exact artifacts and their cross-contract bindings, read-only."""
    root = Path(review_bundle).resolve(strict=True)
    record_raw = _read(root, "run_record.json")
    record = _decode(record_raw)
    if type(record) is not dict or set(record) != _RUN_FIELDS:
        raise ValueError("Incomplete or unsupported MVP-01 run record.")
    if type(record["artifacts"]) is not dict or set(record["artifacts"]) != set(_ARTIFACTS):
        raise ValueError("Exactly five MVP-01 artifacts are required.")
    raw = {name: _read(root, name) for name in _ARTIFACTS}
    for name, content in raw.items():
        _same(record["artifacts"][name], _metadata(content), f"artifact hash/size: {name}")
    try:
        request, temporal, historical, proposal = (_decode(raw[name]) for name in _ARTIFACTS[:4])
        _same(request, mvp01.build_request(record["selected_cluster_ids"], provenance=request["provenance"]),
              "MVP-01 request case/event/parameters")
        for name, expected in dict(record_type="afghanistan_mvp_review_run", schema_version=1,
            case_id=mvp01.CASE_ID, confirmed_event=mvp01.EVENT,
            scientific_input_coordinates=dict(latitude=mvp01.INPUT_LATITUDE, longitude=mvp01.INPUT_LONGITUDE),
            review_only=True, execution_eligible=False, framework_d_execution="not_performed",
            trusted_human_authorization="NOT VERIFIED", windows_local_isolation="NOT VERIFIED",
            selected_execution_window=None, input_hashes_rechecked_after_review=True).items():
            _same(record[name], expected, name)
        _same(record["historical_research_reference"], dict(method="Vision Model and Selected Window Rule",
              window=mvp01.REFERENCE_WINDOW, selected_for_execution=False), "historical reference")
        if (type(record["environment"]) is not dict or set(record["environment"]) != {"python", "numpy"} or
                any(type(v) is not str or not v.strip() for v in record["environment"].values()) or
                type(record["event_metadata_basis"]) is not str or not record["event_metadata_basis"].strip() or
                type(record["code_sha256"]) is not dict or not record["code_sha256"] or
                any(type(k) is not str or not k.strip() or type(v) is not str or
                    not re.fullmatch(r"[0-9a-f]{64}", v) for k, v in record["code_sha256"].items())):
            raise ValueError("Incomplete run provenance metadata.")
        _same(temporal["case_id"], request["case_id"], "evidence case")
        _same(temporal["input_time_convention"], request["input_time_convention"], "UTC convention")
        _same({key: temporal["analysis"][key] for key in request["analysis"]}, request["analysis"], "analysis bounds")
        _same(temporal["parameters"], dict(reference_days=15, threshold_multiplier=3.0,
                                           min_reference_samples=15), "detector parameters")
        _same({key: temporal["location"]["requested_" + key] for key in ("latitude", "longitude")},
              record["scientific_input_coordinates"], "scientific input coordinates")
        inputs = record["inputs"]
        if type(inputs) is not dict or set(inputs) != {"modern_daily_files", "historical_summary"}:
            raise ValueError("Incomplete input provenance.")
        sources = inputs["modern_daily_files"]
        if type(sources) is not list or not sources:
            raise ValueError("Missing Modern input provenance.")
        for source in [*sources, inputs["historical_summary"]]:
            _source_record(source)  # Validate declarations; never open these recorded paths.
        identities = [source["path"] for source in sources]
        if (len(set(identities)) != len(identities) or _COMPUTED_SOURCE in identities or
                inputs["historical_summary"]["path"] in identities):
            raise ValueError("Ambiguous input provenance.")
        declared = _provenance(request["provenance"])
        _same(declared["sources"], [dict(identity=s["path"], sha256=s["sha256"]) for s in sources],
              "request/source provenance")
        bound_sources = temporal["provenance"]["sources"]
        if (type(bound_sources) is not list or len(bound_sources) != len(sources) + 1 or
                set(bound_sources[-1]) != {"identity", "sha256"} or
                bound_sources[-1]["identity"] != _COMPUTED_SOURCE or
                not re.fullmatch(r"[0-9a-f]{64}", str(bound_sources[-1]["sha256"]))):
            raise ValueError("Missing full-series fingerprint binding.")
        _same(temporal["provenance"], {**declared, "sources": declared["sources"] + [bound_sources[-1]]},
              "evidence/source provenance")
        summary = inputs["historical_summary"]
        _same(historical["summary_artifact"], dict(identity=summary["path"], sha256=summary["sha256"],
              size_bytes=summary["size_bytes"], hash_verification="computed_from_read_bytes"), "historical summary binding")
        rebuilt = plan_anchor_based_daily_windows(temporal, historical, case_event=request["case_event"],
            selected_cluster_ids=request["selected_cluster_ids"], mode=request["mode"])
        _same(proposal, rebuilt, "saved proposal/evidence/candidates")
        _same(record["candidate_comparisons"], mvp01._comparisons(rebuilt), "record candidate comparisons")
        _same(raw["review_note.md"].decode("utf-8"), mvp01._note(rebuilt, record["candidate_comparisons"]),
              "review note")
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError("Incomplete or inconsistent MVP-01 scientific bundle.") from exc
    binding = dict(directory=str(root), run_record=_metadata(record_raw), artifacts=record["artifacts"],
                   verification="exact_bytes_and_scientific_contract_consistency; origin_not_authenticated")
    return dict(record=record, proposal=proposal, binding=binding,
                analysis_coverage={key: temporal["analysis"][key] for key in ("start_utc", "end_utc")})


def _unchanged(binding):
    root = Path(binding["directory"])
    for name, expected in {"run_record.json": binding["run_record"], **binding["artifacts"]}.items():
        _same(_metadata(_read(root, name)), expected, "bundle changed during handoff")


def _window(start, end):
    window = select_explicit_window(start, end)
    event_time = datetime.fromisoformat(mvp01.EVENT["time_utc"].replace("Z", "+00:00"))
    if window.end_time >= event_time:
        raise ValueError("Handoff samples must precede the confirmed event; post-event bounds are unsupported.")
    return window


def _bounds(window):
    return dict(start_utc=window.start_time.isoformat().replace("+00:00", "Z"),
                end_utc=window.end_time.isoformat().replace("+00:00", "Z"),
                inclusive_hours=(window.end_time - window.start_time) // timedelta(hours=1) + 1)


def _inventory(modern_data_dir, window, original_sources):
    root = Path(modern_data_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Modern data directory must be an explicit directory.")
    try:
        reference_start = window.start_time - timedelta(days=15)
        reference_end = window.start_time - timedelta(hours=1)
    except OverflowError as exc:
        raise ValueError("Reference interval exceeds the UTC calendar.") from exc
    # Pure lexical matching supports both Windows and POSIX source spellings.
    # Never resolve/open a source-recorded path, including to break a name tie.
    source_index = {}
    for source in original_sources:
        source_index.setdefault(PureWindowsPath(source["path"]).name.casefold(), []).append(source)
    required, missing, invalid, source_issues = [], [], [], []
    day = reference_start.date()
    while day <= window.end_time.date():
        name = f"codg{day.timetuple().tm_yday:03d}0.{day.year % 100:02d}i.npz"
        path = root / name
        item = dict(date_utc=day.isoformat(), filename=name, path=str(path))
        if path.is_symlink():
            invalid.append(dict(filename=name, reason="redirected_file"))
        elif not path.exists():
            missing.append(name)
        elif not path.is_file():
            invalid.append(dict(filename=name, reason="not_regular_file"))
        else:
            try:
                metadata = mvp01._record(path)
                item.update(size_bytes=metadata["size_bytes"], sha256=metadata["sha256"])
            except OSError as exc:
                invalid.append(dict(filename=name, reason=f"unreadable_file: {exc}"))
        matches = source_index.get(name.casefold(), [])
        if not matches:
            item["source_consistency"] = "missing_source_identity"
            source_issues.append(dict(filename=name, reason="missing_source_identity"))
        elif len(matches) != 1:
            item["source_consistency"] = "ambiguous_source_identity"
            source_issues.append(dict(filename=name, reason="ambiguous_source_identity",
                                      source_identities=[source["path"] for source in matches]))
        else:
            item["original_source"] = dict(matches[0])
            item["source_consistency"] = "current_input_unavailable"
            if "sha256" in item:
                item["source_consistency"] = "matched" if item["sha256"] == matches[0]["sha256"] else "sha256_mismatch"
                if item["source_consistency"] == "sha256_mismatch":
                    source_issues.append(dict(filename=name, reason="sha256_mismatch",
                        source_identity=matches[0]["path"], expected_sha256=matches[0]["sha256"],
                        current_sha256=item["sha256"]))
        required.append(item)
        day += timedelta(days=1)
    names = {item["filename"] for item in required}
    extra = sorted(path.name for path in root.iterdir() if path.name not in names)
    present = not missing and not invalid
    consistent = all(item["source_consistency"] == "matched" for item in required)
    return dict(data_directory=str(root), target=_bounds(window), reference_days=15,
        reference=dict(start_utc=reference_start.isoformat().replace("+00:00", "Z"),
                       end_utc=reference_end.isoformat().replace("+00:00", "Z"), inclusive_hours=360),
        threshold_multiplier=3.0, required_daily_files=required, missing_files=missing, invalid_files=invalid,
        extra_directory_entries=extra, required_files_present=present,
        original_sources_consistent=consistent, source_consistency_issues=source_issues,
        source_integrity_ready=present and consistent, recheck_before_computation_required=True,
        grid_orientation="canonical", latitude_order="ascending_physical_latitude",
        daily_maps="owning_file_00_to_23_utc; exclude_25th_map",
        npz_content_validation="not_performed", numerical_correctness="not_verified")


def inspect_handoff(review_bundle, modern_data_dir):
    """Read-only readiness for all eligible candidates/reference; no choice or output."""
    bundle = validate_bundle(review_bundle)
    sources = bundle["record"]["inputs"]["modern_daily_files"]
    inventories = []
    for report in bundle["proposal"]["anchor_reports"]:
        if report["status"] == "candidate":
            value = report["candidate_window"]
            inventories.append(dict(cluster_id=report["anchor"]["cluster_id"],
                inventory=_inventory(modern_data_dir, _window(value["start_utc"], value["end_utc"]), sources)))
    reference = mvp01.REFERENCE_WINDOW
    reference_inventory = _inventory(modern_data_dir, _window(reference["start_utc"], reference["end_utc"]), sources)
    _unchanged(bundle["binding"])
    return dict(parent_review_bundle=bundle["binding"], candidate_inventories=inventories,
                historical_reference_inventory=reference_inventory, selection_made=False,
                review_only=True, execution_eligible=False, framework_d_execution="not_performed",
                windows_local_isolation="NOT VERIFIED", trusted_human_authorization="NOT VERIFIED")


def select_window(review_bundle, modern_data_dir, output_dir, *, cluster_id=None,
                  start_utc=None, end_utc=None, justification=None):
    """Record only the explicit local choice; candidate 'selected' is not approval."""
    if cluster_id is not None:
        if type(cluster_id) is not int or cluster_id < 0 or start_utc is not None or end_utc is not None:
            raise ValueError("Use either one nonnegative integer cluster ID or independent UTC bounds.")
    elif start_utc is None or end_utc is None:
        raise ValueError("An explicit candidate or independent UTC selection is required.")
    if justification is not None and (type(justification) is not str or not justification.strip()):
        raise ValueError("Scientific justification must be nonempty text.")
    if cluster_id is None and justification is None:
        raise ValueError("Independent selection requires a scientific justification.")
    requested_output = Path(output_dir)
    if requested_output.exists() or requested_output.is_symlink():
        raise FileExistsError("Use a fresh selection output directory; no overwrite is permitted.")
    destination = requested_output.resolve()
    bundle = validate_bundle(review_bundle)
    root = Path(modern_data_dir).resolve(strict=True)
    if destination.is_relative_to(Path(bundle["binding"]["directory"])) or destination.is_relative_to(root):
        raise ValueError("Selection output must be outside the source bundle and Modern data directory.")
    proposal = bundle["proposal"]
    candidate = None
    if cluster_id is not None:
        matches = [r for r in proposal["anchor_reports"] if r["anchor"]["cluster_id"] == cluster_id]
        if (len(matches) != 1 or proposal["status"] != "candidates_proposed" or
                matches[0]["status"] != "candidate" or matches[0]["candidate_window"] is None):
            raise ValueError("Cluster ID must identify an actual eligible saved candidate.")
        candidate = matches[0]
        start_utc, end_utc = (candidate["candidate_window"][key] for key in ("start_utc", "end_utc"))
        justification = justification or (f"Explicit selection of saved cluster {cluster_id}: "
            f"{candidate['reason']}. Policy: {proposal['scientific_rule']} {proposal['data_quality_rule']}")
    window = _window(start_utc, end_utc)
    if candidate is None:
        coverage = bundle["analysis_coverage"]
        analysis = select_explicit_window(coverage["start_utc"], coverage["end_utc"])
        if window.start_time < analysis.start_time or window.end_time > analysis.end_time:
            raise ValueError("Independent target window must fall within saved MVP-01 temporal analysis coverage.")
    bounds = _bounds(window)
    inventory = _inventory(root, window, bundle["record"]["inputs"]["modern_daily_files"])
    _unchanged(bundle["binding"])
    record = dict(record_type="afghanistan_mvp_window_selection", schema_version=1,
        case_id=bundle["record"]["case_id"], event=bundle["record"]["confirmed_event"],
        selection_mode="candidate" if candidate is not None else "independent", cluster_id=cluster_id,
        window=bounds, scientific_rationale=justification, parent_review_bundle=bundle["binding"],
        selected_candidate=candidate, historical_reference_comparison=dict(
            reference=bundle["record"]["historical_research_reference"],
            matches_selected_window=bounds == mvp01.REFERENCE_WINDOW,
            duration_difference_hours=bounds["inclusive_hours"] - 120),
        candidate_comparisons=[dict(cluster_id=r["anchor"]["cluster_id"], status=r["status"],
            candidate_window=r["candidate_window"], matches_selected_window=(None if r["candidate_window"] is None
                else all(r["candidate_window"][key] == bounds[key] for key in bounds)))
            for r in proposal["anchor_reports"]], modern_gim_inputs=inventory,
        review_only=True, execution_eligible=False, framework_d_execution="not_performed",
        windows_local_isolation="NOT VERIFIED", trusted_human_authorization="NOT VERIFIED")
    text = _json(record)
    destination.mkdir(parents=True, exist_ok=False)
    output = destination / "selection_record.json"
    with output.open("xb") as handle:
        handle.write(text.encode("utf-8"))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-bundle", type=Path, required=True)
    parser.add_argument("--modern-data-dir", type=Path, required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--cluster-id", type=int)
    choice.add_argument("--start-utc")
    choice.add_argument("--inspect", action="store_true")
    parser.add_argument("--end-utc")
    parser.add_argument("--justification")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.inspect and any(v is not None for v in (args.end_utc, args.justification, args.output_dir)):
        parser.error("--inspect cannot include selection or output arguments.")
    if not args.inspect and args.output_dir is None:
        parser.error("Selection requires --output-dir.")
    try:
        if args.inspect:
            print(_json(inspect_handoff(args.review_bundle, args.modern_data_dir)), end="")
        else:
            output = select_window(args.review_bundle, args.modern_data_dir, args.output_dir,
                cluster_id=args.cluster_id, start_utc=args.start_utc, end_utc=args.end_utc,
                justification=args.justification)
            print(f"Saved review-only selection: {output}")
            print("Windows Local Isolation: NOT VERIFIED\nTrusted Human Authorization: NOT VERIFIED\nExecution Eligibility: FALSE")
    except FileExistsError as exc:
        parser.exit(3, f"Output conflict: {exc}\n")
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"Handoff failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
