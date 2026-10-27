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
    """Full significance diagnostics and the selected pre-event C input.

    significance retains the original B result, including post-event rows.
    clustering_mask is a copied (observation_days + 1, 24) mask with -1/0/+1
    codes; clustering_relative_days is its copied row axis, -observation_days
    through 0 inclusive. Day 0 is the earthquake's UTC calendar date.
    n_significant_cells counts only nonzero cells in clustering_mask, not
    the full significance mask (or overlapping polarity tests separately).

    The two selected-input fields are required when constructing this result
    manually. Prefer run_clustering_workflow(), which selects and validates
    them. Existing attributes remain available; consumers must no longer
    equate n_significant_cells with the full-window B count.
    """

    significance: StatisticalSignificanceResult
    clustering: StatisticalClusteringResult

    n_significant_cells: int
    n_clusters: int
    random_state: int

    clustering_mask: np.ndarray
    clustering_relative_days: np.ndarray


def select_pre_event_clustering_window(
    mask: np.ndarray,
    relative_days: np.ndarray,
    *,
    observation_days: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Copy Day -observation_days..0 without changing B's diagnostics.

    Accept a complete symmetric B axis or an already selected pre-event
    axis. If omitted, observation_days is inferred from the first day.
    Day 0 is the earthquake's UTC calendar date, as in Legacy.
    """

    mask = np.asarray(mask)
    relative_days = np.asarray(relative_days)

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
        not (
            np.issubdtype(relative_days.dtype, np.integer)
            or np.issubdtype(relative_days.dtype, np.floating)
        )
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

    if relative_days.size == 0 or relative_days[0] > 0:
        raise ValueError("relative_days must include Day 0 and the pre-event range.")

    if observation_days is None:
        observation_days = -int(relative_days[0])
    if type(observation_days) is not int or observation_days < 0:
        raise ValueError("observation_days must be a non-negative integer.")

    if (
        relative_days[0] != -observation_days
        or relative_days[-1] not in (0, observation_days)
    ):
        raise ValueError(
            "relative_days must span -observation_days..0 or "
            "-observation_days..+observation_days, including Day 0."
        )

    selected = (relative_days >= -observation_days) & (relative_days <= 0)
    return mask[selected].copy(), relative_days[selected].copy()


def run_clustering_workflow(
    significance: StatisticalSignificanceResult,
    *,
    n_clusters: int = 2,
    random_state: int = 42,
    observation_days: int | None = None,
) -> StatisticalClusteringWorkflowResult:
    """Cluster only pre-event cells; preserve full B significance results.

    The validated C pipeline receives Day -observation_days..0 inclusive.
    Existing callers with a complete pre-event axis remain supported.
    """
    if not isinstance(significance, StatisticalSignificanceResult):
        raise TypeError("significance must be a StatisticalSignificanceResult.")
    if type(n_clusters) is not int or n_clusters < 2:
        raise ValueError("n_clusters must be an integer >= 2.")
    if type(random_state) is not int or random_state < 0:
        raise ValueError("random_state must be a non-negative integer.")

    mask, relative_days = select_pre_event_clustering_window(
        significance.significance_mask,
        significance.relative_days,
        observation_days=observation_days,
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
        clustering_mask=mask,
        clustering_relative_days=relative_days,
    )
