import numpy as np
from src.statistical_clustering.z_test import (
    one_proportion_z_test,
    generate_significance_mask,
)


def test_positive_z_score_matches_manual_calculation():

    positive_counts = np.asarray(
        [[20]],
        dtype=np.float64,
    )

    negative_counts = np.asarray(
        [[10]],
        dtype=np.float64,
    )

    n_events = 100
    p0_positive = 0.10
    p0_negative = 0.10

    result = one_proportion_z_test(
        positive_counts=positive_counts,
        negative_counts=negative_counts,
        n_events=n_events,
        positive_null_proportion=p0_positive,
        negative_null_proportion=p0_negative,
    )

    expected_positive = (
        0.20 - 0.10
    ) / np.sqrt(
        0.10 * 0.90 / 100
    )

    assert np.isclose(
        result.positive_z[0, 0],
        expected_positive,
    )


def test_positive_and_negative_use_separate_null_proportions():

    counts = np.asarray(
        [[10]],
        dtype=np.float64,
    )

    result = one_proportion_z_test(
        positive_counts=counts,
        negative_counts=counts,
        n_events=100,
        positive_null_proportion=0.05,
        negative_null_proportion=0.20,
    )

    assert result.positive_z[0, 0] > 0
    assert result.negative_z[0, 0] < 0


def test_z_score_is_zero_at_null_proportion():

    counts = np.asarray(
        [[10]],
        dtype=np.float64,
    )

    result = one_proportion_z_test(
        positive_counts=counts,
        negative_counts=counts,
        n_events=100,
        positive_null_proportion=0.10,
        negative_null_proportion=0.10,
    )

    assert np.isclose(
        result.positive_z[0, 0],
        0.0,
    )

    assert np.isclose(
        result.negative_z[0, 0],
        0.0,
    )


def test_significance_threshold_is_strict():

    positive_z = np.asarray(
        [[1.96, 1.960001]],
        dtype=np.float64,
    )

    negative_z = np.asarray(
        [[0.0, 0.0]],
        dtype=np.float64,
    )

    mask = generate_significance_mask(
        positive_z=positive_z,
        negative_z=negative_z,
        critical_z=1.96,
    )

    assert mask[0, 0] == 0
    assert mask[0, 1] == 1


def test_significance_mask_polarity():

    positive_z = np.asarray(
        [
            [2.5, 0.0, 0.0],
        ],
        dtype=np.float64,
    )

    negative_z = np.asarray(
        [
            [0.0, 2.5, 0.0],
        ],
        dtype=np.float64,
    )

    mask = generate_significance_mask(
        positive_z=positive_z,
        negative_z=negative_z,
        critical_z=1.96,
    )

    expected = np.asarray(
        [
            [1, -1, 0],
        ],
        dtype=np.int8,
    )

    assert np.array_equal(
        mask,
        expected,
    )

    