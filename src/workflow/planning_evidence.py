"""Versioned scientific evidence, without window selection or execution.

Public builders return detached, strict-JSON dictionaries. Schema V1 has two
independent evidence types: ``case_temporal_anomalies`` and
``historical_bc_context``. UTC timestamps name inclusive hourly samples.

Temporal callers must declare ``naive_utc`` or ``aware_utc`` and supply the
expected analysis bounds; neither timezone nor missing edge hours is guessed.
``unclassifiable`` counts existing detector rows only; ``missing_timestamp``
counts absent rows. Their sum with positive/negative/valid_normal equals the
expected hours. All-NaN statistics are the detector's insufficient-reference
sentinel, not an inferred reference sample count. Physical observation quality
and upstream interpolation history remain unknown unless separately supplied.

Provenance accepts ``sources`` (null or a list of identity/sha256 records) and
``processing_history`` (null or a description). Caller-supplied hashes are
declarations, not file-integrity verification. The historical file loader
separately hashes the exact summary bytes it reads. No raw TEC is loaded here.
"""

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

from src.temporal_anomaly.tec_timeseries import TECTimeSeries
from src.temporal_anomaly.temporal_anomaly import TemporalAnomalyResult


EVIDENCE_SCHEMA_VERSION = 1
TEMPORAL_EVIDENCE_TYPE = "case_temporal_anomalies"
HISTORICAL_EVIDENCE_TYPE = "historical_bc_context"
_STATISTICS = ("q1", "median", "q3", "upper_bound", "lower_bound")
_VALUES = ("observed",) + _STATISTICS
_HOUR = timedelta(hours=1)


def _strict_copy(value):
    """Copy only JSON-native values, rejecting non-string keys and nonfinites."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is list:
        return [_strict_copy(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _strict_copy(item) for key, item in value.items()}
    raise ValueError("Evidence requires strict JSON values and string keys.")


def _integer(value, name, minimum=None, maximum=None):
    if isinstance(value, np.integer):
        value = int(value)
    if type(value) is not int or (minimum is not None and value < minimum) or (
        maximum is not None and value > maximum
    ):
        raise ValueError(f"Invalid integer: {name}.")
    return value


def _number(value, name, minimum=None, maximum=None):
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if type(value) not in (int, float) or not math.isfinite(value) or (
        minimum is not None and value < minimum
    ) or (maximum is not None and value > maximum):
        raise ValueError(f"Invalid finite number: {name}.")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string.")
    return value


def _fields(value, names, name):
    if type(value) is not dict or not set(names).issubset(value):
        raise ValueError(f"Missing or malformed {name} fields.")
    return value


def _provenance(value):
    data = {"sources": None, "processing_history": None}
    if value is not None:
        value = _strict_copy(value)
        if type(value) is not dict or set(value) - set(data):
            raise ValueError("Unsupported provenance fields.")
        data.update(value)
    if data["processing_history"] is not None:
        _text(data["processing_history"], "processing_history")
    if data["sources"] is not None:
        if type(data["sources"]) is not list or not data["sources"]:
            raise ValueError("sources must be a nonempty list or null.")
        for source in data["sources"]:
            _fields(source, ("identity", "sha256"), "source")
            if set(source) != {"identity", "sha256"}:
                raise ValueError("Unsupported source fields.")
            _text(source["identity"], "source identity")
            digest = source["sha256"]
            if digest is not None and (
                not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
            ):
                raise ValueError("source sha256 must be 64 hexadecimal digits or null.")
    return {**data, "source_hash_verification": "not_performed"}


def _utc_hour(value, convention):
    if not isinstance(value, datetime):
        raise ValueError("Timestamps must be datetime objects.")
    if convention == "naive_utc":
        if value.tzinfo is not None:
            raise ValueError("Declared naive_utc requires naive timestamps.")
        value = value.replace(tzinfo=timezone.utc)
    elif value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Declared aware_utc requires explicit UTC timestamps.")
    if value.minute or value.second or value.microsecond or value.fold:
        raise ValueError("Timestamps must be unambiguous UTC hourly samples.")
    return value.astimezone(timezone.utc)


def _epochs(values, convention):
    array = np.asarray(values, dtype=object)
    if array.ndim != 1:
        raise ValueError("epochs must be one-dimensional.")
    times = [_utc_hour(value, convention) for value in array]
    if any(left >= right for left, right in zip(times, times[1:])):
        raise ValueError("epochs must be ordered, unique UTC hours.")
    return times


def _vector(values, length, name):
    array = np.asarray(values)
    if array.ndim != 1 or len(array) != length or array.dtype.kind not in "fiu":
        raise ValueError(f"{name} must be a matching one-dimensional real numeric array.")
    return array


def _location(series, times, observed, convention):
    if series is None:
        return None
    if not isinstance(series, TECTimeSeries):
        raise TypeError("time_series must be a TECTimeSeries or None.")
    source_times = _epochs(series.epochs, convention)
    source_values = _vector(series.tec, len(source_times), "time_series.tec")
    lookup = dict(zip(source_times, source_values))
    for epoch, value in zip(times, observed):
        if epoch not in lookup or not (
            lookup[epoch] == value or (np.isnan(lookup[epoch]) and np.isnan(value))
        ):
            raise ValueError("time_series does not match the temporal observations.")
    location = {}
    for name in ("requested_latitude", "requested_longitude", "grid_latitude", "grid_longitude"):
        raw = getattr(series, name)
        if isinstance(raw, (bool, np.bool_)) or not isinstance(raw, (int, float, np.number)):
            raise ValueError(f"Invalid coordinate: {name}.")
        value = _number(float(raw), name)
        if "latitude" in name and not -90 <= value <= 90:
            raise ValueError(f"Invalid latitude: {name}.")
        location[name] = value
    for name in ("latitude_index", "longitude_index"):
        raw = getattr(series, name)
        if isinstance(raw, np.integer):
            raw = int(raw)
        location[name] = _integer(raw, name, 0)
    return location


def build_temporal_evidence(
    result: TemporalAnomalyResult,
    *,
    case_id: str,
    expected_start: datetime,
    expected_end: datetime,
    input_time_convention: str,
    provenance: dict | None = None,
    time_series: TECTimeSeries | None = None,
) -> dict:
    """Adapt A without recalculating quartiles, thresholds or classifications.

    Bounds use the same explicitly declared convention as result.epochs.
    Missing hours receive null values/code; input nonfinite values receive
    null plus a per-field nan/positive_infinity/negative_infinity marker.
    Anomaly codes must have an integer NumPy dtype; float/bool codes are
    rejected without conversion. Inconsistent statistics/codes raise ValueError.
    """
    if not isinstance(result, TemporalAnomalyResult):
        raise TypeError("result must be a TemporalAnomalyResult.")
    _text(case_id, "case_id")
    if input_time_convention not in ("naive_utc", "aware_utc"):
        raise ValueError("Declare input_time_convention as naive_utc or aware_utc.")
    start = _utc_hour(expected_start, input_time_convention)
    end = _utc_hour(expected_end, input_time_convention)
    if start > end:
        raise ValueError("expected_start must not exceed expected_end.")
    times = _epochs(result.epochs, input_time_convention)
    if times and (times[0] < start or times[-1] > end):
        raise ValueError("Result timestamps lie outside the expected analysis bounds.")
    arrays = {name: _vector(getattr(result, name), len(times), name) for name in _VALUES}
    codes = _vector(result.anomaly, len(times), "anomaly")
    if codes.dtype.kind not in "iu":
        raise ValueError("anomaly must have an integer NumPy dtype.")
    if not np.all(np.isin(codes, (-1, 0, 1))):
        raise ValueError("anomaly must contain only -1, 0, +1.")
    reference_days = _integer(result.reference_days, "reference_days", 1)
    min_reference_samples = _integer(result.min_reference_samples, "min_reference_samples", 1, reference_days)
    multiplier = _number(result.threshold_multiplier, "threshold_multiplier", 0)
    location = _location(time_series, times, arrays["observed"], input_time_convention)
    provenance_data = _provenance(provenance)
    rows = {}
    counts = dict(positive=0, negative=0, valid_normal=0, unclassifiable=0, missing_timestamp=0)
    for index, epoch in enumerate(times):
        values = {name: float(array[index]) for name, array in arrays.items()}
        code = int(codes[index])
        reasons = []
        if not math.isfinite(values["observed"]):
            reasons.append("nonfinite_observation")
        statistics = [values[name] for name in _STATISTICS]
        if all(math.isnan(value) for value in statistics):
            reasons.append("insufficient_reference")
        elif not all(math.isfinite(value) for value in statistics):
            reasons.append("nonfinite_statistics")
        elif not (values["q1"] <= values["median"] <= values["q3"] and
                  values["lower_bound"] <= values["median"] <= values["upper_bound"]):
            raise ValueError("Inconsistent quartile or bound ordering.")
        if reasons:
            if code != 0:
                raise ValueError("Nonzero anomaly with unclassifiable observations/statistics.")
            classification = "unclassifiable"
        else:
            above = values["observed"] > values["upper_bound"]
            below = values["observed"] < values["lower_bound"]
            if (code == 1) != above or (code == -1) != below:
                raise ValueError("Anomaly code contradicts supplied observed TEC/bounds.")
            classification = {1: "positive", -1: "negative", 0: "valid_normal"}[code]
        counts[classification] += 1
        nonfinite = {
            name: ("nan" if math.isnan(value) else
                   "positive_infinity" if value > 0 else "negative_infinity")
            for name, value in values.items() if not math.isfinite(value)
        }
        rows[epoch] = dict(
            result_present=True,
            **{name: value if math.isfinite(value) else None for name, value in values.items()},
            anomaly_code=code, classification=classification,
            unclassifiable_reasons=reasons, nonfinite_values=nonfinite,
        )
    expected_hours = int((end - start) / _HOUR) + 1
    hourly = []
    for offset in range(expected_hours):
        epoch = start + offset * _HOUR
        if epoch in rows:
            row = rows[epoch]
        else:
            counts["missing_timestamp"] += 1
            row = dict(result_present=False, **{name: None for name in _VALUES},
                       anomaly_code=None, classification="missing_timestamp",
                       unclassifiable_reasons=["missing_timestamp"], nonfinite_values={})
        hourly.append({"timestamp_utc": epoch.isoformat().replace("+00:00", "Z"), **row})
    return dict(
        evidence_type=TEMPORAL_EVIDENCE_TYPE, schema_version=EVIDENCE_SCHEMA_VERSION,
        case_id=case_id, input_time_convention=input_time_convention,
        analysis=dict(start_utc=hourly[0]["timestamp_utc"], end_utc=hourly[-1]["timestamp_utc"],
                      bounds="inclusive_hourly_samples", expected_hours=expected_hours,
                      result_hours=len(times), continuous=counts["missing_timestamp"] == 0),
        parameters=dict(reference_days=reference_days, threshold_multiplier=multiplier,
                        min_reference_samples=min_reference_samples),
        provenance=provenance_data, location=location, hourly=hourly, counts=counts,
        reference_sample_counts=None, observation_quality=None,
    )


def _significance_scope(scope, start, end, critical_z):
    fields = ("relative_day_start", "relative_day_end", "shape", "significant_cells", "overlap_cells",
              "positive_significant_count", "negative_significant_count", "positive_mask_count",
              "negative_mask_count", "zero_mask_count", "nonzero_mask_count", "overlap_count")
    _fields(scope, fields, "significance scope")
    if (_integer(scope["relative_day_start"], "relative_day_start") != start or
            _integer(scope["relative_day_end"], "relative_day_end") != end):
        raise ValueError("Inconsistent significance scope bounds/shape.")
    _integer_list(scope["shape"], [end - start + 1, 24], "significance shape")
    cells, overlaps = set(), set()
    for field in ("significant_cells", "overlap_cells"):
        if type(scope[field]) is not list:
            raise ValueError(f"{field} must be a list.")
        for cell in scope[field]:
            _fields(cell, ("relative_day", "hour_utc"), field)
            day = _integer(cell["relative_day"], "relative_day", start, end)
            hour = _integer(cell["hour_utc"], "hour_utc", 0, 23)
            if field == "significant_cells":
                _fields(cell, ("polarity",), field)
                polarity = _integer(cell["polarity"], "polarity", -1, 1)
                if polarity == 0 or any(c[:2] == (day, hour) for c in cells):
                    raise ValueError("Duplicate or zero-polarity significant cell.")
                cells.add((day, hour, polarity))
            else:
                _fields(cell, ("positive_z", "negative_z"), field)
                if (day, hour) in overlaps:
                    raise ValueError("Duplicate overlap cell.")
                for name in ("positive_z", "negative_z"):
                    if _number(cell[name], name) <= critical_z:
                        raise ValueError("Overlap z values must exceed the declared critical_z.")
                overlaps.add((day, hour))
    if {(day, hour) for day, hour, _ in cells} & overlaps:
        raise ValueError("Overlap cells must retain the legacy zero mask encoding.")
    positive = sum(polarity == 1 for _, _, polarity in cells)
    negative = len(cells) - positive
    expected = dict(positive_mask_count=positive, negative_mask_count=negative,
                    nonzero_mask_count=len(cells), overlap_count=len(overlaps),
                    zero_mask_count=(end - start + 1) * 24 - len(cells),
                    positive_significant_count=positive + len(overlaps),
                    negative_significant_count=negative + len(overlaps))
    for name, value in expected.items():
        if _integer(scope[name], name, 0) != value:
            raise ValueError(f"Inconsistent significance count: {name}.")
    return cells


def _matrix(value, rows, columns, name):
    if type(value) is not list or len(value) != rows:
        raise ValueError(f"Invalid matrix: {name}.")
    for row in value:
        if type(row) is not list or len(row) != columns:
            raise ValueError(f"Invalid matrix: {name}.")
        for item in row:
            _number(item, name)


def _integer_list(value, expected, name):
    if type(value) is not list or any(type(item) is not int for item in value) or value != expected:
        raise ValueError(f"Invalid integer axis/shape: {name}.")


def _validate_historical_summary(summary):
    names = ("summary_type", "schema_version", "inputs", "configuration", "environment",
             "historical_data", "population_baseline", "earthquake_selection", "earthquake_subset",
             "statistical_significance", "clustering", "reference_comparison", "legacy_comparison",
             "input_integrity_verified_after_run")
    _fields(summary, names, "historical summary")
    if (summary["summary_type"] != "afghanistan_historical_bc_reproduction" or
            type(summary["schema_version"]) is not int or summary["schema_version"] != 1):
        raise ValueError("Unsupported historical summary type/schema version.")
    for name in names[2:-2]:
        if type(summary[name]) is not dict:
            raise ValueError(f"{name} must be an object.")
    if type(summary["input_integrity_verified_after_run"]) is not bool:
        raise ValueError("Invalid input integrity diagnostic.")
    if summary["legacy_comparison"] is not None and type(summary["legacy_comparison"]) is not dict:
        raise ValueError("legacy_comparison must be an object or null.")
    inputs = summary["inputs"]
    _fields(inputs, ("tec", "usgs_catalog"), "inputs")
    for record in inputs.values():
        _fields(record, ("path", "size_bytes", "sha256"), "input record")
        _integer(record["size_bytes"], "size_bytes", 0)
        _provenance({"sources": [dict(identity=record["path"], sha256=record["sha256"])]})
        if record["sha256"] is None:
            raise ValueError("Historical input records require SHA-256.")
    config = _fields(summary["configuration"],
                     ("start_date", "end_date", "minimum_magnitude", "observation_days", "reference_days",
                      "threshold_multiplier", "critical_z", "clustering_days", "n_clusters", "random_state"),
                     "configuration")
    try:
        start_date = date.fromisoformat(config["start_date"])
        end_date = date.fromisoformat(config["end_date"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid historical dates.") from exc
    if start_date > end_date:
        raise ValueError("Reversed historical dates.")
    days = _integer(config["observation_days"], "observation_days", 1)
    _integer(config["reference_days"], "reference_days", 1)
    _integer(config["random_state"], "random_state", 0)
    k = _integer(config["n_clusters"], "n_clusters", 1)
    critical_z = _number(config["critical_z"], "critical_z", 0)
    _number(config["minimum_magnitude"], "minimum_magnitude")
    _number(config["threshold_multiplier"], "threshold_multiplier", 0)
    _integer_list(config["clustering_days"], [-days, 0], "clustering_days")
    historical = _fields(summary["historical_data"],
                         ("input_shape", "input_dtype", "daily_shape", "n_days", "n_hours",
                          "assigned_start_utc", "assigned_end_utc", "timeline_provenance", "finite_count",
                          "nan_count", "infinite_count", "minimum", "maximum", "observed_input_count",
                          "interpolated_count", "values_unchanged"), "historical_data")
    n_days = (end_date - start_date).days + 1
    n_hours = n_days * 24
    if (_integer(historical["n_days"], "n_days", 1) != n_days or
            _integer(historical["n_hours"], "n_hours", 1) != n_hours):
        raise ValueError("Historical coverage counts differ from configuration dates.")
    _integer_list(historical["daily_shape"], [n_days, 24], "daily_shape")
    shape = historical["input_shape"]
    if type(shape) is not list or any(type(item) is not int for item in shape) or (
        shape not in ([n_hours], [n_hours, 1], [n_days, 24])
    ):
        raise ValueError("Invalid historical input shape.")
    _text(historical["input_dtype"], "input_dtype")
    _text(historical["timeline_provenance"], "timeline_provenance")
    if (historical["assigned_start_utc"] != start_date.isoformat() + "T00:00:00Z" or
            historical["assigned_end_utc"] != end_date.isoformat() + "T23:00:00Z"):
        raise ValueError("Assigned Legacy UTC timeline differs from configuration dates.")
    finite_counts = [_integer(historical[name], name, 0, n_hours)
                     for name in ("finite_count", "nan_count", "infinite_count")]
    if sum(finite_counts) != n_hours:
        raise ValueError("Inconsistent historical finite/missing counts.")
    observed = _integer(historical["observed_input_count"], "observed_input_count", 0, n_hours)
    interpolated = _integer(historical["interpolated_count"], "interpolated_count", 0, n_hours)
    if observed + interpolated != n_hours or type(historical["values_unchanged"]) is not bool:
        raise ValueError("Inconsistent historical preparation diagnostics.")
    if _number(historical["minimum"], "minimum") > _number(historical["maximum"], "maximum"):
        raise ValueError("Reversed historical value range.")
    population = _fields(summary["population_baseline"],
                         ("positive_count", "negative_count", "valid_sample_count", "positive_probability",
                          "negative_probability", "reference_days", "threshold_multiplier"), "population_baseline")
    valid = _integer(population["valid_sample_count"], "valid_sample_count", 1, n_hours)
    pos = _integer(population["positive_count"], "positive_count", 0, valid)
    neg = _integer(population["negative_count"], "negative_count", 0, valid)
    if pos + neg > valid:
        raise ValueError("Population counts exceed valid samples.")
    # Relative tolerance permits tiny float/JSON rounding differences. No
    # absolute floor: zero counts require an exactly zero probability.
    # Validate the recorded ratio only; never replace it or rerun B/C.
    for name, count in (("positive_probability", pos), ("negative_probability", neg)):
        probability = _number(population[name], name, 0, 1)
        if not math.isclose(probability, count / valid, rel_tol=1e-12, abs_tol=0.0):
            raise ValueError(f"Population probability inconsistent with count/valid_sample_count: {name}.")
    if (_integer(population["reference_days"], "population reference_days", 1) != config["reference_days"] or
            _number(population["threshold_multiplier"], "population threshold_multiplier", 0) !=
            config["threshold_multiplier"]):
        raise ValueError("Population parameters differ from configuration.")
    environment = _fields(summary["environment"],
                          ("python_version", "numpy_version", "scipy_version", "sklearn_version", "n_clusters",
                           "random_state", "use_circular_hour", "standardize_features", "kmeans_n_init",
                           "kmeans_init", "kmeans_algorithm"), "environment")
    for name in ("python_version", "numpy_version", "scipy_version", "sklearn_version", "kmeans_n_init",
                 "kmeans_init", "kmeans_algorithm"):
        _text(environment[name], name)
    if (_integer(environment["n_clusters"], "environment n_clusters", 1) != k or
            _integer(environment["random_state"], "environment random_state", 0) != config["random_state"] or
            environment["use_circular_hour"] is not True or environment["standardize_features"] is not True):
        raise ValueError("Environment metadata differs from clustering configuration.")
    for name in ("reference_comparison", "legacy_comparison"):
        comparison = summary[name]
        if comparison is not None:
            _fields(comparison, ("all_match", "checks"), name)
            if type(comparison["all_match"]) is not bool or type(comparison["checks"]) is not dict:
                raise ValueError(f"Invalid comparison diagnostics: {name}.")
    selection = _fields(summary["earthquake_selection"],
                        ("n_catalog_events", "n_selected_events", "events"), "earthquake_selection")
    n_events = _integer(selection["n_selected_events"], "n_selected_events", 1)
    _integer(selection["n_catalog_events"], "n_catalog_events", n_events)
    if type(selection["events"]) is not list or len(selection["events"]) != n_events:
        raise ValueError("Inconsistent selected events.")
    event_dates = set()
    for event in selection["events"]:
        _fields(event, ("date", "magnitude", "event_id"), "selected event")
        try:
            event_date = date.fromisoformat(event["date"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid selected event date.") from exc
        if event_date in event_dates or not start_date <= event_date <= end_date:
            raise ValueError("Duplicate or out-of-coverage selected event date.")
        event_dates.add(event_date)
        _number(event["magnitude"], "event magnitude", config["minimum_magnitude"])
        _text(event["event_id"], "event_id")
    subset = _fields(summary["earthquake_subset"],
                     ("counts_shape", "delta_tec_shape", "positive_count", "negative_count",
                      "positive_count_range", "negative_count_range"), "earthquake_subset")
    _integer_list(subset["counts_shape"], [2 * days + 1, 24], "counts_shape")
    _integer_list(subset["delta_tec_shape"], [2 * days + 1, 24, n_events], "delta_tec_shape")
    for polarity in ("positive", "negative"):
        _integer(subset[polarity + "_count"], polarity + "_count", 0, (2 * days + 1) * 24 * n_events)
        bounds = subset[polarity + "_count_range"]
        if type(bounds) is not list or len(bounds) != 2:
            raise ValueError("Invalid subset count range.")
        low, high = [_integer(value, "subset count range", 0, n_events) for value in bounds]
        if low > high:
            raise ValueError("Reversed subset count range.")
    significance = _fields(summary["statistical_significance"], ("full_window", "pre_event"),
                           "statistical_significance")
    full = _significance_scope(significance["full_window"], -days, days, critical_z)
    pre = _significance_scope(significance["pre_event"], -days, 0, critical_z)
    if pre != {cell for cell in full if cell[0] <= 0}:
        raise ValueError("pre_event cells must be the pre-event subset of full_window.")
    if significance["pre_event"]["overlap_cells"] != [
        cell for cell in significance["full_window"]["overlap_cells"] if cell["relative_day"] <= 0
    ]:
        raise ValueError("Inconsistent pre-event overlap diagnostics.")
    clustering = _fields(summary["clustering"],
                         ("window_selection", "relative_days", "n_significant_cells", "raw_features",
                          "feature_shape", "standardized_feature_shape", "standardized_centers",
                          "decoded_centers", "rounded_centers", "temporal_anchors", "silhouette", "inertia"),
                         "clustering")
    if clustering["window_selection"] != "pre_event":
        raise ValueError("Invalid pre-event clustering scope.")
    _integer_list(clustering["relative_days"], list(range(-days, 1)), "clustering relative_days")
    n_cells = _integer(clustering["n_significant_cells"], "n_significant_cells", k)
    if n_cells != len(pre):
        raise ValueError("Clustering count must match pre-event nonzero cells.")
    _matrix(clustering["raw_features"], n_cells, 3, "raw_features")
    if {(row[1], row[0], row[2]) for row in clustering["raw_features"]} != pre:
        raise ValueError("Clustering raw features differ from pre-event cells.")
    for name in ("feature_shape", "standardized_feature_shape"):
        _integer_list(clustering[name], [n_cells, 4], name)
    for name, width in (("standardized_centers", 4), ("decoded_centers", 3), ("rounded_centers", 3)):
        _matrix(clustering[name], k, width, name)
    _number(clustering["silhouette"], "silhouette", -1, 1)
    _number(clustering["inertia"], "inertia", 0)
    anchors = clustering["temporal_anchors"]
    if type(anchors) is not list or len(anchors) != k:
        raise ValueError("Invalid temporal anchors.")
    ids, positives, negatives = set(), 0, 0
    for anchor in anchors:
        _fields(anchor, ("cluster_id", "hour", "centroid_day", "rounded_day", "centroid_polarity",
                         "dominant_polarity", "n_positive", "n_negative", "n_members"), "anchor")
        cluster_id = _integer(anchor["cluster_id"], "cluster_id", 0, k - 1)
        if cluster_id in ids:
            raise ValueError("Duplicate cluster_id.")
        ids.add(cluster_id)
        _integer(anchor["hour"], "anchor hour", 0, 23)
        _number(anchor["centroid_day"], "centroid_day", -days, 0)
        _integer(anchor["rounded_day"], "rounded_day", -days, 0)
        _number(anchor["centroid_polarity"], "centroid_polarity", -1, 1)
        pos = _integer(anchor["n_positive"], "n_positive", 0)
        neg = _integer(anchor["n_negative"], "n_negative", 0)
        members = _integer(anchor["n_members"], "n_members", 1)
        dominant = _integer(anchor["dominant_polarity"], "dominant_polarity", -1, 1)
        if members != pos + neg or dominant != (1 if pos > neg else -1 if neg > pos else 0):
            raise ValueError("Inconsistent anchor polarity composition.")
        positives += pos
        negatives += neg
    if positives != sum(cell[2] == 1 for cell in pre) or negatives != sum(cell[2] == -1 for cell in pre):
        raise ValueError("Anchor composition differs from pre-event cells.")


def build_historical_bc_evidence(summary: dict, *, provenance: dict | None = None) -> dict:
    """Validate reproduction-summary V1 and preserve it as historical context.

    Structural checks do not recompute B/C or require reference comparisons to
    pass. Relative days, overlap diagnostics and mixed clusters remain intact.
    Unknown upstream observation/interpolation provenance is not manufactured.
    """
    summary = _strict_copy(summary)
    _validate_historical_summary(summary)
    return dict(evidence_type=HISTORICAL_EVIDENCE_TYPE, schema_version=EVIDENCE_SCHEMA_VERSION,
                provenance=_provenance(provenance), historical_summary=summary,
                anchor_time_basis="historical_relative_day_and_utc_hour",
                original_observation_quality=None, original_interpolation_history=None)


def load_historical_bc_evidence(path: str | Path) -> dict:
    """Read strict JSON and hash its bytes; never open its referenced inputs."""
    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"Duplicate JSON key: {key}.")
            obj[key] = value
        return obj

    def reject_constant(value):
        raise ValueError(f"Invalid JSON constant: {value}.")

    path = Path(path)
    raw = path.read_bytes()
    summary = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    evidence = build_historical_bc_evidence(summary)
    evidence["summary_artifact"] = dict(identity=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                                        size_bytes=len(raw), hash_verification="computed_from_read_bytes")
    return evidence


def evidence_to_json(evidence: dict) -> str:
    """Deterministically serialize builder output without timestamps or I/O.

    This checks envelope/version and strict JSON values, not authenticity of
    provenance or externally edited evidence. Use the builders to validate
    scientific source contracts; this is not a generic evidence-file loader.
    """
    evidence = _strict_copy(evidence)
    _fields(evidence, ("evidence_type", "schema_version"), "evidence")
    if evidence["evidence_type"] not in (TEMPORAL_EVIDENCE_TYPE, HISTORICAL_EVIDENCE_TYPE) or (
        type(evidence["schema_version"]) is not int or evidence["schema_version"] != EVIDENCE_SCHEMA_VERSION
    ):
        raise ValueError("Unsupported evidence type/schema version.")
    return json.dumps(evidence, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n"
