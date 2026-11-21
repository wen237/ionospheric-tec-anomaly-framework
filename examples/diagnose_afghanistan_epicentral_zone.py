"""Offline, case-specific grid-center EPZ diagnostic of saved A/B evidence.

Run with --evidence-root outputs --output outputs/NEW_DIR/diagnostic.json.
No detector, model, network, plotting or Stage 2 execution is performed.
Center membership differs from the paper's visual grid-cell/circle overlap.
Counts and unweighted percentages are descriptive, not association decisions.
"""

import argparse
import hashlib
import math
from numbers import Real
from pathlib import Path
import platform

import numpy as np

from examples import compare_afghanistan_mvp_spatial as saved_spatial
from examples import select_afghanistan_mvp_window as handoff
from examples.review_afghanistan_mvp import EVENT
from src.agent.scientific_evidence_tools import (
    EvidenceTools, EXPERIMENTS, POST_ROOT, PRE_ROOT, SELECTION_ROOT,
)
from src.spatial_verification.spatial_grid import GIM_LATITUDES, GIM_LONGITUDES
from src.workflow.spatial_summary_export import _maximum_anomaly


EARTH_RADIUS_KM = 6371.0088
RECORD_TYPE = "afghanistan_epicentral_zone_diagnostic"
SCHEMA_VERSION = 1
_ROOT = Path(__file__).resolve().parents[1]
_CODE_FILES = (
    "examples/diagnose_afghanistan_epicentral_zone.py",
    "src/agent/scientific_evidence_tools.py",
    "examples/compare_afghanistan_mvp_spatial.py",
    "examples/select_afghanistan_mvp_window.py",
    "examples/review_afghanistan_mvp.py",
    "src/spatial_verification/spatial_grid.py",
    "src/workflow/spatial_summary_export.py",
)
LIMITATIONS = (
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
    "Snapshot hashes do not authenticate origin, OS isolation or trusted human authorization.",
)


def _finite_scalar(value, name, *, lower, upper=math.inf):
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not math.isfinite(value) or not lower <= value <= upper):
        raise ValueError(f"Invalid {name}.")
    return float(value)


def preparation_radius_km(magnitude):
    """Evaluate the established 10**(0.43*M) reference, without peak fitting."""
    magnitude = _finite_scalar(magnitude, "magnitude", lower=0)
    if magnitude == 0:
        raise ValueError("Magnitude must be positive.")
    try:
        radius = 10.0 ** (0.43 * magnitude)
    except OverflowError as exc:
        raise ValueError("Nonfinite preparation radius.") from exc
    if not math.isfinite(radius):
        raise ValueError("Nonfinite preparation radius.")
    return radius


def great_circle_distances_km(epicenter_latitude, epicenter_longitude, latitudes, longitudes):
    """Wrapped spherical haversine distances; coordinate inputs broadcast."""
    latitude = _finite_scalar(epicenter_latitude, "epicenter latitude", lower=-90, upper=90)
    longitude = _finite_scalar(epicenter_longitude, "epicenter longitude", lower=-180, upper=180)
    latitudes, longitudes = np.broadcast_arrays(
        np.asarray(latitudes, dtype=float), np.asarray(longitudes, dtype=float))
    if (not np.isfinite(latitudes).all() or not np.isfinite(longitudes).all()
            or np.any(np.abs(latitudes) > 90) or np.any(np.abs(longitudes) > 180)):
        raise ValueError("Invalid grid coordinates.")
    p0, p = np.deg2rad(latitude), np.deg2rad(latitudes)
    dl = np.deg2rad((longitudes - longitude + 180.0) % 360.0 - 180.0)
    h = np.clip(np.sin((p - p0) / 2)**2 + np.cos(p0) * np.cos(p) * np.sin(dl / 2)**2, 0, 1)
    return 2 * EARTH_RADIUS_KM * np.arctan2(np.sqrt(h), np.sqrt(1 - h))


def center_membership(distances_km, radius_km):
    """Inclusive grid-center boundary, with no tolerance or radius inflation."""
    radius = _finite_scalar(radius_km, "radius", lower=0)
    distances = np.asarray(distances_km, dtype=float)
    if not np.isfinite(distances).all() or np.any(distances < 0):
        raise ValueError("Distances must be finite and nonnegative.")
    return distances <= radius


def _point(row, column, a, distances, radius):
    return dict(row_index=int(row), column_index=int(column),
                latitude=float(a["latitudes"][row]), longitude=float(a["longitudes"][column]),
                distance_km=float(distances[row, column]),
                signed_boundary_margin_km=float(distances[row, column] - radius))


def regional_summary(counts, ratios, mask):
    """Unweighted center summaries; count units are grid-hour occurrences."""
    c = np.asarray(counts)[mask]
    p = np.asarray(ratios)[mask]
    return dict(grid_hour_occurrence_count_sum=int(c.sum()),
                unweighted_mean_ratio_percent=float(p.mean()) if p.size else None,
                count_minimum=int(c.min()) if c.size else None,
                count_maximum=int(c.max()) if c.size else None,
                ratio_minimum_percent=float(p.min()) if p.size else None,
                ratio_maximum_percent=float(p.max()) if p.size else None)


def _code_records():
    return {name: handoff._metadata((_ROOT / name).read_bytes()) for name in _CODE_FILES}


def _build_report(evidence):
    """Consume only snapshots already checked by the existing offline loader."""
    if evidence.status != dict(temporal_historical="validated_snapshot", spatial="validated_snapshot"):
        raise ValueError("Validated Post-Spatial evidence is required; no reconstruction is permitted.")
    evidence.recheck()
    code = _code_records()
    a, b = evidence.arrays["A"], evidence.arrays["B"]
    event = evidence.summaries["A"]["event"]
    for actual in (event, evidence.summaries["B"]["event"],
                   evidence.bundle["record"]["confirmed_event"]):
        handoff._same(actual, EVENT, "confirmed Afghanistan event")
    for label, arrays in (("A", a), ("B", b)):
        if (not np.array_equal(arrays["latitudes"], GIM_LATITUDES)
                or not np.array_equal(arrays["longitudes"], GIM_LONGITUDES)
                or evidence.summaries[label]["parameters"]["grid_orientation"] != "canonical"):
            raise ValueError("Both experiments require the same canonical Modern grid.")
    radius = preparation_radius_km(event["magnitude"])
    lat, lon = np.meshgrid(a["latitudes"], a["longitudes"], indexing="ij")
    distances = great_circle_distances_km(event["latitude"], event["longitude"], lat, lon)
    mask = center_membership(distances, radius)
    if mask[:, 0].any() or mask[:, -1].any():
        raise ValueError("Dateline aggregation is outside this case-specific diagnostic.")
    indices = np.argwhere(mask)
    points = [_point(i, j, a, distances, radius) for i, j in indices]
    closest = {}
    for name, selected in (("closest_included_center_to_boundary", mask),
                           ("closest_excluded_center_to_boundary", ~mask)):
        candidates = np.argwhere(selected)
        if candidates.size:
            k = int(np.argmin(np.abs(distances[selected] - radius)))
            closest[name] = _point(*candidates[k], a, distances, radius)
        else:
            closest[name] = None
    fields = ("positive_counts", "negative_counts", "positive_ratio", "negative_ratio",
              "target_input_finite_counts", "initial_reference_input_finite_counts")
    experiments = {}
    for label, arrays in (("A", a), ("B", b)):
        summary, selection = evidence.summaries[label], evidence.selections[label]
        polarities = {}
        for polarity in ("positive", "negative"):
            peaks = _maximum_anomaly(arrays[polarity + "_ratio"], arrays["latitudes"],
                                     arrays["longitudes"], grid_orientation="canonical")
            peak_points = []
            for p in peaks["maximum_grid_points"]:
                i = int(np.flatnonzero(arrays["latitudes"] == p["latitude"])[0])
                j = int(np.flatnonzero(arrays["longitudes"] == p["longitude"])[0])
                peak_points.append(dict(**_point(i, j, a, distances, radius),
                    count=int(arrays[polarity + "_counts"][i, j]),
                    ratio_percent=float(arrays[polarity + "_ratio"][i, j]),
                    grid_center_inside_epz=bool(mask[i, j])))
            polarities[polarity] = dict(global_maximum_ratio_percent=peaks["maximum_ratio_percent"],
                global_peak_centers=peak_points,
                regional=regional_summary(arrays[polarity + "_counts"], arrays[polarity + "_ratio"], mask))
        availability = {}
        for field in fields[-2:]:
            values = arrays[field]
            availability[field] = dict(global_minimum=int(values.min()), global_maximum=int(values.max()),
                included_minimum=int(values[mask].min()) if indices.size else None,
                included_maximum=int(values[mask].max()) if indices.size else None)
        experiments[label] = dict(experiment=EXPERIMENTS[label], window=dict(summary["window"]),
            selection_mode=selection["selection_mode"], cluster_id=selection["cluster_id"],
            selection_artifact=f"{SELECTION_ROOT}/{EXPERIMENTS[label]}/selection_record.json",
            parameters=dict(summary["parameters"]), window_steps=int(arrays["window_steps"]),
            ratio_denominator=int(arrays["ratio_denominator"]),
            nominal_grid_hour_denominator=int(mask.sum()) * int(arrays["ratio_denominator"]),
            included_centers=[dict(row_index=int(i), column_index=int(j),
                **{field: arrays[field][i, j].item() for field in fields}) for i, j in indices],
            polarities=polarities, input_availability=availability, effective_detector_valid_counts=None)
    # Reuse the validated signed differences; do not renormalize percentages.
    differences = evidence.differences
    comparison = dict(direction="B minus A", ratio_difference_unit="percentage_points",
        mask_identity="shared mask for A and B", denominators={"A": int(a["ratio_denominator"]),
        "B": int(b["ratio_denominator"])}, included_centers=[dict(row_index=int(i), column_index=int(j),
            **{field + "_b_minus_a": differences[field + "_b_minus_a"][i, j].item()
               for field in fields}) for i, j in indices], polarities={})
    for polarity in ("positive", "negative"):
        dc = differences[polarity + "_counts_b_minus_a"][mask]
        dp = differences[polarity + "_ratio_b_minus_a"][mask]
        comparison["polarities"][polarity] = dict(grid_hour_occurrence_count_sum_b_minus_a=int(dc.sum()),
            mean_cell_ratio_difference_percentage_points=float(dp.mean()) if dp.size else None)
    report = dict(record_type=RECORD_TYPE, schema_version=SCHEMA_VERSION, case_id="afghanistan_2022",
        event=dict(event), scientific_reference=dict(relation="R_km = 10 ** (0.43 * M)",
            doi="10.1007/BF00876083", magnitude=event["magnitude"], epz_radius_km=radius,
            earth_radius_km=EARTH_RADIUS_KM, distance_method="wrapped spherical haversine",
            membership_rule="grid_center_distance_km <= epz_radius_km", radius_tolerance_km=0.0,
            interpretation="literature-motivated retrospective spatial reference; no validated TEC influence boundary",
            historical_spatial_decision_rule="visual overlap of anomaly grid cells with the plotted EPZ circle",
            diagnostic_spatial_decision_rule="great-circle grid-center membership",
            historical_visual_overlap_reproduced=False, grid_cell_intersection_computed=False,
            physical_areal_coverage_computed=False),
        grid=dict(shape=[71, 73], orientation="canonical", coordinates="grid centers",
            latitudes=a["latitudes"].tolist(), longitudes=a["longitudes"].tolist(),
            latitude_spacing_degrees=2.5, longitude_spacing_degrees=5.0,
            endpoint_meridian="-180 and +180 duplicate one physical meridian; neither is included"),
        mask=dict(included_center_count=int(mask.sum()), status="nonempty" if indices.size else "empty",
            centers=points, sha256=hashlib.sha256(mask.astype("uint8").tobytes(order="C")).hexdigest(),
            hash_encoding="uint8 0/1, shape (71,73), C row-major order, 5183 bytes",
            boundary_margin_sign="distance minus radius; negative inside", **closest),
        summary_semantics=dict(count_sum_unit="grid-hour occurrences",
            regional_mean="unweighted mean of included grid-center occurrence percentages",
            interpretation="descriptive summaries only",
            excluded_interpretations=["unique anomaly hours", "EPZ areal coverage",
                                     "spatial statistical significance", "earthquake association probability"]),
        experiments=experiments, comparison=comparison, limitations=list(LIMITATIONS),
        provenance=dict(validated_source_artifacts={k: dict(v) for k, v in evidence.sources.items()},
            current_direct_code_artifacts=code,
            environment=dict(python=platform.python_version(), numpy=np.__version__),
            original_input_files_opened=False,
            source_integrity="saved snapshot hashes rechecked before and after calculation; source declarations bound, raw sources not rehashed",
            code_scope="current diagnostic and direct reused code; saved historical code declarations remain in bound source records"),
        review_state=dict(stop_point="Scientific & Security Review", researcher_review="pending",
            agent_integration="not_authorized", windows_local_isolation="NOT VERIFIED",
            trusted_human_authorization="NOT VERIFIED", execution_eligible=False,
            framework_execution="not_performed", llm_execution="not_performed"))
    evidence.recheck()
    if _code_records() != code:
        raise ValueError("Diagnostic code changed during calculation.")
    return report


def serialize_report(report):
    """Sorted UTF-8 JSON with a fixed newline and no nonfinite JSON numbers."""
    return handoff._json(report).encode("utf-8")


def diagnose(evidence_root, output_path):
    """Write one fresh JSON outside the fixed source evidence directories."""
    root = Path(evidence_root).resolve(strict=True)
    output = Path(output_path)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Diagnostic output already exists; no overwrite is permitted.")
    if output.suffix.lower() != ".json":
        raise ValueError("Diagnostic output must be a JSON file.")
    destination = output.resolve()
    if any(destination.is_relative_to((root / name).resolve())
           for name in (PRE_ROOT, POST_ROOT, SELECTION_ROOT)):
        raise ValueError("Diagnostic output must be outside source evidence directories.")
    evidence = EvidenceTools(root, "post_spatial")
    report = _build_report(evidence)
    raw = serialize_report(report)
    evidence.recheck()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as handle:
        handle.write(raw)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = diagnose(args.evidence_root, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Diagnostic failed ({type(exc).__name__}); no framework execution attempted.\n")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
