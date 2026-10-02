"""Integrated statistical-clustering pipeline."""

from dataclasses import dataclass

import numpy as np

from .clustering import (
    ClusteringFeatures,
    prepare_clustering_features,
)

from .feature_scaling import (
    ScaledClusteringFeatures,
    standardize_clustering_features,
)

from .kmeans_clustering import (
    KMeansClusteringResult,
    apply_kmeans_clustering,
)

from .centroid_decoding import (
    DecodedCentroids,
    decode_cluster_centroids,
)

from .temporal_anchors import (
    TemporalAnchor,
    extract_temporal_anchors,
)

from .centroid_presentation import (
    PresentedCentroids,
    prepare_centroid_presentation,
)


@dataclass(frozen=True)
class StatisticalClusteringResult:
    """Outputs from the complete clustering pipeline."""

    clustering_features: ClusteringFeatures

    scaled_features: ScaledClusteringFeatures

    kmeans: KMeansClusteringResult

    decoded_centroids: DecodedCentroids

    temporal_anchors: tuple[TemporalAnchor, ...]

    centroid_presentation: PresentedCentroids


def run_statistical_clustering(
    mask: np.ndarray,
    relative_days: np.ndarray,
    n_clusters: int = 2,
    random_state: int = 42,
) -> StatisticalClusteringResult:
    """Run the validated circular-hour clustering pipeline.

    Parameters
    ----------
    mask:
        Two-dimensional significance mask containing -1, 0, +1.

    relative_days:
        Relative day coordinate corresponding to each mask row.

    n_clusters:
        Number of K-Means clusters.

    random_state:
        Random state used by K-Means.
    """

    # C1: Feature preparation
    clustering_features = (
        prepare_clustering_features(
            mask=mask,
            relative_days=relative_days,
            use_circular_hour=True,
        )
    )

    # C2: Feature standardization
    scaled_features = (
        standardize_clustering_features(
            clustering_features.features
        )
    )

    # C3: K-Means
    kmeans = apply_kmeans_clustering(
        standardized_features=(
            scaled_features.standardized_features
        ),
        n_clusters=n_clusters,
        random_state=random_state,
    )

    # C4: Centroid decoding
    decoded_centroids = decode_cluster_centroids(
        standardized_centers=kmeans.centers,
        scaler=scaled_features.scaler,
    )

    # C5: Temporal anchor extraction
    temporal_anchors = extract_temporal_anchors(
        decoded_centers=(
            decoded_centroids.decoded_centers
        ),
        labels=kmeans.labels,
        raw_features=clustering_features.raw_features,
    )

    # C6: Paper-compatible presentation
    centroid_presentation = (
        prepare_centroid_presentation(
            decoded_centroids.decoded_centers
        )
    )

    return StatisticalClusteringResult(
        clustering_features=clustering_features,
        scaled_features=scaled_features,
        kmeans=kmeans,
        decoded_centroids=decoded_centroids,
        temporal_anchors=temporal_anchors,
        centroid_presentation=centroid_presentation,
    )