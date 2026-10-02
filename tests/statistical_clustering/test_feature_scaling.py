import numpy as np
import pytest

from sklearn.preprocessing import StandardScaler

from src.statistical_clustering.feature_scaling import (
    standardize_clustering_features,
)


def test_standardized_feature_statistics():

    features = np.asarray(
        [
            [0.0,  1.0, -10.0,  1.0],
            [1.0,  0.0,  -5.0,  1.0],
            [0.0, -1.0, -20.0, -1.0],
            [-1.0, 0.0, -15.0, -1.0],
        ],
        dtype=np.float64,
    )

    result = standardize_clustering_features(
        features
    )

    assert result.standardized_features.shape == (
        4,
        4,
    )

    np.testing.assert_allclose(
        result.standardized_features.mean(axis=0),
        np.zeros(4),
        atol=1e-12,
    )

    np.testing.assert_allclose(
        result.standardized_features.std(axis=0),
        np.ones(4),
        atol=1e-12,
    )


def test_matches_sklearn_standard_scaler():

    features = np.asarray(
        [
            [0.0,  1.0, -10.0,  1.0],
            [1.0,  0.0,  -5.0,  1.0],
            [0.0, -1.0, -20.0, -1.0],
            [-1.0, 0.0, -15.0, -1.0],
        ],
        dtype=np.float64,
    )

    expected = StandardScaler().fit_transform(
        features
    )

    result = standardize_clustering_features(
        features
    )

    np.testing.assert_array_equal(
        result.standardized_features,
        expected,
    )


def test_inverse_transformation():

    features = np.asarray(
        [
            [0.0,  1.0, -10.0,  1.0],
            [1.0,  0.0,  -5.0,  1.0],
            [0.0, -1.0, -20.0, -1.0],
            [-1.0, 0.0, -15.0, -1.0],
        ],
        dtype=np.float64,
    )

    result = standardize_clustering_features(
        features
    )

    restored = result.scaler.inverse_transform(
        result.standardized_features
    )

    np.testing.assert_allclose(
        restored,
        features,
        rtol=0,
        atol=1e-12,
    )

