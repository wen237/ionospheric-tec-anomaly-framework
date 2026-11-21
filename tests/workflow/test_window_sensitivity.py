"""Synthetic hourly diagnostics; no research observations are manufactured."""

from datetime import datetime, timedelta
from io import BytesIO

import numpy as np
import pytest

from src.spatial_verification.spatial_anomaly import compute_hourly_spatial_anomalies, compute_spatial_anomalies
from src.workflow.window_sensitivity import (
    bounds, build_window_diagnostic, compare_saved_counts, hourly_rows,
    load_hourly_snapshot, make_hourly_snapshot, masks, nearest_cell, validate_snapshot,
)


@pytest.fixture
def hourly_case():
    tec = np.full((366, 2), 10.0)
    tec[360:] = [[20, 0], [0, 20], [20, 10], [10, 0], [10, 10], [np.nan, 10]]
    tec[np.arange(4, 360, 24), 1] = np.nan
    with pytest.warns(RuntimeWarning, match="All-NaN"):
        hourly = compute_hourly_spatial_anomalies(tec, 24, 15, 6, 3.0, [0], [0, 5])
    times = [datetime(2022, 1, 16) + timedelta(hours=h) for h in range(6)]
    a = make_hourly_snapshot(hourly, times, [0], [0, 5])
    base = dict(start_utc="2022-01-16T00:00:00Z", end_utc="2022-01-16T03:00:00Z")
    ext = dict(start_utc=base["start_utc"], end_utc="2022-01-16T05:00:00Z")
    return tec, a, base, ext


def test_exact_added_hours_counts_ratios_and_validity(hourly_case):
    _, a, base, ext = hourly_case
    d = build_window_diagnostic(a, base, ext, case_id="synthetic", selected_cells=[dict(latitude=0, longitude=0)])
    assert d["parameters"] == dict(reference_days=15, k=3.0, samples_per_day=24, grid_orientation="canonical")
    assert d["additional_utc_hours"] == ["2022-01-16T04:00:00Z", "2022-01-16T05:00:00Z"]
    assert d["segments"]["baseline"]["positive"]["anomaly_grid_hours"] == 3
    assert d["segments"]["additional"]["positive"]["anomaly_grid_hours"] == 0
    assert d["segments"]["additional"]["positive"]["evaluated_grid_hours"] == 2
    assert d["segments"]["additional"]["target_finite_grid_hours"] == 3
    assert d["segments"]["additional"]["empty_reference_grid_hours"] == 1
    cell = d["relevant_cells"][0]["segments"]
    assert cell["baseline"]["positive"]["anomaly_grid_hours"] == 2
    assert cell["baseline"]["positive"]["mean_occurrence_ratio_percent"] == 50.0
    assert cell["extended"]["positive"]["mean_occurrence_ratio_percent"] == 2 / 6 * 100
    assert cell["extended"]["ratio_denominator_hours"] == 6
    assert cell["extended"]["positive"]["evaluated_grid_hours"] == 5
    assert d["contribution"]["positive"]["lower_additional_anomaly_rate_than_baseline"] is True
    assert d["human_approval_required"] is True and d["execution_eligible"] is False
    rows = hourly_rows(a, base, ext, d["additional_utc_hours"][0], d["additional_utc_hours"][-1], 0, 5)
    assert rows[0]["cell"]["positive"] == -1 and rows[0]["cell"]["target_finite"] is True
    assert rows[0]["cell"]["reference_finite_count"] == 0
    assert rows[1]["cell"]["positive"] == 0


def test_aggregation_matches_original_full_window_and_saved_checks(hourly_case):
    tec, a, base, ext = hourly_case
    results = {}
    with pytest.warns(RuntimeWarning):
        for key, hours in (("baseline", 4), ("extended", 6)):
            result = compute_spatial_anomalies(tec[:360 + hours], 24, 15, hours, 3.0, [0], [0, 5])
            results[key] = {field: getattr(result, field) for field in
                            ("positive_counts", "negative_counts", "positive_ratio", "negative_ratio", "latitudes", "longitudes")}
            results[key]["ratio_denominator"] = np.array(hours)
    assert compare_saved_counts(a, base, ext, results) == dict(baseline=True, extended=True)
    results["extended"]["negative_counts"][0, 0] += 1
    assert compare_saved_counts(a, base, ext, results)["extended"] is False


def test_nested_window_can_add_hours_on_both_sides(hourly_case):
    _, a, base, ext = hourly_case
    base = dict(start_utc="2022-01-16T01:00:00Z", end_utc="2022-01-16T04:00:00Z")
    d = build_window_diagnostic(a, base, ext, case_id="synthetic")
    assert d["additional_utc_hours"] == ["2022-01-16T00:00:00Z", "2022-01-16T05:00:00Z"]
    with pytest.raises(ValueError, match="additional"):
        hourly_rows(a, base, ext, "2022-01-16T00:00:00Z", "2022-01-16T05:00:00Z")


@pytest.mark.parametrize("change", ["timezone", "minute", "duration", "not_nested", "equal"])
def test_invalid_temporal_contract(hourly_case, change):
    _, a, base, ext = hourly_case
    if change == "timezone":
        base["start_utc"] = "2022-01-16T00:00:00+08:00"
    if change == "minute":
        base["end_utc"] = "2022-01-16T03:01:00Z"
    if change == "duration":
        base["inclusive_hours"] = 99
    if change == "not_nested":
        base["start_utc"] = "2022-01-15T23:00:00Z"
    if change == "equal":
        base = dict(ext)
    with pytest.raises(ValueError):
        build_window_diagnostic(a, base, ext, case_id="synthetic")


def test_snapshot_roundtrip_and_no_aggregate_substitution(hourly_case):
    _, a, base, ext = hourly_case
    stream = BytesIO()
    np.savez_compressed(stream, **a)
    restored = load_hourly_snapshot(stream.getvalue())
    assert build_window_diagnostic(restored, base, ext, case_id="synthetic") == build_window_diagnostic(a, base, ext, case_id="synthetic")
    stream = BytesIO()
    np.savez(stream, positive_counts=np.zeros((1, 2)))
    with pytest.raises(ValueError):
        load_hourly_snapshot(stream.getvalue())


def test_coordinates_and_unknown_zero_baseline(hourly_case):
    _, a, base, ext = hourly_case
    assert nearest_cell(a, 0, 5) == (0, 1, 1)
    with pytest.raises(ValueError):
        nearest_cell(a, True, 0)
    a["positive"][:] = 0
    d = build_window_diagnostic(a, base, ext, case_id="synthetic")
    assert d["contribution"]["positive"]["additional_anomaly_share_of_extended"] is None
    a["epochs"][2] += 3600
    with pytest.raises(ValueError, match="Continuous"):
        validate_snapshot(a)
