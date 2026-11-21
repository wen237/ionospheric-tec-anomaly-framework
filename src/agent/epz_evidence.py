"""Validate/project a pinned, saved Afghanistan EPZ V1 report; never generate one.

The case-specific reference and mask below are from the accepted V1 validation
record. Geometry is not recalculated. Distances remain researcher-reviewed saved
values, bound by the independently supplied artifact pin. Generator code hashes
are historical declarations, never paths to open or current-reader requirements.
"""

import hashlib
import math
import re

import numpy as np

from examples.select_afghanistan_mvp_window import _same


REFERENCE = dict(
    relation="R_km = 10 ** (0.43 * M)", doi="10.1007/BF00876083", magnitude=6.0,
    epz_radius_km=380.1893963205613, earth_radius_km=6371.0088,
    distance_method="wrapped spherical haversine",
    membership_rule="grid_center_distance_km <= epz_radius_km", radius_tolerance_km=0.0,
    interpretation="literature-motivated retrospective spatial reference; no validated TEC influence boundary",
    historical_spatial_decision_rule="visual overlap of anomaly grid cells with the plotted EPZ circle",
    diagnostic_spatial_decision_rule="great-circle grid-center membership",
    historical_visual_overlap_reproduced=False, grid_cell_intersection_computed=False,
    physical_areal_coverage_computed=False)
MASK_SHA256 = "7644ce22be563963c99ed349737aa4a7ac582a5d4d2495f0fa49512ba89063c3"
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
SEMANTICS = dict(count_sum_unit="grid-hour occurrences",
    regional_mean="unweighted mean of included grid-center occurrence percentages",
    interpretation="descriptive summaries only",
    excluded_interpretations=["unique anomaly hours", "EPZ areal coverage",
                             "spatial statistical significance", "earthquake association probability"])
FIELDS = ("positive_counts", "negative_counts", "positive_ratio", "negative_ratio",
          "target_input_finite_counts", "initial_reference_input_finite_counts")
CODE_IDENTITIES = (
    "examples/diagnose_afghanistan_epicentral_zone.py", "src/agent/scientific_evidence_tools.py",
    "examples/compare_afghanistan_mvp_spatial.py", "examples/select_afghanistan_mvp_window.py",
    "examples/review_afghanistan_mvp.py", "src/spatial_verification/spatial_grid.py",
    "src/workflow/spatial_summary_export.py")


def host_binding(mode, identity, sha256, size_bytes, maximum_bytes):
    """Validate host declarations without probing any filesystem path."""
    if all(v is None for v in (identity, sha256, size_bytes)):
        return None
    if mode != "post_spatial":
        raise ValueError("EPZ binding requires Post-Spatial mode")
    if (type(identity) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", identity)
            or not identity.endswith(".json") or any(p in (".", "..") or p.endswith(".")
                or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", p.split(".")[0]) for p in identity.split("/"))
            or type(sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", sha256)
            or type(size_bytes) is not int or not 0 < size_bytes <= maximum_bytes):
        raise ValueError("EPZ binding requires a relative JSON identity and independent SHA-256/size pins")
    return dict(artifact=identity, sha256=sha256, size_bytes=size_bytes)


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError("Unsupported EPZ fields")


def _point(point, arrays, radius, extra=""):
    _fields(point, "row_index column_index latitude longitude distance_km signed_boundary_margin_km " + extra)
    i, j = point["row_index"], point["column_index"]
    if type(i) is not int or type(j) is not int or not (0 <= i < 71 and 0 <= j < 73):
        raise ValueError("Invalid EPZ grid index")
    _same([point["latitude"], point["longitude"]],
          [float(arrays["latitudes"][i]), float(arrays["longitudes"][j])], "EPZ coordinates")
    distance = point["distance_km"]
    if type(distance) not in (float, int) or not math.isfinite(distance) or not 0 <= distance <= math.pi * REFERENCE["earth_radius_km"]:
        raise ValueError("Invalid saved EPZ distance")
    _same(point["signed_boundary_margin_km"], float(distance - radius), "EPZ boundary margin")
    return i, j


def validate_report(d, evidence):
    """Bounded consistency arithmetic on saved arrays/indices, no EPZ algorithm.

    Requires an already validated spatial snapshot. The caller verifies the
    external diagnostic pin before decoding, and rechecks snapshots afterward.
    Returns a compact projection; no recommendation or authorization is added.
    """
    _fields(d, "record_type schema_version case_id event scientific_reference grid mask summary_semantics "
               "experiments comparison limitations provenance review_state")
    _same([d["record_type"], d["schema_version"], d["case_id"]],
          ["afghanistan_epicentral_zone_diagnostic", 1, evidence.bundle["record"]["case_id"]], "EPZ type/case")
    _same(d["event"], evidence.bundle["record"]["confirmed_event"], "EPZ event")
    _same(d["scientific_reference"], REFERENCE, "accepted EPZ V1 reference")
    _same(d["limitations"], list(LIMITATIONS), "EPZ limitations")
    _same(d["summary_semantics"], SEMANTICS, "EPZ summary units")
    a = evidence.arrays["A"]
    _same(d["grid"], dict(shape=[71, 73], orientation="canonical", coordinates="grid centers",
        latitudes=a["latitudes"].tolist(), longitudes=a["longitudes"].tolist(),
        latitude_spacing_degrees=2.5, longitude_spacing_degrees=5.0,
        endpoint_meridian="-180 and +180 duplicate one physical meridian; neither is included"), "EPZ grid")
    provenance = d["provenance"]
    _fields(provenance, "validated_source_artifacts current_direct_code_artifacts environment "
                        "original_input_files_opened source_integrity code_scope")
    _same(provenance["validated_source_artifacts"], evidence.sources, "EPZ spatial source snapshots")
    _same(provenance["original_input_files_opened"], False, "EPZ source scope")
    code = provenance["current_direct_code_artifacts"]
    if type(code) is not dict or set(code) != set(CODE_IDENTITIES):
        raise ValueError("Incomplete historical generator provenance")
    for pin in code.values():
        _fields(pin, "sha256 size_bytes")
        if (type(pin["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])
                or type(pin["size_bytes"]) is not int or pin["size_bytes"] < 0):
            raise ValueError("Invalid historical generator pin")
    _fields(provenance["environment"], "python numpy")
    for value in [*provenance["environment"].values(), provenance["source_integrity"], provenance["code_scope"]]:
        if type(value) is not str or not value.strip():
            raise ValueError("Incomplete EPZ provenance")
    _same(d["review_state"], dict(stop_point="Scientific & Security Review", researcher_review="pending",
        agent_integration="not_authorized", windows_local_isolation="NOT VERIFIED",
        trusted_human_authorization="NOT VERIFIED", execution_eligible=False,
        framework_execution="not_performed", llm_execution="not_performed"), "historical EPZ state")

    m, radius = d["mask"], REFERENCE["epz_radius_km"]
    _fields(m, "included_center_count status centers sha256 hash_encoding boundary_margin_sign "
               "closest_included_center_to_boundary closest_excluded_center_to_boundary")
    _same([m["included_center_count"], m["status"], m["sha256"], m["hash_encoding"], m["boundary_margin_sign"]],
          [3, "nonempty", MASK_SHA256, "uint8 0/1, shape (71,73), C row-major order, 5183 bytes",
           "distance minus radius; negative inside"], "reviewed EPZ mask")
    if type(m["centers"]) is not list or len(m["centers"]) != 3:
        raise ValueError("Invalid EPZ centers")
    indices = [_point(p, a, radius) for p in m["centers"]]
    if indices != sorted(set(indices)) or any(p["distance_km"] > radius for p in m["centers"]):
        raise ValueError("Inconsistent EPZ membership")
    mask = np.zeros((71, 73), dtype="uint8")
    for i, j in indices:
        mask[i, j] = 1
    _same(hashlib.sha256(mask.tobytes(order="C")).hexdigest(), MASK_SHA256, "saved EPZ mask indices")
    inside = mask.astype(bool)
    _same(m["closest_included_center_to_boundary"], max(m["centers"], key=lambda p: p["distance_km"]), "EPZ inside boundary")
    outside = m["closest_excluded_center_to_boundary"]
    i, j = _point(outside, a, radius)
    if inside[i, j] or outside["distance_km"] <= radius:
        raise ValueError("Invalid excluded EPZ center")

    _fields(d["experiments"], "A B")
    for label, hours in (("A", 120), ("B", 144)):
        s, arrays, selection = evidence.summaries[label], evidence.arrays[label], evidence.selections[label]
        v = d["experiments"][label]
        _fields(v, "experiment window selection_mode cluster_id selection_artifact parameters window_steps "
                   "ratio_denominator nominal_grid_hour_denominator included_centers polarities input_availability effective_detector_valid_counts")
        expected = dict(experiment=s["experiment"], window=s["window"], selection_mode=selection["selection_mode"],
            cluster_id=selection["cluster_id"], selection_artifact=f"afghanistan_mvp02b_selections/{s['experiment']}/selection_record.json",
            parameters=s["parameters"], window_steps=hours, ratio_denominator=hours,
            nominal_grid_hour_denominator=3 * hours, effective_detector_valid_counts=None)
        _same(int(arrays["ratio_denominator"]), hours, "EPZ A/B denominator")
        for key, value in expected.items():
            _same(v[key], value, "EPZ experiment " + key)
        _same(v["included_centers"], [dict(row_index=i, column_index=j,
            **{f: arrays[f][i, j].item() for f in FIELDS}) for i, j in indices], "EPZ per-center observations")
        _fields(v["input_availability"], "target_input_finite_counts initial_reference_input_finite_counts")
        for f in FIELDS[-2:]:
            values = arrays[f]
            _same(v["input_availability"][f], dict(global_minimum=int(values.min()), global_maximum=int(values.max()),
                included_minimum=int(values[inside].min()), included_maximum=int(values[inside].max())), "EPZ availability")
        _fields(v["polarities"], "positive negative")
        for polarity in ("positive", "negative"):
            p = v["polarities"][polarity]
            _fields(p, "global_maximum_ratio_percent global_peak_centers regional")
            peak = s["spatial_anomalies"][polarity]
            maximum = peak["maximum_ratio_percent"]
            _same(p["global_maximum_ratio_percent"], maximum, "EPZ global maximum")
            points = p["global_peak_centers"]
            expected_points = peak["maximum_grid_points"] if maximum > 0 else []
            if type(points) is not list or len(points) != len(expected_points):
                raise ValueError("EPZ global peak mismatch")
            for point, coords in zip(points, expected_points):
                i, j = _point(point, arrays, radius, "count ratio_percent grid_center_inside_epz")
                _same({k: point[k] for k in coords}, coords, "EPZ global peak coordinates")
                _same([point["count"], point["ratio_percent"], point["grid_center_inside_epz"]],
                      [int(arrays[polarity + "_counts"][i, j]), float(arrays[polarity + "_ratio"][i, j]), bool(inside[i, j])], "EPZ peak observations")
                if (point["distance_km"] <= radius) != bool(inside[i, j]):
                    raise ValueError("EPZ peak membership mismatch")
                if (i, j) in indices:
                    saved_point = m["centers"][indices.index((i, j))]
                    _same({k: point[k] for k in saved_point}, saved_point, "EPZ shared distances")
            counts, ratios = arrays[polarity + "_counts"][inside], arrays[polarity + "_ratio"][inside]
            _same(p["regional"], dict(grid_hour_occurrence_count_sum=int(counts.sum()),
                unweighted_mean_ratio_percent=float(ratios.mean()), count_minimum=int(counts.min()),
                count_maximum=int(counts.max()), ratio_minimum_percent=float(ratios.min()),
                ratio_maximum_percent=float(ratios.max())), "EPZ regional summary")

    c, diff = d["comparison"], evidence.differences
    _fields(c, "direction ratio_difference_unit mask_identity denominators included_centers polarities")
    _same([c["direction"], c["ratio_difference_unit"], c["mask_identity"], c["denominators"]],
          ["B minus A", "percentage_points", "shared mask for A and B", dict(A=120, B=144)], "EPZ comparison scope")
    _same(c["included_centers"], [dict(row_index=i, column_index=j,
        **{f + "_b_minus_a": diff[f + "_b_minus_a"][i, j].item() for f in FIELDS})
        for i, j in indices], "EPZ signed per-center differences")
    _fields(c["polarities"], "positive negative")
    for polarity in ("positive", "negative"):
        _same(c["polarities"][polarity], dict(
            grid_hour_occurrence_count_sum_b_minus_a=int(diff[polarity + "_counts_b_minus_a"][inside].sum()),
            mean_cell_ratio_difference_percentage_points=float(diff[polarity + "_ratio_b_minus_a"][inside].mean())), "EPZ regional differences")

    return dict(event=d["event"], epz_definition=d["scientific_reference"],
        grid={k: d["grid"][k] for k in ("shape", "orientation", "coordinates", "latitude_spacing_degrees", "longitude_spacing_degrees")},
        shared_mask=d["mask"], summary_semantics=d["summary_semantics"],
        experiments=d["experiments"], comparison=c, limitations=d["limitations"],
        missing_physical_evidence=["Kp", "Dst", "F10.7"])
