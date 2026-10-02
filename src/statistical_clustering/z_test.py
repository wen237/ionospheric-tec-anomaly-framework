"""One-proportion z-test for earthquake-related TEC anomalies."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OneProportionZTestResult:
    """Results of positive and negative one-proportion z-tests."""

    positive_proportion: np.ndarray
    negative_proportion: np.ndarray

    positive_z: np.ndarray
    negative_z: np.ndarray

    positive_null_proportion: float
    negative_null_proportion: float

    n_events: int


def one_proportion_z_test(
    positive_counts: np.ndarray,
    negative_counts: np.ndarray,
    n_events: int,
    positive_null_proportion: float,
    negative_null_proportion: float,
) -> OneProportionZTestResult:
    """Compute one-proportion z statistics for TEC anomaly counts."""

    positive_counts = np.asarray(
        positive_counts,
        dtype=np.float64,
    )

    negative_counts = np.asarray(
        negative_counts,
        dtype=np.float64,
    )

    if positive_counts.shape != negative_counts.shape:
        raise ValueError(
            "positive_counts and negative_counts "
            "must have the same shape."
        )

    if positive_counts.ndim != 2:
        raise ValueError(
            "Anomaly counts must be two-dimensional."
        )

    if n_events <= 0:
        raise ValueError(
            "n_events must be positive."
        )

    if np.any(
        positive_counts < 0
    ) or np.any(
        negative_counts < 0
    ):
        raise ValueError(
            "Anomaly counts cannot be negative."
        )

    if np.any(
        positive_counts > n_events
    ) or np.any(
        negative_counts > n_events
    ):
        raise ValueError(
            "Anomaly counts cannot exceed n_events."
        )

    if not (
        0.0
        < positive_null_proportion
        < 1.0
    ):
        raise ValueError(
            "positive_null_proportion "
            "must be between 0 and 1."
        )

    if not (
        0.0
        < negative_null_proportion
        < 1.0
    ):
        raise ValueError(
            "negative_null_proportion "
            "must be between 0 and 1."
        )

    positive_proportion = (
        positive_counts
        / n_events
    )

    negative_proportion = (
        negative_counts
        / n_events
    )

    positive_standard_error = np.sqrt(
        positive_null_proportion
        * (
            1.0
            - positive_null_proportion
        )
        / n_events
    )

    negative_standard_error = np.sqrt(
        negative_null_proportion
        * (
            1.0
            - negative_null_proportion
        )
        / n_events
    )

    positive_z = (
        positive_proportion
        - positive_null_proportion
    ) / positive_standard_error

    negative_z = (
        negative_proportion
        - negative_null_proportion
    ) / negative_standard_error

    return OneProportionZTestResult(
        positive_proportion=positive_proportion,
        negative_proportion=negative_proportion,
        positive_z=positive_z,
        negative_z=negative_z,
        positive_null_proportion=float(
            positive_null_proportion
        ),
        negative_null_proportion=float(
            negative_null_proportion
        ),
        n_events=n_events,
    )


def generate_significance_mask(
    positive_z: np.ndarray,
    negative_z: np.ndarray,
    critical_z: float = 1.96,
) -> np.ndarray:
    """Generate the legacy-compatible significance mask.

    Positive significance is encoded as +1, negative significance
    as -1, and non-significance as 0.

    If both positive and negative tests are significant at the same
    cell, the legacy encoding sums +1 and -1 to 0. Users requiring
    overlap information should inspect the positive and negative
    z-score arrays separately.
    """

    positive_z = np.asarray(
        positive_z,
        dtype=np.float64,
    )

    negative_z = np.asarray(
        negative_z,
        dtype=np.float64,
    )

    if positive_z.shape != negative_z.shape:
        raise ValueError(
            "positive_z and negative_z "
            "must have the same shape."
        )

    if critical_z < 0:
        raise ValueError(
            "critical_z must be non-negative."
        )

    positive_significant = (
        positive_z > critical_z
    )

    negative_significant = (
        negative_z > critical_z
    )

    mask = (
        positive_significant.astype(
            np.int8
        )
        - negative_significant.astype(
            np.int8
        )
    )

    return mask