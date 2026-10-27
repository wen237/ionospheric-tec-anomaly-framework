"""V2 JSON summary export with separate full-B and pre-event-C scopes.

V1 counted clustering cells over the full supplied significance mask.
V2 records the selected pre-event window and counts only its nonzero cells.
Preparation Manifest and Spatial Summary schema versions are independent.
"""

import json
import math
from pathlib import Path

import numpy as np

from .preparation_workflow import PreparationWorkflowRunResult
from .clustering_adapter import select_pre_event_clustering_window


SUMMARY_SCHEMA_VERSION = 2


def _json_scalar(value):
    """Convert a NumPy/Python scalar into a strict JSON scalar."""

    if isinstance(value, (bool, np.bool_)):
        return bool(value)

    if isinstance(value, (int, np.integer)):
        return int(value)

    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Summary contains a non-finite number.")
        return number

    if isinstance(value, str):
        return value

    if value is None:
        return None

    raise TypeError(
        f"Unsupported summary scalar: {type(value).__name__}"
    )


def _anchor_to_dict(anchor):
    """Serialize the validated Framework C temporal anchor."""

    fields = (
        "cluster_id",
        "hour",
        "centroid_day",
        "rounded_day",
        "centroid_polarity",
        "dominant_polarity",
        "n_positive",
        "n_negative",
        "n_members",
    )

    return {
        name: _json_scalar(getattr(anchor, name))
        for name in fields
    }


def build_clustering_summary(
    result: PreparationWorkflowRunResult,
) -> dict:
    """Build a JSON-compatible scientific summary."""

    if not isinstance(result, PreparationWorkflowRunResult):
        raise TypeError(
            "result must be a PreparationWorkflowRunResult."
        )

    config = result.preparation.config
    historical = result.historical
    analysis = result.statistical_analysis
    significance = result.statistical_significance
    workflow = result.clustering_workflow

    population = analysis.population
    samples = analysis.earthquake_samples
    subset = analysis.earthquake_subset

    mask = np.asarray(significance.significance_mask)
    positive = np.asarray(significance.positive_significant)
    negative = np.asarray(significance.negative_significant)
    overlap = np.asarray(significance.overlap_mask)

    if mask.ndim != 2 or mask.shape[1] != 24:
        raise ValueError("Invalid significance mask shape.")

    if not (
        positive.shape == mask.shape
        and negative.shape == mask.shape
        and overlap.shape == mask.shape
    ):
        raise ValueError("Significance diagnostic shapes differ.")

    if not np.all(np.isin(mask, (-1, 0, 1))):
        raise ValueError("Invalid significance mask values.")

    if not np.array_equal(overlap, positive & negative):
        raise ValueError("Inconsistent significance overlap mask.")

    if not np.array_equal(
        mask,
        positive.astype(np.int8) - negative.astype(np.int8),
    ):
        raise ValueError("Inconsistent significance mask encoding.")

    if int(significance.overlap_count) != int(
        np.count_nonzero(overlap)
    ):
        raise ValueError("Inconsistent overlap count.")

    clustering_mask, clustering_days = select_pre_event_clustering_window(
        mask, significance.relative_days,
        observation_days=samples.observation_days,
    )
    if not (
        np.array_equal(workflow.clustering_mask, clustering_mask)
        and np.array_equal(workflow.clustering_relative_days, clustering_days)
    ):
        raise ValueError("Inconsistent pre-event clustering window.")

    n_mask_cells = int(np.count_nonzero(clustering_mask))

    if workflow.n_significant_cells != n_mask_cells:
        raise ValueError("Inconsistent significant cell count.")

    if analysis.n_events != significance.n_events:
        raise ValueError("Inconsistent earthquake event counts.")

    if analysis.n_events != len(samples.selected_dates):
        raise ValueError("Inconsistent selected earthquake count.")

    if not np.array_equal(
        np.asarray(subset.relative_days),
        np.asarray(significance.relative_days),
    ):
        raise ValueError("Inconsistent relative days.")

    anchors = [
        _anchor_to_dict(anchor)
        for anchor in workflow.clustering.temporal_anchors
    ]

    anchors.sort(key=lambda item: item["cluster_id"])

    if len(anchors) != workflow.n_clusters:
        raise ValueError("Unexpected number of temporal anchors.")

    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "case_id": config.case_id,
        "historical_data": {
            "start_date": historical.start_date.isoformat(),
            "end_date": historical.end_date.isoformat(),
            "n_days": int(historical.n_days),
        },
        "population_baseline": {
            "positive_probability": _json_scalar(
                population.positive_probability
            ),
            "negative_probability": _json_scalar(
                population.negative_probability
            ),
            "valid_sample_count": int(
                population.valid_sample_count
            ),
            "reference_days": int(population.reference_days),
            "threshold_multiplier": _json_scalar(
                population.threshold_multiplier
            ),
        },
        "earthquake_selection": {
            "n_selected_events": int(analysis.n_events),
            "minimum_magnitude": _json_scalar(
                samples.minimum_magnitude
            ),
            "observation_days": int(samples.observation_days),
        },
        "statistical_significance": {
            "critical_z": _json_scalar(significance.critical_z),
            "positive_significant_count": int(
                np.count_nonzero(positive)
            ),
            "negative_significant_count": int(
                np.count_nonzero(negative)
            ),
            "overlap_count": int(np.count_nonzero(overlap)),
            "positive_mask_count": int(
                np.count_nonzero(mask == 1)
            ),
            "negative_mask_count": int(
                np.count_nonzero(mask == -1)
            ),
            "relative_day_start": int(
                significance.relative_days[0]
            ),
            "relative_day_end": int(
                significance.relative_days[-1]
            ),
        },
        "clustering": {
            "window_selection": "pre_event",
            "relative_day_start": int(clustering_days[0]),
            "relative_day_end": int(clustering_days[-1]),
            "n_clusters": int(workflow.n_clusters),
            "random_state": int(workflow.random_state),
            "n_significant_cells": n_mask_cells,
            "positive_mask_count": int(np.count_nonzero(clustering_mask == 1)),
            "negative_mask_count": int(np.count_nonzero(clustering_mask == -1)),
            "temporal_anchors": anchors,
        },
    }


def save_clustering_summary(
    result: PreparationWorkflowRunResult,
    output_path: Path,
) -> Path:
    """Save a scientific summary as strict UTF-8 JSON."""

    if not isinstance(output_path, Path):
        raise TypeError("output_path must be a Path.")

    summary = build_clustering_summary(result)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        file.write("\n")

    return output_path
