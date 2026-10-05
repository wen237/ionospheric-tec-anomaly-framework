from datetime import datetime, timedelta

import numpy as np

from src.temporal_anomaly.temporal_anomaly import detect_temporal_anomalies


def _make_daily_series(final_value):
    start = datetime(2022, 1, 1, 0, 0)

    epochs = np.array(
        [start + timedelta(days=i) for i in range(16)],
        dtype=object,
    )

    reference_tec = np.array(
        [
            10, 11, 12, 13, 14,
            15, 16, 17, 18, 19,
            20, 21, 22, 23, 24,
        ],
        dtype=float,
    )

    tec = np.append(reference_tec, final_value)

    return epochs, reference_tec, tec


def test_detect_temporal_anomalies_normal_case():
    epochs, reference_tec, tec = _make_daily_series(17.0)

    result = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    q1, median, q3 = np.percentile(
        reference_tec,
        [25, 50, 75],
    )

    upper_bound = median + 3.0 * (q3 - median)
    lower_bound = median - 3.0 * (median - q1)

    assert result.observed[-1] == 17.0
    assert result.q1[-1] == q1
    assert result.median[-1] == median
    assert result.q3[-1] == q3
    assert result.upper_bound[-1] == upper_bound
    assert result.lower_bound[-1] == lower_bound
    assert result.anomaly[-1] == 0


def test_detect_temporal_anomalies_positive_case():
    epochs, _, tec = _make_daily_series(40.0)

    result = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    assert result.observed[-1] == 40.0
    assert result.observed[-1] > result.upper_bound[-1]
    assert result.anomaly[-1] == 1


def test_detect_temporal_anomalies_negative_case():
    epochs, _, tec = _make_daily_series(0.0)

    result = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    assert result.observed[-1] == 0.0
    assert result.observed[-1] < result.lower_bound[-1]
    assert result.anomaly[-1] == -1


def test_detect_temporal_anomalies_missing_reference_data():
    start = datetime(2022, 1, 1, 0, 0)

    epochs = np.array(
        [start + timedelta(days=i) for i in range(16)],
        dtype=object,
    )

    reference_tec = np.array(
        [
            10, 11, 12, 13, 14,
            15, 16, np.nan, 18, 19,
            20, 21, 22, 23, 24,
        ],
        dtype=float,
    )

    tec = np.append(reference_tec, 40.0)

    result_strict = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    assert np.isnan(result_strict.upper_bound[-1])
    assert np.isnan(result_strict.lower_bound[-1])
    assert result_strict.anomaly[-1] == 0

    result_relaxed = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
        min_reference_samples=14,
    )

    assert np.isfinite(result_relaxed.upper_bound[-1])
    assert np.isfinite(result_relaxed.lower_bound[-1])
    assert result_relaxed.anomaly[-1] == 1


def test_detect_temporal_anomalies_multiple_epochs_per_day():
    start = datetime(2022, 1, 1)

    epochs = []
    tec = []

    for day in range(16):
        current_date = start + timedelta(days=day)

        epochs.append(current_date)
        tec.append(10 + day)

        epochs.append(current_date + timedelta(hours=12))
        tec.append(100 + day)

    epochs = np.array(epochs, dtype=object)
    tec = np.array(tec, dtype=float)

    tec[-2] = 40.0
    tec[-1] = 107.0

    result = detect_temporal_anomalies(
        tec,
        epochs,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    assert result.epochs[-2] == epochs[-2]
    assert result.epochs[-1] == epochs[-1]

    assert result.observed[-2] == 40.0
    assert result.observed[-1] == 107.0

    assert result.anomaly[-2] == 1
    assert result.anomaly[-1] == 0