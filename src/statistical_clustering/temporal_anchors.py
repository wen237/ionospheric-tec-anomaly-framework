"""Temporal anchor points derived from decoded cluster centroids."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TemporalAnchor:
    """A temporal anchor derived from one clustering centroid."""

    cluster_id: int
    hour: int
    centroid_day: float
    rounded_day: int
    centroid_polarity: float
    dominant_polarity: int
    n_positive: int
    n_negative: int
    n_members: int


def extract_temporal_anchors(
    decoded_centers: np.ndarray,
    labels: np.ndarray,
    raw_features: np.ndarray,
) -> tuple[TemporalAnchor, ...]:
    """Extract temporal anchors and their cluster composition.

    decoded_centers columns:
        [decoded hour, continuous day, continuous polarity]

    raw_features columns:
        [hour, relative day, polarity]
    """

    centers = np.asarray(
        decoded_centers,
        dtype=np.float64,
    )

    labels = np.asarray(labels)

    raw = np.asarray(
        raw_features,
        dtype=np.float64,
    )

    if centers.ndim != 2 or centers.shape[1] != 3:
        raise ValueError(
            "decoded_centers must have shape (k, 3)."
        )

    if raw.ndim != 2 or raw.shape[1] != 3:
        raise ValueError(
            "raw_features must have shape (n, 3)."
        )

    if labels.ndim != 1 or labels.size != raw.shape[0]:
        raise ValueError(
            "labels must contain one entry per observation."
        )

    if not np.all(np.isfinite(centers)):
        raise ValueError(
            "decoded_centers must contain finite values."
        )

    if not np.all(np.isfinite(raw)):
        raise ValueError(
            "raw_features must contain finite values."
        )

    if not np.all(np.isin(raw[:, 2], [-1, 1])):
        raise ValueError(
            "raw feature polarities must be +1 or -1."
        )

    anchors = []

    for cluster_id, center in enumerate(centers):

        member_mask = labels == cluster_id

        n_members = int(np.count_nonzero(member_mask))

        if n_members == 0:
            raise ValueError(
                f"Cluster {cluster_id} has no members."
            )

        member_polarities = raw[member_mask, 2]

        n_positive = int(
            np.count_nonzero(member_polarities == 1)
        )

        n_negative = int(
            np.count_nonzero(member_polarities == -1)
        )

        centroid_polarity = float(center[2])

        # A tie has no uniquely dominant polarity.
        if n_positive > n_negative:
            dominant_polarity = 1
        elif n_negative > n_positive:
            dominant_polarity = -1
        else:
            dominant_polarity = 0

        anchors.append(
            TemporalAnchor(
                cluster_id=cluster_id,
                hour=int(center[0]),
                centroid_day=float(center[1]),
                rounded_day=int(np.round(center[1])),
                centroid_polarity=centroid_polarity,
                dominant_polarity=dominant_polarity,
                n_positive=n_positive,
                n_negative=n_negative,
                n_members=n_members,
            )
        )

    return tuple(anchors)