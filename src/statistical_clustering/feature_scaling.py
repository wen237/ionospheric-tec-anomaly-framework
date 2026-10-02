"""Feature standardization for TEC anomaly clustering."""

from dataclasses import dataclass

import numpy as np

from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class ScaledClusteringFeatures:
    """Standardized clustering features and their fitted scaler."""

    features: np.ndarray
    standardized_features: np.ndarray
    scaler: StandardScaler


def standardize_clustering_features(
    features: np.ndarray,
) -> ScaledClusteringFeatures:
    """Standardize clustering features using StandardScaler.

    The scaler is fitted on the complete feature matrix, following
    the accepted-paper legacy implementation.
    """

    features = np.asarray(
        features,
        dtype=np.float64,
    )

    if features.ndim != 2:
        raise ValueError(
            "features must be a two-dimensional array."
        )

    if features.shape[1] != 4:
        raise ValueError(
            "features must have four columns: "
            "[sin_hour, cos_hour, day, polarity]."
        )

    if features.shape[0] == 0:
        raise ValueError(
            "features must contain at least one observation."
        )

    if not np.all(np.isfinite(features)):
        raise ValueError(
            "features must contain only finite values."
        )

    scaler = StandardScaler()

    standardized_features = (
        scaler.fit_transform(features)
    )

    return ScaledClusteringFeatures(
        features=features,
        standardized_features=standardized_features,
        scaler=scaler,
    )