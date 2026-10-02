import numpy as np

from src.statistical_clustering.population_anomaly import (
    compute_population_anomaly_probability,
)


def test_positive_negative_and_normal_anomalies():

    tec = np.asarray(
        [
            [10.0, 20.0, 30.0],
            [10.0, 20.0, 30.0],
            [10.0, 20.0, 30.0],
            [10.0, 20.0, 30.0],
            [30.0, 5.0, 30.0],
        ],
        dtype=np.float64,
    )

    result = compute_population_anomaly_probability(
        tec=tec,
        reference_days=4,
        threshold_multiplier=3.0,
    )

    assert result.positive_count == 1
    assert result.negative_count == 1
    assert result.valid_sample_count == 3

    assert result.positive_probability == 1 / 3
    assert result.negative_probability == 1 / 3


def test_reference_is_computed_independently_for_each_hour():

    tec = np.asarray(
        [
            [10.0, 100.0],
            [10.0, 100.0],
            [10.0, 100.0],
            [10.0, 100.0],
            [50.0, 50.0],
        ],
        dtype=np.float64,
    )

    result = compute_population_anomaly_probability(
        tec=tec,
        reference_days=4,
        threshold_multiplier=3.0,
    )

    assert result.positive_count == 1
    assert result.negative_count == 1


def test_reference_uses_only_preceding_days():

    tec = np.asarray(
        [
            [10.0],
            [10.0],
            [10.0],
            [10.0],
            [100.0],
        ],
        dtype=np.float64,
    )

    result = compute_population_anomaly_probability(
        tec=tec,
        reference_days=4,
        threshold_multiplier=3.0,
    )

    assert result.positive_count == 1
    assert result.negative_count == 0


def test_reference_window_rolls_forward():

    tec = np.asarray(
        [
            [10.0],
            [10.0],
            [10.0],
            [10.0],
            [100.0],
            [100.0],
            [100.0],
            [100.0],
            [100.0],
        ],
        dtype=np.float64,
    )

    result = compute_population_anomaly_probability(
        tec=tec,
        reference_days=4,
        threshold_multiplier=3.0,
    )

    assert result.positive_count == 2
    assert result.negative_count == 0


def test_values_equal_to_bounds_are_not_anomalies():

    tec = np.asarray(
        [
            [10.0, 20.0],
            [10.0, 20.0],
            [10.0, 20.0],
            [10.0, 20.0],
            [10.0, 20.0],
        ],
        dtype=np.float64,
    )

    result = compute_population_anomaly_probability(
        tec=tec,
        reference_days=4,
        threshold_multiplier=3.0,
    )

    assert result.positive_count == 0
    assert result.negative_count == 0


def test_valid_sample_count_matches_target_dimensions():

    tec = np.full(
        shape=(10, 6),
        fill_value=10.0,
        dtype=np.float64,
    )

    result = compute_population_anomaly_probability(
        tec=tec,
        reference_days=4,
        threshold_multiplier=3.0,
    )

    expected_count = (
        (10 - 4) * 6
    )

    assert result.valid_sample_count == expected_count

    assert result.positive_count == 0
    assert result.negative_count == 0

    assert result.positive_probability == 0.0
    assert result.negative_probability == 0.0

