"""K-Means clustering for significant TEC anomaly features."""

from dataclasses import dataclass

import numpy as np

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


@dataclass(frozen=True)
class KMeansClusteringResult:
    """Results of K-Means clustering in standardized feature space."""

    labels: np.ndarray
    centers: np.ndarray
    silhouette: float
    inertia: float
    n_clusters: int
    random_state: int


def apply_kmeans_clustering(
    standardized_features: np.ndarray,
    n_clusters: int = 2,
    random_state: int = 42,
) -> KMeansClusteringResult:
    """Cluster standardized features using the legacy K-Means settings.

    The input must already be standardized. This function does not
    perform feature construction or standardization.
    """

    X = np.asarray(
        standardized_features,
        dtype=np.float64,
    )

    if X.ndim != 2:
        raise ValueError(
            "standardized_features must be two-dimensional."
        )

    if X.shape[1] != 4:
        raise ValueError(
            "Expected four standardized features: "
            "[sin_hour, cos_hour, day, polarity]."
        )

    if not np.all(np.isfinite(X)):
        raise ValueError(
            "standardized_features must contain only finite values."
        )

    if not isinstance(n_clusters, (int, np.integer)):
        raise ValueError(
            "n_clusters must be an integer."
        )

    if n_clusters < 2:
        raise ValueError(
            "n_clusters must be at least 2."
        )

    if X.shape[0] <= n_clusters:
        raise ValueError(
            "The number of observations must exceed n_clusters "
            "to calculate the silhouette score."
        )

    model = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
    )

    labels = model.fit_predict(X)

    centers = model.cluster_centers_

    silhouette = silhouette_score(
        X,
        labels,
    )

    return KMeansClusteringResult(
        labels=labels,
        centers=centers,
        silhouette=float(silhouette),
        inertia=float(model.inertia_),
        n_clusters=n_clusters,
        random_state=random_state,
    )