"""Paper-compatible presentation of decoded cluster centroids."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PresentedCentroids:
    """Continuous and rounded centroid coordinates."""

    continuous_centers: np.ndarray
    rounded_centers: np.ndarray


def prepare_centroid_presentation(
    decoded_centers: np.ndarray,
) -> PresentedCentroids:
    """Prepare centroid coordinates for paper-style presentation.

    Input columns:
        [decoded hour, continuous day, continuous polarity]

    Output:
        continuous_centers: original coordinates
        rounded_centers: [hour, rounded day, rounded polarity]

    Rounding follows NumPy's np.round convention.
    """

    centers = np.asarray(
        decoded_centers,
        dtype=np.float64,
    )

    if centers.ndim != 2 or centers.shape[1] != 3:
        raise ValueError(
            "decoded_centers must have shape (k, 3)."
        )

    if centers.shape[0] == 0:
        raise ValueError(
            "decoded_centers must contain at least one center."
        )

    if not np.all(np.isfinite(centers)):
        raise ValueError(
            "decoded_centers must contain finite values."
        )

    rounded_centers = centers.copy()

    rounded_centers[:, 1] = np.round(
        centers[:, 1]
    )

    rounded_centers[:, 2] = np.round(
        centers[:, 2]
    )

    return PresentedCentroids(
        continuous_centers=centers.copy(),
        rounded_centers=rounded_centers,
    )