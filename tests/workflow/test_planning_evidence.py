"""Synthetic evidence-contract tests; no fixtures represent observed research."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json

import numpy as np
import pytest

from src.temporal_anomaly.tec_timeseries import TECTimeSeries
from src.temporal_anomaly.temporal_anomaly import detect_temporal_anomalies
from src.workflow.planning_evidence import (
    build_historical_bc_evidence,
    build_temporal_evidence,
    evidence_to_json,
    load_historical_bc_evidence,
)


START = datetime(2000, 2, 29)
END = START + timedelta(hours=23)
VALUE_FIELDS = ("observed", "q1", "median", "q3", "upper_bound", "lower_bound")


@pytest.fixture
def temporal():
    """Actual validated A detector on explicitly synthetic hourly TEC."""
    first = START - timedelta(days=15)
    epochs = np.array([first + timedelta(hours=i) for i in range(16 * 24)], dtype=object)
    values = np.repeat(np.arange(10.0, 26.0), 24)
    values[-24:] = 17.0
    values[-24], values[-23] = 40.0, 0.0
    return detect_temporal_anomalies(values, epochs)


def adapt(result, **kwargs):
    arguments = dict(case_id="synthetic_case", expected_start=START, expected_end=END,
                     input_time_convention="naive_utc")
    arguments.update(kwargs)
    return build_temporal_evidence(result, **arguments)


def subset(result, indices):
    return replace(result, **{name: getattr(result, name)[indices].copy()
                              for name in ("epochs", "anomaly") + VALUE_FIELDS})


def test_valid_temporal_preserves_values_classifications_and_parameters(temporal):
    evidence = adapt(temporal)
    assert evidence["evidence_type"] == "case_temporal_anomalies"
    assert evidence["schema_version"] == 1
    assert evidence["case_id"] == "synthetic_case"
    assert evidence["input_time_convention"] == "naive_utc"
    assert evidence["analysis"] == dict(start_utc="2000-02-29T00:00:00Z",
                                        end_utc="2000-02-29T23:00:00Z",
                                        bounds="inclusive_hourly_samples", expected_hours=24,
                                        result_hours=24, continuous=True)
    assert evidence["counts"] == dict(positive=1, negative=1, valid_normal=22,
                                      unclassifiable=0, missing_timestamp=0)
    assert evidence["parameters"] == dict(reference_days=15, threshold_multiplier=3.0,
                                          min_reference_samples=15)
    for index, row in enumerate(evidence["hourly"]):
        assert row["timestamp_utc"] == temporal.epochs[index].isoformat() + "Z"
        assert row["anomaly_code"] == temporal.anomaly[index]
        assert row["unclassifiable_reasons"] == []
        assert row["nonfinite_values"] == {}
        for name in VALUE_FIELDS:
            assert row[name] == getattr(temporal, name)[index]
    assert [row["classification"] for row in evidence["hourly"][:3]] == [
        "positive", "negative", "valid_normal",
    ]
    assert evidence["observation_quality"] is None
    assert evidence["reference_sample_counts"] is None
    assert evidence["provenance"]["sources"] is None
    assert evidence["provenance"]["processing_history"] is None


def test_zero_codes_distinguish_missing_observations_and_insufficient_reference():
    first = START - timedelta(days=15)
    epochs = [first + timedelta(hours=i) for i in range(16 * 24)]
    values = np.full(len(epochs), 10.0)
    values[-24] = np.nan                    # observation missing, valid references
    values[1] = np.nan                      # reference missing, finite observation
    values[2] = values[-22] = np.nan         # both missing
    result = detect_temporal_anomalies(values, epochs)
    evidence = adapt(result)
    rows = evidence["hourly"]
    assert [row["anomaly_code"] for row in rows[:4]] == [0, 0, 0, 0]
    assert rows[0]["unclassifiable_reasons"] == ["nonfinite_observation"]
    assert rows[1]["unclassifiable_reasons"] == ["insufficient_reference"]
    assert rows[2]["unclassifiable_reasons"] == ["nonfinite_observation", "insufficient_reference"]
    assert rows[3]["classification"] == "valid_normal"
    assert rows[0]["observed"] is None
    assert rows[0]["nonfinite_values"] == {"observed": "nan"}
    assert all(rows[1][field] is None for field in VALUE_FIELDS[1:])
    assert evidence["counts"]["unclassifiable"] == 3
    assert evidence["counts"]["valid_normal"] == 21
    assert "NaN" not in evidence_to_json(evidence)


@pytest.mark.parametrize("value,marker", [(np.inf, "positive_infinity"), (-np.inf, "negative_infinity")])
def test_nonfinite_observations_remain_unclassified_and_preserve_marker(temporal, value, marker):
    observed = temporal.observed.copy()
    observed[2] = value
    evidence = adapt(replace(temporal, observed=observed))
    row = evidence["hourly"][2]
    assert row["classification"] == "unclassifiable"
    assert row["observed"] is None
    assert row["nonfinite_values"] == {"observed": marker}
    assert "Infinity" not in evidence_to_json(evidence)


def test_partial_nonfinite_statistics_are_not_called_normal_or_reference_shortage(temporal):
    upper = temporal.upper_bound.copy()
    upper[2] = np.inf
    row = adapt(replace(temporal, upper_bound=upper))["hourly"][2]
    assert row["classification"] == "unclassifiable"
    assert row["unclassifiable_reasons"] == ["nonfinite_statistics"]
    assert row["nonfinite_values"] == {"upper_bound": "positive_infinity"}


@pytest.mark.parametrize("field", ["upper_bound", "lower_bound"])
def test_equality_with_threshold_is_valid_normal(temporal, field):
    observed = temporal.observed.copy()
    observed[2] = getattr(temporal, field)[2]
    assert adapt(replace(temporal, observed=observed))["hourly"][2]["classification"] == "valid_normal"


def test_relaxed_reference_requirement_is_preserved():
    first = START - timedelta(days=15)
    epochs = [first + timedelta(hours=i) for i in range(16 * 24)]
    values = np.full(len(epochs), 10.0)
    values[0], values[-24] = np.nan, 40.0
    result = detect_temporal_anomalies(values, epochs, min_reference_samples=14)
    evidence = adapt(result)
    assert evidence["parameters"]["min_reference_samples"] == 14
    assert evidence["hourly"][0]["classification"] == "positive"


def test_numpy_parameter_scalars_serialize_as_json_numbers(temporal):
    evidence = adapt(replace(temporal, min_reference_samples=np.int64(15),
                             threshold_multiplier=np.float64(3.0)))
    assert json.loads(evidence_to_json(evidence))["parameters"]["threshold_multiplier"] == 3.0


def test_missing_internal_and_edge_hours_are_explicit_without_normal_filling(temporal):
    evidence = adapt(subset(temporal, np.arange(1, 23)[np.arange(1, 23) != 10]))
    assert evidence["analysis"]["continuous"] is False
    assert evidence["analysis"]["result_hours"] == 21
    assert evidence["counts"]["missing_timestamp"] == 3
    assert sum(evidence["counts"].values()) == 24
    for index in (0, 10, 23):
        row = evidence["hourly"][index]
        assert row["result_present"] is False
        assert row["anomaly_code"] is None
        assert row["classification"] == "missing_timestamp"
        assert row["nonfinite_values"] == {}
        assert all(row[name] is None for name in VALUE_FIELDS)


def test_empty_result_can_describe_a_completely_missing_expected_period(temporal):
    evidence = adapt(subset(temporal, np.array([], dtype=int)))
    assert evidence["counts"]["missing_timestamp"] == 24
    assert evidence["counts"]["valid_normal"] == 0
    assert evidence["analysis"]["result_hours"] == 0


def test_single_hour_and_cross_midnight_leap_day_bounds(temporal):
    one = adapt(subset(temporal, [23]), expected_start=END)
    assert one["analysis"]["expected_hours"] == 1
    crossing = adapt(subset(temporal, [23]), expected_start=END,
                     expected_end=END + timedelta(hours=2))
    assert [row["timestamp_utc"] for row in crossing["hourly"]] == [
        "2000-02-29T23:00:00Z", "2000-03-01T00:00:00Z", "2000-03-01T01:00:00Z",
    ]
    assert crossing["counts"]["missing_timestamp"] == 2


def test_aware_utc_matches_same_instants_without_changing_values(temporal):
    aware = replace(temporal, epochs=np.array([t.replace(tzinfo=timezone.utc)
                                              for t in temporal.epochs], dtype=object))
    evidence = adapt(aware, expected_start=START.replace(tzinfo=timezone.utc),
                     expected_end=END.replace(tzinfo=timezone.utc), input_time_convention="aware_utc")
    assert evidence["hourly"] == adapt(temporal)["hourly"]


@pytest.mark.parametrize("kind", ["duplicate", "reversed", "string", "numpy_datetime", "nonhourly",
                                  "mixed_timezone", "non_utc", "fold", "outside", "two_dimensional"])
def test_rejects_malformed_result_timestamps(temporal, kind):
    epochs = temporal.epochs.copy()
    if kind == "duplicate":
        epochs[1] = epochs[0]
    elif kind == "reversed":
        epochs[[0, 1]] = epochs[[1, 0]]
    elif kind == "string":
        epochs[0] = "2000-02-29T00:00:00Z"
    elif kind == "numpy_datetime":
        epochs[0] = np.datetime64(START)
    elif kind == "nonhourly":
        epochs[0] += timedelta(minutes=1)
    elif kind == "mixed_timezone":
        epochs[0] = epochs[0].replace(tzinfo=timezone.utc)
    elif kind == "non_utc":
        epochs[0] = epochs[0].replace(tzinfo=timezone(timedelta(hours=8)))
    elif kind == "fold":
        epochs[0] = epochs[0].replace(fold=1)
    elif kind == "outside":
        epochs[0] -= timedelta(hours=1)
    else:
        epochs = epochs[:, None]
    with pytest.raises(ValueError):
        adapt(replace(temporal, epochs=epochs))


@pytest.mark.parametrize("kwargs", [dict(expected_start=END, expected_end=START),
                                    dict(expected_start="2000-02-29T00:00:00Z"),
                                    dict(expected_end=END + timedelta(seconds=1)),
                                    dict(input_time_convention="unknown"),
                                    dict(input_time_convention="aware_utc"), dict(case_id="")])
def test_rejects_invalid_declared_analysis(temporal, kwargs):
    with pytest.raises(ValueError):
        adapt(temporal, **kwargs)


@pytest.mark.parametrize("code", [True, 2, 0.5, np.nan, "0"])
def test_rejects_invalid_anomaly_codes(temporal, code):
    codes = np.full(24, code)
    with pytest.raises(ValueError):
        adapt(replace(temporal, anomaly=codes))


@pytest.mark.parametrize("dtype", [np.int8, np.int16, np.int32, np.int64])
def test_accepts_signed_integer_anomaly_dtypes(temporal, dtype):
    codes = temporal.anomaly.astype(dtype)
    evidence = adapt(replace(temporal, anomaly=codes))
    assert [row["anomaly_code"] for row in evidence["hourly"]] == codes.tolist()
    assert codes.dtype == np.dtype(dtype)


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16, np.uint32, np.uint64])
def test_accepts_unsigned_integer_anomaly_dtypes_for_nonnegative_codes(temporal, dtype):
    nonnegative = subset(temporal, [0, 2])
    codes = nonnegative.anomaly.astype(dtype)
    evidence = adapt(replace(nonnegative, anomaly=codes))
    assert evidence["hourly"][0]["anomaly_code"] == 1
    assert evidence["hourly"][2]["anomaly_code"] == 0
    assert codes.dtype == np.dtype(dtype)


@pytest.mark.parametrize("dtype", [np.float16, np.float32, np.float64, np.bool_])
def test_rejects_numerically_equivalent_float_or_bool_anomaly_dtypes(temporal, dtype):
    source = subset(temporal, [0, 2]) if dtype is np.bool_ else temporal
    codes = source.anomaly.astype(dtype)
    before = codes.copy()
    with pytest.raises(ValueError, match="anomaly"):
        adapt(replace(source, anomaly=codes))
    assert codes.dtype == np.dtype(dtype)
    np.testing.assert_array_equal(codes, before)


@pytest.mark.parametrize("kind", ["mismatched_shape", "complex", "wrong_polarity", "false_normal",
                                  "nonzero_missing", "quartile_order", "bound_order"])
def test_rejects_inconsistent_result_without_reclassifying(temporal, kind):
    if kind == "mismatched_shape":
        result = replace(temporal, q1=temporal.q1[:-1])
    elif kind == "complex":
        result = replace(temporal, observed=temporal.observed.astype(complex))
    elif kind in ("wrong_polarity", "false_normal"):
        codes = temporal.anomaly.copy()
        codes[0] = -1 if kind == "wrong_polarity" else 0
        result = replace(temporal, anomaly=codes)
    elif kind == "nonzero_missing":
        observed = temporal.observed.copy()
        observed[0] = np.nan
        result = replace(temporal, observed=observed)
    else:
        name = "q1" if kind == "quartile_order" else "lower_bound"
        values = getattr(temporal, name).copy()
        values[0] = 100.0
        result = replace(temporal, **{name: values})
    with pytest.raises(ValueError):
        adapt(result)


def test_location_and_provenance_preserved_and_detached(temporal):
    series = TECTimeSeries(epochs=temporal.epochs, tec=temporal.observed,
                           requested_latitude=33.02, requested_longitude=69.46,
                           grid_latitude=32.5, grid_longitude=70.0,
                           latitude_index=48, longitude_index=50)
    provenance = dict(sources=[dict(identity="synthetic-day.npz", sha256="a" * 64)],
                      processing_history="Synthetic input; upstream history not known.")
    evidence = adapt(temporal, time_series=series, provenance=provenance)
    assert evidence["location"]["requested_latitude"] == 33.02
    assert evidence["location"]["grid_latitude"] == 32.5
    assert evidence["location"]["longitude_index"] == 50
    assert evidence["provenance"]["source_hash_verification"] == "not_performed"
    provenance["sources"][0]["sha256"] = "b" * 64
    assert evidence["provenance"]["sources"][0]["sha256"] == "a" * 64
    with pytest.raises(ValueError, match="does not match"):
        adapt(temporal, time_series=replace(series, tec=series.tec + 1))
    with pytest.raises(ValueError):
        adapt(temporal, time_series=replace(series, grid_latitude=np.nan))


@pytest.mark.parametrize("provenance", [dict(sources=[]), dict(sources=[dict(identity="a", sha256="bad")]),
                                        dict(sources=[dict(identity="", sha256=None)]),
                                        dict(processing_history=float("nan")), {1: "bad"},
                                        dict(unrecognized="field")])
def test_rejects_invalid_provenance(temporal, provenance):
    with pytest.raises(ValueError):
        adapt(temporal, provenance=provenance)


def test_temporal_content_and_serialization_are_deterministic_without_input_mutation(temporal):
    before = {name: getattr(temporal, name).copy() for name in VALUE_FIELDS + ("anomaly", "epochs")}
    first, second = adapt(temporal), adapt(temporal)
    assert first == second
    assert evidence_to_json(first) == evidence_to_json(second)
    assert json.loads(evidence_to_json(first)) == first
    for name, array in before.items():
        assert np.array_equal(getattr(temporal, name), array)
    assert not {"candidates", "policy", "approval_status"} & set(first)


def synthetic_scope(start, end, cells, overlaps):
    positive = sum(cell[2] == 1 for cell in cells)
    negative = len(cells) - positive
    return dict(relative_day_start=start, relative_day_end=end, shape=[end - start + 1, 24],
                positive_significant_count=positive + len(overlaps),
                negative_significant_count=negative + len(overlaps),
                positive_mask_count=positive, negative_mask_count=negative,
                zero_mask_count=(end - start + 1) * 24 - len(cells),
                nonzero_mask_count=len(cells), overlap_count=len(overlaps),
                significant_cells=[dict(relative_day=d, hour_utc=h, polarity=p) for d, h, p in cells],
                overlap_cells=deepcopy(overlaps))


@pytest.fixture
def historical():
    """Hand-authored synthetic summary, never a fabricated observed dataset."""
    cells = [(-22, 6, -1), (-9, 9, 1), (-8, 8, 1), (-7, 7, -1)]
    overlap = dict(relative_day=-5, hour_utc=3, positive_z=2.2, negative_z=2.3)
    post_overlap = dict(relative_day=30, hour_utc=11, positive_z=2.4, negative_z=2.5)
    return dict(
        summary_type="afghanistan_historical_bc_reproduction", schema_version=1,
        inputs={name: dict(path=f"synthetic-{name}", size_bytes=123, sha256="a" * 64)
                for name in ("tec", "usgs_catalog")},
        configuration=dict(start_date="1999-01-01", end_date="2021-12-31", minimum_magnitude=6.0,
                           observation_days=30, reference_days=15, threshold_multiplier=3.0,
                           critical_z=1.96, clustering_days=[-30, 0], n_clusters=2, random_state=42),
        environment=dict(python_version="synthetic", numpy_version="synthetic", scipy_version="synthetic",
                         sklearn_version="synthetic", n_clusters=2, random_state=42,
                         use_circular_hour=True, standardize_features=True, kmeans_n_init="auto",
                         kmeans_init="k-means++", kmeans_algorithm="lloyd"),
        historical_data=dict(input_shape=[201624, 1], input_dtype="float64", daily_shape=[8401, 24],
                             n_days=8401, n_hours=201624, assigned_start_utc="1999-01-01T00:00:00Z",
                             assigned_end_utc="2021-12-31T23:00:00Z",
                             timeline_provenance="Synthetic metadata; assigned timeline, not embedded timestamps.",
                             finite_count=201624, nan_count=0, infinite_count=0, minimum=1.0, maximum=20.0,
                             observed_input_count=201624, interpolated_count=0, values_unchanged=True),
        population_baseline=dict(positive_count=1000, negative_count=2000, valid_sample_count=201264,
                                 positive_probability=1000 / 201264, negative_probability=2000 / 201264,
                                 reference_days=15, threshold_multiplier=3.0),
        earthquake_selection=dict(n_catalog_events=5, n_selected_events=4,
                                  events=[dict(date=f"2000-0{i}-01", magnitude=6.5, event_id=f"synthetic-{i}")
                                          for i in range(1, 5)]),
        earthquake_subset=dict(counts_shape=[61, 24], delta_tec_shape=[61, 24, 4],
                               positive_count=100, negative_count=100,
                               positive_count_range=[0, 4], negative_count_range=[0, 4]),
        statistical_significance=dict(full_window=synthetic_scope(-30, 30, cells + [(1, 5, 1)],
                                                                  [overlap, post_overlap]),
                                      pre_event=synthetic_scope(-30, 0, cells, [overlap])),
        clustering=dict(window_selection="pre_event", relative_days=list(range(-30, 1)),
                        n_significant_cells=4, raw_features=[[h, d, p] for d, h, p in cells],
                        feature_shape=[4, 4], standardized_feature_shape=[4, 4],
                        standardized_centers=[[0.0] * 4 for _ in range(2)],
                        decoded_centers=[[8, -8.0, 1 / 3], [6, -22.0, -1.0]],
                        rounded_centers=[[8, -8, 0], [6, -22, -1]],
                        temporal_anchors=[dict(cluster_id=0, hour=8, centroid_day=-8.0, rounded_day=-8,
                                               centroid_polarity=1 / 3, dominant_polarity=1,
                                               n_positive=2, n_negative=1, n_members=3),
                                          dict(cluster_id=1, hour=6, centroid_day=-22.0, rounded_day=-22,
                                               centroid_polarity=-1.0, dominant_polarity=-1,
                                               n_positive=0, n_negative=1, n_members=1)],
                        silhouette=0.1, inertia=1.0),
        reference_comparison=dict(source="synthetic", silhouette_atol=1e-12, checks={}, all_match=False),
        legacy_comparison=None, input_integrity_verified_after_run=True,
    )


def test_historical_preserves_full_pre_overlap_and_mixed_anchors_without_dates(historical):
    evidence = build_historical_bc_evidence(historical)
    assert evidence["evidence_type"] == "historical_bc_context"
    assert evidence["schema_version"] == 1
    assert evidence["historical_summary"] == historical
    assert evidence["anchor_time_basis"] == "historical_relative_day_and_utc_hour"
    assert evidence["original_observation_quality"] is None
    assert evidence["original_interpolation_history"] is None
    assert not {"case_id", "candidates", "policy", "approval_status"} & set(evidence)
    saved = evidence["historical_summary"]
    assert saved["statistical_significance"]["full_window"]["overlap_count"] == 2
    assert saved["statistical_significance"]["pre_event"]["overlap_count"] == 1
    assert saved["clustering"]["temporal_anchors"][0]["n_negative"] == 1
    assert saved["reference_comparison"]["all_match"] is False  # mismatch is not fitted away
    assert json.loads(evidence_to_json(evidence))["historical_summary"] == historical
    historical["clustering"]["temporal_anchors"][0]["rounded_day"] = -1
    assert saved["clustering"]["temporal_anchors"][0]["rounded_day"] == -8


def test_historical_tied_cluster_polarity_preserved(historical):
    a, b = historical["clustering"]["temporal_anchors"]
    a.update(n_positive=1, n_negative=1, n_members=2, dominant_polarity=0, centroid_polarity=0.0)
    b.update(n_positive=1, n_negative=1, n_members=2, dominant_polarity=0, centroid_polarity=0.0)
    assert build_historical_bc_evidence(historical)["historical_summary"]["clustering"]["temporal_anchors"] == [a, b]


def test_historical_consistent_probabilities_are_preserved(historical):
    before = deepcopy(historical)
    evidence = build_historical_bc_evidence(historical)
    assert evidence["historical_summary"]["population_baseline"] == before["population_baseline"]
    assert historical == before


@pytest.mark.parametrize("polarity", ["positive", "negative"])
@pytest.mark.parametrize("relative_error", [2e-12, 0.1])
def test_historical_rejects_inconsistent_probability_without_correcting(historical, polarity, relative_error):
    population = historical["population_baseline"]
    name = polarity + "_probability"
    population[name] *= 1 + relative_error
    before = deepcopy(historical)
    with pytest.raises(ValueError, match=name):
        build_historical_bc_evidence(historical)
    assert historical == before


@pytest.mark.parametrize("polarity", ["positive", "negative"])
def test_historical_probability_tolerance_preserves_small_rounding_difference(historical, polarity):
    population = historical["population_baseline"]
    name = polarity + "_probability"
    population[name] *= 1 + 5e-13  # within documented 1e-12 relative tolerance
    evidence = build_historical_bc_evidence(historical)
    assert evidence["historical_summary"]["population_baseline"][name] == population[name]


@pytest.mark.parametrize("positive_fraction,negative_fraction", [(0, 0), (0, None), (None, 0), (1, 0), (0, 1)])
def test_historical_accepts_consistent_boundary_probabilities(historical, positive_fraction, negative_fraction):
    population = historical["population_baseline"]
    for polarity, fraction in (("positive", positive_fraction), ("negative", negative_fraction)):
        if fraction is not None:
            population[polarity + "_count"] = fraction * population["valid_sample_count"]
            population[polarity + "_probability"] = float(fraction)
    evidence = build_historical_bc_evidence(historical)
    assert evidence["historical_summary"]["population_baseline"] == population


@pytest.mark.parametrize("polarity", ["positive", "negative"])
@pytest.mark.parametrize("probability", [-1e-15, 1.0 + 1e-15])
def test_historical_rejects_out_of_range_probability(historical, polarity, probability):
    name = polarity + "_probability"
    historical["population_baseline"][name] = probability
    with pytest.raises(ValueError, match=name):
        build_historical_bc_evidence(historical)


@pytest.mark.parametrize("polarity", ["positive", "negative"])
def test_historical_zero_count_rejects_tiny_nonzero_probability(historical, polarity):
    population = historical["population_baseline"]
    population[polarity + "_count"] = 0
    population[polarity + "_probability"] = 1e-30
    with pytest.raises(ValueError, match=polarity + "_probability"):
        build_historical_bc_evidence(historical)


@pytest.mark.parametrize("kind", ["wrong_type", "wrong_version", "bool_version", "missing_block",
                                  "malformed_block", "wrong_scope", "bad_count", "bad_hour", "zero_polarity",
                                  "duplicate_cell", "overlap_collision", "bad_overlap_z", "pre_mismatch",
                                  "feature_mismatch", "anchor_composition", "duplicate_cluster",
                                  "bad_anchor_hour", "bad_hash", "nonfinite", "nonstr_key"])
def test_rejects_unsupported_or_malformed_historical_summary(historical, kind):
    full = historical["statistical_significance"]["full_window"]
    clustering = historical["clustering"]
    if kind == "wrong_type":
        historical["summary_type"] = "clustering_summary"
    elif kind in ("wrong_version", "bool_version"):
        historical["schema_version"] = 2 if kind == "wrong_version" else True
    elif kind == "missing_block":
        del historical["historical_data"]
    elif kind == "malformed_block":
        historical["environment"] = []
    elif kind == "wrong_scope":
        clustering["relative_days"] = list(range(-30, 31))
    elif kind == "bad_count":
        full["positive_significant_count"] += 1
    elif kind == "bad_hour":
        full["significant_cells"][0]["hour_utc"] = 24
    elif kind == "zero_polarity":
        full["significant_cells"][0]["polarity"] = 0
    elif kind == "duplicate_cell":
        full["significant_cells"].append(deepcopy(full["significant_cells"][0]))
    elif kind == "overlap_collision":
        full["overlap_cells"][0].update(relative_day=-22, hour_utc=6)
    elif kind == "bad_overlap_z":
        full["overlap_cells"][0]["negative_z"] = 1.0
    elif kind == "pre_mismatch":
        historical["statistical_significance"]["pre_event"]["significant_cells"][0]["hour_utc"] = 5
    elif kind == "feature_mismatch":
        clustering["raw_features"][0][0] = 4
    elif kind == "anchor_composition":
        clustering["temporal_anchors"][0]["n_members"] = 4
    elif kind == "duplicate_cluster":
        clustering["temporal_anchors"][1]["cluster_id"] = 0
    elif kind == "bad_anchor_hour":
        clustering["temporal_anchors"][0]["hour"] = "8"
    elif kind == "bad_hash":
        historical["inputs"]["tec"]["sha256"] = "bad"
    elif kind == "nonfinite":
        clustering["silhouette"] = np.nan
    else:
        historical[1] = "invalid key"
    with pytest.raises(ValueError):
        build_historical_bc_evidence(historical)


@pytest.mark.parametrize("block", ["historical_data", "population_baseline", "environment", "earthquake_subset",
                                   "reference_comparison", "configuration", "clustering",
                                   "earthquake_selection", "statistical_significance"])
def test_historical_rejects_empty_required_sections(historical, block):
    historical[block] = {}
    with pytest.raises(ValueError):
        build_historical_bc_evidence(historical)


@pytest.mark.parametrize("block,field,value", [
    ("historical_data", "n_hours", 2),
    ("historical_data", "daily_shape", [24, 8401]),
    ("historical_data", "input_shape", [201624.0]),
    ("historical_data", "assigned_start_utc", "1999-01-01T00:00:00"),
    ("historical_data", "finite_count", 1),
    ("historical_data", "interpolated_count", 1),
    ("historical_data", "values_unchanged", "true"),
    ("historical_data", "minimum", 100.0),
    ("population_baseline", "reference_days", 14),
    ("population_baseline", "threshold_multiplier", 4.0),
    ("population_baseline", "valid_sample_count", 0),
    ("population_baseline", "positive_count", 201264),
    ("population_baseline", "positive_probability", 1.0),
    ("environment", "n_clusters", 3),
    ("environment", "use_circular_hour", 1),
    ("earthquake_subset", "delta_tec_shape", [61, 24, 5]),
    ("earthquake_subset", "positive_count_range", [4, 0]),
    ("configuration", "clustering_days", [-30, False]),
    ("clustering", "relative_days", list(range(-30, 0)) + [False]),
    ("reference_comparison", "all_match", "false"),
    ("legacy_comparison", "all_match", 1),
])
def test_historical_rejects_inconsistent_metadata(historical, block, field, value):
    if block == "legacy_comparison":
        historical[block] = dict(checks={})
    historical[block][field] = value
    with pytest.raises(ValueError):
        build_historical_bc_evidence(historical)


@pytest.mark.parametrize("kind", ["duplicate_date", "outside_coverage", "below_magnitude", "bool_shape"])
def test_historical_rejects_invalid_selection_or_scope(historical, kind):
    events = historical["earthquake_selection"]["events"]
    if kind == "duplicate_date":
        events[1]["date"] = events[0]["date"]
    elif kind == "outside_coverage":
        events[0]["date"] = "2022-01-01"
    elif kind == "below_magnitude":
        events[0]["magnitude"] = 5.0
    else:
        historical["statistical_significance"]["pre_event"]["shape"] = [31.0, 24]
    with pytest.raises(ValueError):
        build_historical_bc_evidence(historical)


def test_historical_loader_hashes_exact_bytes_and_is_deterministic(historical, tmp_path):
    path = tmp_path / "synthetic-summary.json"
    raw = (json.dumps(historical, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(raw)
    first = load_historical_bc_evidence(path)
    assert first["summary_artifact"] == dict(identity=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                                             size_bytes=len(raw), hash_verification="computed_from_read_bytes")
    assert evidence_to_json(first) == evidence_to_json(load_historical_bc_evidence(path))
    assert first["provenance"]["sources"] is None  # referenced inputs were not opened/verified
    assert path.read_bytes() == raw


@pytest.mark.parametrize("text", ['{"schema_version":1,"schema_version":2}',
                                  '{"value":NaN}', '{"value":Infinity}', '{"value":1e999}',
                                  '[]', '{invalid'])
def test_historical_loader_rejects_non_strict_or_malformed_json(tmp_path, text):
    path = tmp_path / "invalid-summary.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_historical_bc_evidence(path)


@pytest.mark.parametrize("update", [dict(schema_version=2), dict(schema_version=True),
                                    dict(evidence_type="unknown"), dict(extra=float("nan")),
                                    dict(extra=float("inf")), dict(extra=(1, 2))])
def test_serializer_rejects_unsupported_envelope_and_non_json_values(temporal, update):
    evidence = adapt(temporal)
    evidence.update(update)
    with pytest.raises(ValueError):
        evidence_to_json(evidence)
