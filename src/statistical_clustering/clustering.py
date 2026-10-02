"""Feature preparation for clustering significant TEC anomaly cells."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ClusteringFeatures:
    """Significant TEC anomaly cells and their clustering features."""

    hours: np.ndarray
    relative_days: np.ndarray
    polarities: np.ndarray
    raw_features: np.ndarray
    features: np.ndarray
    use_circular_hour: bool


def encode_hour_sin_cos(
    hours: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Encode UT hours using circular sine-cosine coordinates."""

    hours = np.asarray(
        hours,
        dtype=np.float64,
    )

    angles = (
        2.0
        * np.pi
        * hours
        / 24.0
    )

    return (
        np.sin(angles),
        np.cos(angles),
    )


def prepare_clustering_features(
    mask: np.ndarray,
    relative_days: np.ndarray,
    use_circular_hour: bool = True,
) -> ClusteringFeatures:
    """Extract significant cells and construct clustering features.

    Significant positive cells are placed before significant negative
    cells to preserve the ordering used by the legacy implementation.
    """

    mask = np.asarray(mask)
    relative_days = np.asarray(relative_days)

    if mask.ndim != 2:
        raise ValueError(
            "mask must be two-dimensional."
        )

    if relative_days.ndim != 1:
        raise ValueError(
            "relative_days must be one-dimensional."
        )

    if mask.shape[0] != relative_days.size:
        raise ValueError(
            "The number of mask rows must match "
            "the number of relative days."
        )

    if not np.all(
        np.isin(mask, [-1, 0, 1])
    ):
        raise ValueError(
            "mask may contain only -1, 0, and 1."
        )

    # Reproduce the legacy day ordering:
    # Day 0, Day -1, ..., Day -observation_days.
    order = np.argsort(
        relative_days
    )[::-1]

    ordered_mask = mask[
        order,
        :
    ]

    ordered_days = relative_days[
        order
    ]

    # Legacy ordering:
    # all positive cells first, then all negative cells.
    positive_rows, positive_hours = np.where(
        ordered_mask == 1
    )

    negative_rows, negative_hours = np.where(
        ordered_mask == -1
    )

    hours = np.concatenate(
        (
            positive_hours,
            negative_hours,
        )
    ).astype(np.int64)

    days = np.concatenate(
        (
            ordered_days[positive_rows],
            ordered_days[negative_rows],
        )
    ).astype(np.int64)

    polarities = np.concatenate(
        (
            np.ones(
                positive_rows.size,
                dtype=np.int8,
            ),
            -np.ones(
                negative_rows.size,
                dtype=np.int8,
            ),
        )
    )

    raw_features = np.column_stack(
        (
            hours,
            days,
            polarities,
        )
    ).astype(np.float64)

    if use_circular_hour:

        sin_hour, cos_hour = (
            encode_hour_sin_cos(hours)
        )

        features = np.column_stack(
            (
                sin_hour,
                cos_hour,
                days,
                polarities,
            )
        )

    else:

        features = raw_features.copy()

    return ClusteringFeatures(
        hours=hours,
        relative_days=days,
        polarities=polarities,
        raw_features=raw_features,
        features=np.asarray(
            features,
            dtype=np.float64,
        ),
        use_circular_hour=use_circular_hour,
    )