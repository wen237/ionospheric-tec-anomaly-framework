"""Clustering integration for the Framework B+C workflow."""

from dataclasses import dataclass

import numpy as np

from src.statistical_clustering.pipeline import (
    StatisticalClusteringResult,
    run_statistical_clustering,
)

from .statistical_significance_adapter import (
    StatisticalSignificanceResult,
)


@dataclass(frozen=True)
class StatisticalClusteringWorkflowResult:
    """Combined significance and clustering workflow outputs."""

    significance: StatisticalSignificanceResult
    clustering: StatisticalClusteringResult

    n_significant_cells: int
    n_clusters: int
    random_state: int


def run_clustering_workflow(
    significance: StatisticalSignificanceResult,
    *,
    n_clusters: int = 2,
    random_state: int = 42,
) -> StatisticalClusteringWorkflowResult:
    """Cluster statistically significant TEC anomaly cells.

    Reuses the validated Framework C clustering pipeline.
    Significance overlap information remains available through
    the original StatisticalSignificanceResult.
    """

    if not isinstance(significance, StatisticalSignificanceResult):
        raise TypeError(
            "significance must be a StatisticalSignificanceResult."
        )

    if type(n_clusters) is not int or n_clusters < 2:
        raise ValueError(
            "n_clusters must be an integer >= 2."
        )

    if type(random_state) is not int or random_state < 0:
        raise ValueError(
            "random_state must be a non-negative integer."
        )

    mask = np.asarray(significance.significance_mask)
    relative_days = np.asarray(significance.relative_days)

    if mask.ndim != 2:
        raise ValueError(
            "Significance mask must be two-dimensional."
        )

    if mask.shape[1] != 24:
        raise ValueError(
            "Significance mask must contain 24 UT hours."
        )

    if (
        relative_days.ndim != 1
        or len(relative_days) != mask.shape[0]
    ):
        raise ValueError(
            "relative_days must match the significance mask rows."
        )

    if not np.all(np.isin(mask, [-1, 0, 1])):
        raise ValueError(
            "Significance mask must contain only -1, 0, +1."
        )

    if (
        not np.issubdtype(relative_days.dtype, np.number)
        or not np.all(np.isfinite(relative_days))
        or not np.all(relative_days == np.floor(relative_days))
    ):
        raise ValueError(
            "relative_days must contain finite integers."
        )

    if (
        len(relative_days) > 1
        and not np.all(np.diff(relative_days) == 1)
    ):
        raise ValueError(
            "relative_days must be consecutive and increasing."
        )

    n_significant_cells = int(
        np.count_nonzero(mask)
    )

    if n_significant_cells < n_clusters:
        raise ValueError(
            "Not enough significant cells for the requested "
            "number of clusters."
        )

    # Delegate all scientific clustering operations
    # to the validated Framework C pipeline.
    clustering = run_statistical_clustering(
        mask=mask,
        relative_days=relative_days,
        n_clusters=n_clusters,
        random_state=random_state,
    )

    return StatisticalClusteringWorkflowResult(
        significance=significance,
        clustering=clustering,
        n_significant_cells=n_significant_cells,
        n_clusters=n_clusters,
        random_state=random_state,
    )
