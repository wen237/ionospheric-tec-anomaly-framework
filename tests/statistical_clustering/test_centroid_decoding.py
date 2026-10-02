import numpy as np

from sklearn.preprocessing import StandardScaler

from src.statistical_clustering.centroid_decoding import (
    decode_cluster_centroids,
)


def test_known_circular_hours():

    original_centers = np.asarray(
        [
            [0.0,  1.0, -10.0,  1.0],
            [1.0,  0.0, -20.0, -1.0],
            [0.0, -1.0, -15.0,  1.0],
            [-1.0, 0.0,  -5.0, -1.0],
        ],
        dtype=np.float64,
    )

    scaler = StandardScaler().fit(
        original_centers
    )

    standardized_centers = scaler.transform(
        original_centers
    )

    result = decode_cluster_centroids(
        standardized_centers,
        scaler,
    )

    np.testing.assert_array_equal(
        result.hours,
        np.asarray([0, 6, 12, 18]),
    )

    np.testing.assert_allclose(
        result.relative_days,
        original_centers[:, 2],
        atol=1e-12,
    )

    np.testing.assert_allclose(
        result.polarities,
        original_centers[:, 3],
        atol=1e-12,
    )


def test_inverse_transformation_matches_scaler():

    features = np.asarray(
        [
            [0.0,  1.0, -10.0,  1.0],
            [1.0,  0.0, -20.0, -1.0],
            [0.0, -1.0, -15.0,  1.0],
            [-1.0, 0.0,  -5.0, -1.0],
        ],
        dtype=np.float64,
    )

    scaler = StandardScaler().fit(features)

    standardized_centers = np.asarray(
        [
            [0.25, -0.50, 0.75, 1.00],
            [-0.25, 0.50, -0.75, -1.00],
        ],
        dtype=np.float64,
    )

    expected = scaler.inverse_transform(
        standardized_centers
    )

    result = decode_cluster_centroids(
        standardized_centers,
        scaler,
    )

    np.testing.assert_array_equal(
        result.unscaled_centers,
        expected,
    )


def test_legacy_hour_rounding():

    original_centers = np.asarray(
        [
            [
                np.sin(2.0 * np.pi * 5.6 / 24.0),
                np.cos(2.0 * np.pi * 5.6 / 24.0),
                -10.5,
                0.8,
            ],
            [
                np.sin(2.0 * np.pi * 18.4 / 24.0),
                np.cos(2.0 * np.pi * 18.4 / 24.0),
                -20.5,
                -0.8,
            ],
        ],
        dtype=np.float64,
    )

    scaler = StandardScaler().fit(
        original_centers
    )

    result = decode_cluster_centroids(
        scaler.transform(original_centers),
        scaler,
    )

    np.testing.assert_array_equal(
        result.hours,
        np.asarray([6, 18]),
    )

    np.testing.assert_allclose(
        result.relative_days,
        np.asarray([-10.5, -20.5]),
        atol=1e-12,
    )

