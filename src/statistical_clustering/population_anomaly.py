from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PopulationAnomalyResult:
    """Background anomaly statistics for historical TEC."""

    positive_count: int
    negative_count: int
    valid_sample_count: int

    positive_probability: float
    negative_probability: float

    reference_days: int
    threshold_multiplier: float


def compute_population_anomaly_probability(
    tec: np.ndarray,
    reference_days: int = 15,
    threshold_multiplier: float = 3.0,
) -> PopulationAnomalyResult:
    """Compute historical background TEC anomaly probabilities.

    Parameters
    ----------
    tec
        Two-dimensional TEC array with shape
        (n_days, n_hours).

    reference_days
        Number of preceding days used to construct
        the quartile reference distribution.

    threshold_multiplier
        Multiplier applied to the upper and lower
        quartile distances from the median.
    """

    tec = np.asarray(
        tec,
        dtype=np.float64,
    )

    if tec.ndim != 2:
        raise ValueError(
            "tec must have shape (n_days, n_hours)."
        )

    n_days, n_hours = tec.shape

    if reference_days <= 0:
        raise ValueError(
            "reference_days must be positive."
        )

    if n_days <= reference_days:
        raise ValueError(
            "TEC must contain more days than reference_days."
        )

    if threshold_multiplier < 0:
        raise ValueError(
            "threshold_multiplier must be non-negative."
        )

    positive_count = 0
    negative_count = 0
    valid_sample_count = 0

    for day_index in range(
        reference_days,
        n_days,
    ):

        reference = tec[
            day_index - reference_days:
            day_index,
            :
        ]

        observed = tec[
            day_index,
            :
        ]

        q1 = np.percentile(
            reference,
            25,
            axis=0,
        )

        median = np.percentile(
            reference,
            50,
            axis=0,
        )

        q3 = np.percentile(
            reference,
            75,
            axis=0,
        )

        upper_bound = (
            median
            + threshold_multiplier
            * (q3 - median)
        )

        lower_bound = (
            median
            - threshold_multiplier
            * (median - q1)
        )

        positive = (
            observed > upper_bound
        )

        negative = (
            observed < lower_bound
        )

        positive_count += int(
            np.sum(positive)
        )

        negative_count += int(
            np.sum(negative)
        )

        valid_sample_count += n_hours

    positive_probability = (
        positive_count
        / valid_sample_count
    )

    negative_probability = (
        negative_count
        / valid_sample_count
    )

    return PopulationAnomalyResult(
        positive_count=positive_count,
        negative_count=negative_count,
        valid_sample_count=valid_sample_count,
        positive_probability=positive_probability,
        negative_probability=negative_probability,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
    )