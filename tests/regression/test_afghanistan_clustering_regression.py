"""End-to-end regression test for Afghanistan clustering."""

from pathlib import Path

import numpy as np

from src.statistical_clustering.pipeline import (
    run_statistical_clustering,
)

from tests.regression.afghanistan_clustering_reference import (
    EXPECTED_SIGNIFICANT_POINTS,
    EXPECTED_POSITIVE_POINTS,
    EXPECTED_NEGATIVE_POINTS,
    EXPECTED_CLUSTER_SIZES,
    EXPECTED_SILHOUETTE,
    EXPECTED_CONTINUOUS_CENTROIDS,
    EXPECTED_ROUNDED_CENTROIDS,
    EXPECTED_CLUSTER_COMPOSITION,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "afghanistan"
    / "b5_paper_mask.npz"
)


def test_afghanistan_clustering_regression():

    with np.load(
        FIXTURE_PATH,
        allow_pickle=False,
    ) as data:

        mask = data["mask"]

        relative_days = data["relative_days"]

    assert np.count_nonzero(mask) == (
        EXPECTED_SIGNIFICANT_POINTS
    )

    assert np.count_nonzero(mask == 1) == (
        EXPECTED_POSITIVE_POINTS
    )

    assert np.count_nonzero(mask == -1) == (
        EXPECTED_NEGATIVE_POINTS
    )

    result = run_statistical_clustering(
        mask=mask,
        relative_days=relative_days,
        n_clusters=2,
        random_state=42,
    )

    np.testing.assert_array_equal(
        np.bincount(result.kmeans.labels),
        EXPECTED_CLUSTER_SIZES,
    )

    np.testing.assert_allclose(
        result.kmeans.silhouette,
        EXPECTED_SILHOUETTE,
        rtol=0,
        atol=1e-12,
    )

    np.testing.assert_allclose(
        result.decoded_centroids.decoded_centers,
        EXPECTED_CONTINUOUS_CENTROIDS,
        rtol=0,
        atol=1e-8,
    )

    np.testing.assert_array_equal(
        result.centroid_presentation.rounded_centers,
        EXPECTED_ROUNDED_CENTROIDS,
    )

    for anchor, expected in zip(
        result.temporal_anchors,
        EXPECTED_CLUSTER_COMPOSITION,
    ):

        assert anchor.cluster_id == expected["cluster_id"]

        assert anchor.n_positive == expected["positive"]

        assert anchor.n_negative == expected["negative"]

        assert anchor.n_members == expected["total"]

test_afghanistan_clustering_regression()