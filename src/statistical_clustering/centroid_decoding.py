"""Decode K-Means centroids into physical feature coordinates."""

from dataclasses import dataclass

import numpy as np
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class DecodedCentroids:
    """Cluster centers in original and decoded feature spaces."""

    unscaled_centers: np.ndarray
    hours: np.ndarray
    relative_days: np.ndarray
    polarities: np.ndarray
    decoded_centers: np.ndarray


def decode_cluster_centroids(
    standardized_centers: np.ndarray,
    scaler: StandardScaler,
) -> DecodedCentroids:
    """Decode circular-hour K-Means centers using legacy conventions.

    Input columns:
        [standardized sin_hour,
         standardized cos_hour,
         standardized day,
         standardized polarity]

    Output columns:
        [rounded hour, continuous day, continuous polarity]
    """

    centers = np.asarray(
        standardized_centers,
        dtype=np.float64,
    )

    if centers.ndim != 2 or centers.shape[1] != 4:
        raise ValueError(
            "standardized_centers must have shape (k, 4)."
        )

    if centers.shape[0] == 0:
        raise ValueError(
            "standardized_centers must contain at least one center."
        )

    if not np.all(np.isfinite(centers)):
        raise ValueError(
            "standardized_centers must contain only finite values."
        )

    unscaled_centers = scaler.inverse_transform(
        centers
    )

    sin_hour = unscaled_centers[:, 0]
    cos_hour = unscaled_centers[:, 1]

    hours = np.round(
        np.mod(
            np.arctan2(sin_hour, cos_hour)
            * 24.0
            / (2.0 * np.pi),
            24.0,
        )
    ).astype(int)

    relative_days = unscaled_centers[:, 2].copy()
    polarities = unscaled_centers[:, 3].copy()

    decoded_centers = np.column_stack(
        (
            hours,
            relative_days,
            polarities,
        )
    )

    return DecodedCentroids(
        unscaled_centers=unscaled_centers,
        hours=hours,
        relative_days=relative_days,
        polarities=polarities,
        decoded_centers=decoded_centers,
    )