import numpy as np

from src.statistical_clustering.centroid_presentation import (
    prepare_centroid_presentation,
)


def test_afghanistan_centroid_rounding():

    decoded_centers = np.asarray(
        [
            [8.0, -7.77777778, 0.66666667],
            [6.0, -22.0625, -0.625],
        ],
        dtype=np.float64,
    )

    result = prepare_centroid_presentation(
        decoded_centers
    )

    expected = np.asarray(
        [
            [8.0, -8.0, 1.0],
            [6.0, -22.0, -1.0],
        ],
        dtype=np.float64,
    )

    np.testing.assert_array_equal(
        result.rounded_centers,
        expected,
    )


def test_preserves_continuous_centers():

    decoded_centers = np.asarray(
        [
            [8.0, -7.77777778, 0.66666667],
            [6.0, -22.0625, -0.625],
        ],
        dtype=np.float64,
    )

    original = decoded_centers.copy()

    result = prepare_centroid_presentation(
        decoded_centers
    )

    np.testing.assert_array_equal(
        result.continuous_centers,
        original,
    )

    np.testing.assert_array_equal(
        decoded_centers,
        original,
    )


def test_rounding_does_not_force_polarity_sign():

    decoded_centers = np.asarray(
        [
            [8.0, -8.2, 0.4],
            [6.0, -22.2, -0.4],
        ],
        dtype=np.float64,
    )

    result = prepare_centroid_presentation(
        decoded_centers
    )

    np.testing.assert_array_equal(
        result.rounded_centers[:, 2],
        np.asarray([0.0, 0.0]),
    )

