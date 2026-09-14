"""Temporal TEC anomaly detection based on a quartile reference model.

This module implements the core temporal anomaly detection method used to
compare an observed TEC value with the distribution of TEC values measured
at the same time of day during preceding reference days.

The module performs scientific computation only. Data acquisition,
location-to-grid conversion, visualization, and case-specific configuration
are intentionally handled elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class TemporalAnomalyResult:
    """Container for temporal TEC anomaly detection results.

    Arrays correspond to the analysis epochs after the initial reference
    period. Anomaly codes are +1 for positive anomalies, 0 for normal or
    unclassified observations, and -1 for negative anomalies.
    """

    epochs: np.ndarray
    observed: np.ndarray

    q1: np.ndarray
    median: np.ndarray
    q3: np.ndarray

    upper_bound: np.ndarray
    lower_bound: np.ndarray

    anomaly: np.ndarray

    reference_days: int
    threshold_multiplier: float
    min_reference_samples: int


def _validate_inputs(
    tec: np.ndarray,
    epochs: Sequence[datetime],
    reference_days: int,
    threshold_multiplier: float,
    min_reference_samples: int | None,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Validate and normalize inputs."""

    tec = np.asarray(tec, dtype=np.float64)
    epochs = np.asarray(epochs, dtype=object)

    if tec.ndim != 1:
        raise ValueError("tec must be a one-dimensional time series.")

    if epochs.ndim != 1:
        raise ValueError("epochs must be one-dimensional.")

    if len(tec) != len(epochs):
        raise ValueError(
            "tec and epochs must contain the same number of elements."
        )

    if len(tec) == 0:
        raise ValueError("tec and epochs must not be empty.")

    if reference_days <= 0:
        raise ValueError("reference_days must be greater than zero.")

    if threshold_multiplier < 0:
        raise ValueError(
            "threshold_multiplier must be greater than or equal to zero."
        )

    if not np.isfinite(threshold_multiplier):
        raise ValueError("threshold_multiplier must be finite.")

    if not all(isinstance(epoch, datetime) for epoch in epochs):
        raise TypeError("All epochs must be datetime objects.")

    if len(set(epochs)) != len(epochs):
        raise ValueError("epochs must not contain duplicate timestamps.")

    if any(
        epochs[i] >= epochs[i + 1]
        for i in range(len(epochs) - 1)
    ):
        raise ValueError(
            "epochs must be strictly increasing."
        )

    if min_reference_samples is None:
        min_reference_samples = reference_days

    if not 1 <= min_reference_samples <= reference_days:
        raise ValueError(
            "min_reference_samples must be between 1 and reference_days."
        )

    return tec, epochs, min_reference_samples


def detect_temporal_anomalies(
    tec: np.ndarray,
    epochs: Sequence[datetime],
    *,
    reference_days: int = 15,
    threshold_multiplier: float = 3.0,
    min_reference_samples: int | None = None,
) -> TemporalAnomalyResult:
    """Detect positive and negative TEC anomalies.

    For each analysis epoch, reference TEC values are collected from the
    same time of day during the preceding ``reference_days`` calendar days.

    Quartile statistics are calculated from the valid reference values:

        UB = Q2 + k * (Q3 - Q2)
        LB = Q2 - k * (Q2 - Q1)

    where Q1, Q2, and Q3 are the 25th, 50th, and 75th percentiles,
    respectively, and ``k`` is ``threshold_multiplier``.

    Anomalies are classified as:

        +1 : observed TEC > upper bound
         0 : observed TEC is within the bounds
        -1 : observed TEC < lower bound

    If insufficient valid reference values are available, the statistical
    quantities are returned as NaN and the anomaly code is 0.

    Parameters
    ----------
    tec
        One-dimensional TEC time series.
    epochs
        UTC datetime corresponding to each TEC observation.
    reference_days
        Number of preceding calendar days used as the reference period.
    threshold_multiplier
        Multiplier applied to the upper and lower quartile deviations.
    min_reference_samples
        Minimum number of valid reference values required to calculate
        the anomaly bounds. If None, all reference days are required.

    Returns
    -------
    TemporalAnomalyResult
        Temporal anomaly statistics and classifications for epochs having
        a complete calendar reference period.
    """

    tec, epochs, min_reference_samples = _validate_inputs(
        tec=tec,
        epochs=epochs,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
        min_reference_samples=min_reference_samples,
    )

    value_by_epoch = {
        epoch: value
        for epoch, value in zip(epochs, tec)
    }

    first_epoch = epochs[0]
    analysis_start = first_epoch + timedelta(days=reference_days)

    analysis_mask = np.array(
        [epoch >= analysis_start for epoch in epochs],
        dtype=bool,
    )

    analysis_epochs = epochs[analysis_mask]
    observed = tec[analysis_mask]

    n = len(analysis_epochs)

    q1 = np.full(n, np.nan, dtype=np.float64)
    median = np.full(n, np.nan, dtype=np.float64)
    q3 = np.full(n, np.nan, dtype=np.float64)

    upper_bound = np.full(n, np.nan, dtype=np.float64)
    lower_bound = np.full(n, np.nan, dtype=np.float64)

    anomaly = np.zeros(n, dtype=np.int8)

    for i, (epoch, obs) in enumerate(
        zip(analysis_epochs, observed)
    ):
        reference_values = np.array(
            [
                value_by_epoch.get(
                    epoch - timedelta(days=day),
                    np.nan,
                )
                for day in range(1, reference_days + 1)
            ],
            dtype=np.float64,
        )

        valid_reference = reference_values[
            np.isfinite(reference_values)
        ]

        if len(valid_reference) < min_reference_samples:
            continue

        q1_i, median_i, q3_i = np.percentile(
            valid_reference,
            [25, 50, 75],
        )

        q1[i] = q1_i
        median[i] = median_i
        q3[i] = q3_i

        upper_bound[i] = (
            median_i
            + threshold_multiplier * (q3_i - median_i)
        )

        lower_bound[i] = (
            median_i
            - threshold_multiplier * (median_i - q1_i)
        )

        if not np.isfinite(obs):
            continue

        if obs > upper_bound[i]:
            anomaly[i] = 1
        elif obs < lower_bound[i]:
            anomaly[i] = -1

    return TemporalAnomalyResult(
        epochs=analysis_epochs,
        observed=observed,
        q1=q1,
        median=median,
        q3=q3,
        upper_bound=upper_bound,
        lower_bound=lower_bound,
        anomaly=anomaly,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
        min_reference_samples=min_reference_samples,
    )