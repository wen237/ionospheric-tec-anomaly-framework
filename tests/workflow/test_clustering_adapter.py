"""Tests for Framework B+C clustering workflow integration."""

from dataclasses import replace

import numpy as np
import pytest

from src.statistical_clustering.z_test import (
    one_proportion_z_test,
    generate_significance_mask,
)
from src.statistical_clustering.pipeline import (
    StatisticalClusteringResult,
)

from src.workflow.statistical_significance_adapter import (
    StatisticalSignificanceResult,
)
from src.workflow.clustering_adapter import (
    run_clustering_workflow,
)


def make_significance():
    """Construct deterministic, statistically significant cells."""

    positive_counts = np.zeros((5, 24), dtype=int)
    negative_counts = np.zeros((5, 24), dtype=int)

    # Positive and negative events at different days/hours.
    positive_counts[0, 3] = 30
    positive_counts[0, 4] = 30
    positive_counts[1, 5] = 30
    positive_counts[1, 6] = 30

    negative_counts[3, 15] = 30
    negative_counts[3, 16] = 30
    negative_counts[4, 17] = 30
    negative_counts[4, 18] = 30

    z_test = one_proportion_z_test(
        positive_counts=positive_counts,
        negative_counts=negative_counts,
        n_events=100,
        positive_null_proportion=0.1,
        negative_null_proportion=0.1,
    )

    mask = generate_significance_mask(
        positive_z=z_test.positive_z,
        negative_z=z_test.negative_z,
        critical_z=1.96,
    )

    positive_significant = z_test.positive_z > 1.96
    negative_significant = z_test.negative_z > 1.96

    overlap_mask = (
        positive_significant & negative_significant
    )

    return StatisticalSignificanceResult(
        z_test=z_test,
        significance_mask=mask,
        relative_days=np.arange(-4, 1),
        positive_significant=positive_significant,
        negative_significant=negative_significant,
        overlap_mask=overlap_mask,
        overlap_count=int(np.count_nonzero(overlap_mask)),
        critical_z=1.96,
        n_events=100,
    )


def test_clustering_workflow_integration():
    significance = make_significance()

    result = run_clustering_workflow(significance)

    assert isinstance(
        result.clustering,
        StatisticalClusteringResult,
    )

    assert result.significance is significance
    assert result.n_significant_cells == 8
    assert result.n_clusters == 2
    assert result.random_state == 42

    assert len(result.clustering.temporal_anchors) == 2

    np.testing.assert_array_equal(
        result.significance.relative_days,
        np.arange(-4, 1),
    )


def test_clustering_reproducibility():
    significance = make_significance()

    first = run_clustering_workflow(
        significance,
        random_state=42,
    )

    second = run_clustering_workflow(
        significance,
        random_state=42,
    )

    np.testing.assert_array_equal(
        first.clustering.kmeans.labels,
        second.clustering.kmeans.labels,
    )

    np.testing.assert_allclose(
        first.clustering.decoded_centroids.decoded_centers,
        second.clustering.decoded_centroids.decoded_centers,
    )


def test_significance_metadata_preserved():
    significance = make_significance()

    result = run_clustering_workflow(significance)

    assert result.significance is significance
    assert result.significance.overlap_count == 0
    assert result.significance.n_events == 100


def test_reject_invalid_significance_type():
    with pytest.raises(
        TypeError,
        match="StatisticalSignificanceResult",
    ):
        run_clustering_workflow(None)


@pytest.mark.parametrize(
    "n_clusters",
    [0, 1, -1, 2.5, True],
)
def test_reject_invalid_n_clusters(n_clusters):
    with pytest.raises(ValueError, match="n_clusters"):
        run_clustering_workflow(
            make_significance(),
            n_clusters=n_clusters,
        )


@pytest.mark.parametrize(
    "random_state",
    [-1, 1.5, True],
)
def test_reject_invalid_random_state(random_state):
    with pytest.raises(ValueError, match="random_state"):
        run_clustering_workflow(
            make_significance(),
            random_state=random_state,
        )


def test_reject_insufficient_significant_cells():
    significance = make_significance()

    with pytest.raises(ValueError, match="Not enough"):
        run_clustering_workflow(
            significance,
            n_clusters=9,
        )


def test_reject_invalid_mask_shape():
    significance = make_significance()

    invalid = replace(
        significance,
        significance_mask=np.zeros((5, 12)),
    )

    with pytest.raises(ValueError, match="24 UT hours"):
        run_clustering_workflow(invalid)


def test_reject_invalid_mask_values():
    significance = make_significance()

    mask = significance.significance_mask.copy()
    mask[0, 0] = 2

    invalid = replace(
        significance,
        significance_mask=mask,
    )

    with pytest.raises(ValueError, match="only -1, 0,"):
        run_clustering_workflow(invalid)


def test_reject_invalid_relative_days():
    significance = make_significance()

    invalid = replace(
        significance,
        relative_days=np.array([-4, -3]),
    )

    with pytest.raises(ValueError, match="relative_days"):
        run_clustering_workflow(invalid)


def test_reject_nonconsecutive_relative_days():
    significance = make_significance()

    invalid = replace(
        significance,
        relative_days=np.array([-4, -3, -1, 0, 1]),
    )

    with pytest.raises(ValueError, match="consecutive"):
        run_clustering_workflow(invalid)
