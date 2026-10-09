import numpy as np
from src.spatial_verification.spatial_anomaly import (
    compute_spatial_anomalies,
)


def test_same_time_of_day_reference_indexing():
    samples_per_day = 2
    reference_days = 3
    window_steps = 2

    tec = np.array(
        [
            [10.0],
            [100.0],
            [20.0],
            [200.0],
            [30.0],
            [300.0],
            [40.0],
            [400.0],
        ]
    )

    reference = np.empty(
        (window_steps, 1, reference_days),
        dtype=float,
    )

    for day in range(reference_days):
        start = day * samples_per_day
        stop = start + window_steps

        reference[:, :, day] = tec[start:stop]

    np.testing.assert_array_equal(
        reference[:, 0, :],
        np.array(
            [
                [10.0, 20.0, 30.0],
                [100.0, 200.0, 300.0],
            ]
        ),
    )


def test_compute_spatial_anomalies_counts_and_ratios():
    tec = np.array(
        [
            [10.0, 100.0],
            [20.0, 200.0],
            [10.0, 100.0],
            [20.0, 200.0],
            [10.0, 100.0],
            [20.0, 200.0],
            [50.0, 50.0],
            [5.0, 500.0],
        ]
    )

    result = compute_spatial_anomalies(
        tec=tec,
        samples_per_day=2,
        reference_days=3,
        window_steps=2,
        k=3.0,
        latitudes=np.array([0.0]),
        longitudes=np.array([0.0, 5.0]),
    )

    np.testing.assert_array_equal(
        result.positive_counts,
        np.array([[1.0, 1.0]]),
    )

    np.testing.assert_array_equal(
        result.negative_counts,
        np.array([[1.0, 1.0]]),
    )

    np.testing.assert_array_equal(
        result.positive_ratio,
        np.array([[50.0, 50.0]]),
    )

    np.testing.assert_array_equal(
        result.negative_ratio,
        np.array([[50.0, 50.0]]),
    )

    assert result.window_steps == 2


def test_values_equal_to_bounds_are_not_anomalies():
    tec = np.array(
        [
            [10.0],
            [10.0],
            [10.0],
            [10.0],
        ]
    )

    result = compute_spatial_anomalies(
        tec=tec,
        samples_per_day=1,
        reference_days=3,
        window_steps=1,
        k=3.0,
        latitudes=np.array([0.0]),
        longitudes=np.array([0.0]),
    )

    assert result.positive_counts[0, 0] == 0
    assert result.negative_counts[0, 0] == 0