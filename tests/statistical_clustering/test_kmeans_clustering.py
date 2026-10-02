import numpy as np
import pytest

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from src.statistical_clustering.kmeans_clustering import (
    apply_kmeans_clustering,
)


def test_kmeans_two_clusters():

    X = np.asarray(
        [
            [-2.0, -2.0, -2.0, -2.0],
            [-1.8, -2.1, -1.9, -2.0],
            [-2.1, -1.9, -2.0, -1.8],
            [ 2.0,  2.0,  2.0,  2.0],
            [ 1.8,  2.1,  1.9,  2.0],
            [ 2.1,  1.9,  2.0,  1.8],
        ],
        dtype=np.float64,
    )

    result = apply_kmeans_clustering(
        standardized_features=X,
        n_clusters=2,
        random_state=42,
    )

    assert result.labels.shape == (6,)
    assert result.centers.shape == (2, 4)

    assert np.unique(result.labels).size == 2

    assert np.isfinite(result.silhouette)
    assert np.isfinite(result.inertia)


def test_matches_sklearn_kmeans():

    X = np.asarray(
        [
            [-2.0, -2.0, -2.0, -2.0],
            [-1.8, -2.1, -1.9, -2.0],
            [-2.1, -1.9, -2.0, -1.8],
            [ 2.0,  2.0,  2.0,  2.0],
            [ 1.8,  2.1,  1.9,  2.0],
            [ 2.1,  1.9,  2.0,  1.8],
        ],
        dtype=np.float64,
    )

    legacy_model = KMeans(
        n_clusters=2,
        random_state=42,
    )

    expected_labels = legacy_model.fit_predict(X)

    expected_centers = (
        legacy_model.cluster_centers_
    )

    expected_silhouette = silhouette_score(
        X,
        expected_labels,
    )

    result = apply_kmeans_clustering(
        standardized_features=X,
        n_clusters=2,
        random_state=42,
    )

    np.testing.assert_array_equal(
        result.labels,
        expected_labels,
    )

    np.testing.assert_array_equal(
        result.centers,
        expected_centers,
    )

    assert result.silhouette == expected_silhouette

    assert result.inertia == legacy_model.inertia_


def test_rejects_invalid_cluster_count():

    X = np.zeros(
        (3, 4),
        dtype=np.float64,
    )

    with pytest.raises(ValueError):
        apply_kmeans_clustering(
            standardized_features=X,
            n_clusters=3,
        )

