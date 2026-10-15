"""Z-test and significance-mask integration for Framework B+C."""

from dataclasses import dataclass

import numpy as np

from src.statistical_clustering.z_test import (
    OneProportionZTestResult,
    one_proportion_z_test,
    generate_significance_mask,
)

from .statistical_analysis_adapter import StatisticalAnalysisResult


@dataclass(frozen=True)
class StatisticalSignificanceResult:
    """Statistical significance outputs and overlap diagnostics."""

    z_test: OneProportionZTestResult
    significance_mask: np.ndarray
    relative_days: np.ndarray

    positive_significant: np.ndarray
    negative_significant: np.ndarray
    overlap_mask: np.ndarray
    overlap_count: int

    critical_z: float
    n_events: int


def run_statistical_significance(
    analysis: StatisticalAnalysisResult,
    *,
    critical_z: float = 1.96,
) -> StatisticalSignificanceResult:
    """Compute legacy-compatible statistical significance results."""

    if not isinstance(analysis, StatisticalAnalysisResult):
        raise TypeError(
            "analysis must be a StatisticalAnalysisResult."
        )

    if (
        not np.isscalar(critical_z)
        or not isinstance(critical_z, (int, float, np.number))
        or isinstance(critical_z, (bool, np.bool_))
        or not np.isfinite(critical_z)
        or critical_z < 0
    ):
        raise ValueError(
            "critical_z must be finite and non-negative."
        )

    if type(analysis.n_events) is not int or analysis.n_events <= 0:
        raise ValueError("n_events must be a positive integer.")

    population = analysis.population
    subset = analysis.earthquake_subset

    positive_p0 = population.positive_probability
    negative_p0 = population.negative_probability

    if not (
        np.isfinite(positive_p0)
        and 0.0 < positive_p0 < 1.0
    ):
        raise ValueError(
            "Positive population probability must be between 0 and 1."
        )

    if not (
        np.isfinite(negative_p0)
        and 0.0 < negative_p0 < 1.0
    ):
        raise ValueError(
            "Negative population probability must be between 0 and 1."
        )

    positive_counts = np.asarray(subset.positive_counts)
    negative_counts = np.asarray(subset.negative_counts)
    relative_days = np.asarray(subset.relative_days)

    if (
        positive_counts.ndim != 2
        or positive_counts.shape != negative_counts.shape
    ):
        raise ValueError(
            "Positive and negative counts must have matching 2D shapes."
        )

    if (
        relative_days.ndim != 1
        or len(relative_days) != positive_counts.shape[0]
    ):
        raise ValueError(
            "relative_days must match the anomaly count rows."
        )

    if not (
        np.all(np.isfinite(positive_counts))
        and np.all(np.isfinite(negative_counts))
    ):
        raise ValueError("Anomaly counts must be finite.")

    if not (
        np.all(positive_counts == np.floor(positive_counts))
        and np.all(negative_counts == np.floor(negative_counts))
    ):
        raise ValueError("Anomaly counts must be integers.")

    if (
        np.any(positive_counts < 0)
        or np.any(negative_counts < 0)
        or np.any(positive_counts > analysis.n_events)
        or np.any(negative_counts > analysis.n_events)
    ):
        raise ValueError(
            "Anomaly counts must be between 0 and n_events."
        )

    # 1. Reuse the validated scientific z-test.
    z_test = one_proportion_z_test(
        positive_counts=positive_counts,
        negative_counts=negative_counts,
        n_events=analysis.n_events,
        positive_null_proportion=positive_p0,
        negative_null_proportion=negative_p0,
    )

    # 2. Reuse the validated legacy significance encoding.
    mask = generate_significance_mask(
        positive_z=z_test.positive_z,
        negative_z=z_test.negative_z,
        critical_z=float(critical_z),
    )

    # 3. Preserve significance overlap diagnostics.
    positive_significant = z_test.positive_z > critical_z
    negative_significant = z_test.negative_z > critical_z

    overlap_mask = (
        positive_significant & negative_significant
    )

    return StatisticalSignificanceResult(
        z_test=z_test,
        significance_mask=mask,
        relative_days=relative_days.copy(),
        positive_significant=positive_significant,
        negative_significant=negative_significant,
        overlap_mask=overlap_mask,
        overlap_count=int(np.count_nonzero(overlap_mask)),
        critical_z=float(critical_z),
        n_events=analysis.n_events,
    )
