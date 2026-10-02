import numpy as np
from datetime import date
from src.statistical_clustering.earthquake_subset import compute_earthquake_subset_anomalies


def test_relative_day_axis():

    tec = np.full(
        (20, 2),
        10.0,
        dtype=np.float64,
    )

    result = compute_earthquake_subset_anomalies(
        tec=tec,
        start_date=date(2000, 1, 1),
        earthquake_dates=np.asarray(
            [date(2000, 1, 10)],
            dtype=object,
        ),
        observation_days=2,
        reference_days=3,
        threshold_multiplier=3.0,
    )

    assert np.array_equal(
        result.relative_days,
        np.asarray(
            [-2, -1, 0, 1, 2]
        ),
    )

    assert result.positive_counts.shape == (
        5,
        2,
    )

    assert result.delta_tec.shape == (
        5,
        2,
        1,
    )


def test_earthquake_day_is_center_of_output():

    tec = np.full(
        (20, 1),
        10.0,
        dtype=np.float64,
    )

    # January 10 is array index 9.
    tec[9, 0] = 100.0

    result = compute_earthquake_subset_anomalies(
        tec=tec,
        start_date=date(2000, 1, 1),
        earthquake_dates=np.asarray(
            [date(2000, 1, 10)],
            dtype=object,
        ),
        observation_days=2,
        reference_days=3,
        threshold_multiplier=3.0,
    )

    assert result.relative_days[2] == 0

    assert result.positive_counts[
        2,
        0,
    ] == 1


def test_subset_reference_is_hour_specific():

    tec = np.empty(
        (20, 2),
        dtype=np.float64,
    )

    tec[:, 0] = 10.0
    tec[:, 1] = 100.0

    # Earthquake day.
    tec[9, 0] = 50.0
    tec[9, 1] = 50.0

    result = compute_earthquake_subset_anomalies(
        tec=tec,
        start_date=date(2000, 1, 1),
        earthquake_dates=np.asarray(
            [date(2000, 1, 10)],
            dtype=object,
        ),
        observation_days=2,
        reference_days=3,
        threshold_multiplier=3.0,
    )

    assert result.positive_counts[
        2,
        0,
    ] == 1

    assert result.negative_counts[
        2,
        1,
    ] == 1


def test_counts_are_summed_across_earthquakes():

    tec = np.full(
        (30, 1),
        10.0,
        dtype=np.float64,
    )

    tec[9, 0] = 100.0
    tec[19, 0] = 100.0

    result = compute_earthquake_subset_anomalies(
        tec=tec,
        start_date=date(2000, 1, 1),
        earthquake_dates=np.asarray(
            [
                date(2000, 1, 10),
                date(2000, 1, 20),
            ],
            dtype=object,
        ),
        observation_days=2,
        reference_days=3,
        threshold_multiplier=3.0,
    )

    assert result.positive_counts[
        2,
        0,
    ] == 2

    assert result.negative_counts[
        2,
        0,
    ] == 0

    assert result.delta_tec.shape == (
        5,
        1,
        2,
    )