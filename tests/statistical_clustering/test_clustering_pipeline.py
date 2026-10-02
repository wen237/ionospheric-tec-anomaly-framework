import numpy as np
import pytest

from src.statistical_clustering.pipeline import (
    run_statistical_clustering,
)


def make_synthetic_mask():

    mask = np.zeros(
        (6, 24),
        dtype=np.int8,
    )

    # Positive significant cells
    mask[0, 6] = 1
    mask[0, 7] = 1
    mask[1, 8] = 1
    mask[1, 9] = 1

    # Negative significant cells
    mask[4, 16] = -1
    mask[4, 17] = -1
    mask[5, 18] = -1
    mask[5, 19] = -1

    relative_days = np.asarray(
        [-5, -4, -3, -2, -1, 0],
    )

    return mask, relative_days


def test_pipeline_runs_end_to_end():

    mask, relative_days = make_synthetic_mask()

    result = run_statistical_clustering(
        mask=mask,
        relative_days=relative_days,
    )

    assert result.clustering_features.raw_features.shape == (
        8,
        3,
    )

    assert result.clustering_features.features.shape == (
        8,
        4,
    )

    assert result.scaled_features.standardized_features.shape == (
        8,
        4,
    )

    assert result.kmeans.labels.shape == (8,)

    assert result.kmeans.centers.shape == (2, 4)

    assert result.decoded_centroids.decoded_centers.shape == (
        2,
        3,
    )

    assert len(result.temporal_anchors) == 2

    assert result.centroid_presentation.rounded_centers.shape == (
        2,
        3,
    )


from src.statistical_clustering.clustering import (
    prepare_clustering_features,
)

from src.statistical_clustering.feature_scaling import (
    standardize_clustering_features,
)

from src.statistical_clustering.kmeans_clustering import (
    apply_kmeans_clustering,
)

from src.statistical_clustering.centroid_decoding import (
    decode_cluster_centroids,
)

from src.statistical_clustering.temporal_anchors import (
    extract_temporal_anchors,
)

from src.statistical_clustering.centroid_presentation import (
    prepare_centroid_presentation,
)


def test_pipeline_matches_individual_modules():

    mask, relative_days = make_synthetic_mask()

    # Execute individual modules.
    features = prepare_clustering_features(
        mask,
        relative_days,
        use_circular_hour=True,
    )

    scaled = standardize_clustering_features(
        features.features
    )

    kmeans = apply_kmeans_clustering(
        scaled.standardized_features,
        n_clusters=2,
        random_state=42,
    )

    decoded = decode_cluster_centroids(
        kmeans.centers,
        scaled.scaler,
    )

    anchors = extract_temporal_anchors(
        decoded.decoded_centers,
        kmeans.labels,
        features.raw_features,
    )

    presentation = prepare_centroid_presentation(
        decoded.decoded_centers
    )

    # Execute integrated pipeline.
    result = run_statistical_clustering(
        mask,
        relative_days,
        n_clusters=2,
        random_state=42,
    )

    np.testing.assert_array_equal(
        result.clustering_features.raw_features,
        features.raw_features,
    )

    np.testing.assert_array_equal(
        result.clustering_features.features,
        features.features,
    )

    np.testing.assert_array_equal(
        result.scaled_features.standardized_features,
        scaled.standardized_features,
    )

    np.testing.assert_array_equal(
        result.kmeans.labels,
        kmeans.labels,
    )

    np.testing.assert_array_equal(
        result.kmeans.centers,
        kmeans.centers,
    )

    assert result.kmeans.silhouette == kmeans.silhouette

    np.testing.assert_array_equal(
        result.decoded_centroids.decoded_centers,
        decoded.decoded_centers,
    )

    assert result.temporal_anchors == anchors

    np.testing.assert_array_equal(
        result.centroid_presentation.rounded_centers,
        presentation.rounded_centers,
    )


def test_pipeline_passes_kmeans_parameters():

    mask, relative_days = make_synthetic_mask()

    result = run_statistical_clustering(
        mask=mask,
        relative_days=relative_days,
        n_clusters=3,
        random_state=7,
    )

    assert result.kmeans.n_clusters == 3

    assert result.kmeans.random_state == 7

    assert result.kmeans.centers.shape == (3, 4)

    assert len(result.temporal_anchors) == 3

