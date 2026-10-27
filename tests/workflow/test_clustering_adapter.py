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
    run_statistical_clustering,
)

from src.workflow.statistical_significance_adapter import (
    StatisticalSignificanceResult,
)
from src.workflow.clustering_adapter import (
    run_clustering_workflow,
    select_pre_event_clustering_window,
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


def make_full_significance(observation_days=30, *, include_post_event=True):
    positive_counts = np.zeros((2 * observation_days + 1, 24), dtype=int)
    negative_counts = np.zeros_like(positive_counts)
    positive_counts[0, 3:5] = 30  # Earliest permitted pre-event day.
    positive_counts[observation_days // 2, 5:7] = 30
    negative_counts[observation_days - 1, 15:17] = 30
    negative_counts[observation_days, 17:19] = 30  # Day 0, including 18 UTC.
    if include_post_event:
        positive_counts[observation_days + 1, 0] = 30
        negative_counts[-1, 23] = 30
    z_test = one_proportion_z_test(positive_counts, negative_counts, 100, 0.1, 0.1)
    positive = z_test.positive_z > 1.96
    negative = z_test.negative_z > 1.96
    return StatisticalSignificanceResult(
        z_test=z_test,
        significance_mask=generate_significance_mask(
            z_test.positive_z, z_test.negative_z, 1.96,
        ),
        relative_days=np.arange(-observation_days, observation_days + 1),
        positive_significant=positive,
        negative_significant=negative,
        overlap_mask=positive & negative,
        overlap_count=int(np.count_nonzero(positive & negative)),
        critical_z=1.96,
        n_events=100,
    )


@pytest.mark.parametrize("observation_days", [2, 30])
def test_c_receives_only_complete_pre_event_window(monkeypatch, observation_days):
    import src.workflow.clustering_adapter as module

    significance = make_full_significance(observation_days)
    original = significance.significance_mask.copy()
    expected_days = np.arange(-observation_days, 1)
    expected_mask = original[:observation_days + 1]
    received = []

    def checked_pipeline(**kwargs):
        # Inspect the actual boundary before entering the unchanged C core.
        np.testing.assert_array_equal(kwargs["relative_days"], expected_days)
        np.testing.assert_array_equal(kwargs["mask"], expected_mask)
        received.append(kwargs)
        return run_statistical_clustering(**kwargs)

    monkeypatch.setattr(module, "run_statistical_clustering", checked_pipeline)
    result = run_clustering_workflow(significance, observation_days=observation_days)

    assert len(received) == 1
    assert result.significance is significance
    np.testing.assert_array_equal(significance.significance_mask, original)
    np.testing.assert_array_equal(result.clustering_relative_days, expected_days)
    np.testing.assert_array_equal(result.clustering_mask, expected_mask)
    assert result.clustering_mask.shape == (observation_days + 1, 24)
    assert result.n_significant_cells == 8
    assert np.count_nonzero(original[observation_days + 1:]) == 2
    assert not np.shares_memory(result.clustering_mask, original)
    assert not np.shares_memory(result.clustering_mask, significance.significance_mask)

    # Every pre-event significant cell survives with its original hour/polarity.
    expected_cells = {
        (hour, int(expected_days[row]), int(expected_mask[row, hour]))
        for row, hour in np.argwhere(expected_mask != 0)
    }
    actual_cells = {
        tuple(cell) for cell in result.clustering.clustering_features.raw_features
    }
    assert actual_cells == expected_cells
    assert (18, 0, -1) in actual_cells

    # Call the unmodified Legacy preprocessing on this synthetic full mask.
    from validation.legacy.statistical_clustering.OneSampleTest_and_KMeans_5 import (
        data_preprocessing,
    )

    legacy_mask, legacy_features = data_preprocessing(original, observation_days)
    np.testing.assert_array_equal(result.clustering_mask[::-1], legacy_mask)
    np.testing.assert_array_equal(
        result.clustering.clustering_features.raw_features, legacy_features,
    )


def test_post_event_cells_do_not_change_clustering_or_determinism():
    first = run_clustering_workflow(make_full_significance(), random_state=42)
    second = run_clustering_workflow(
        make_full_significance(include_post_event=False), random_state=42,
    )
    third = run_clustering_workflow(make_full_significance(), random_state=42)
    for other in (second, third):
        np.testing.assert_array_equal(
            first.clustering.kmeans.labels, other.clustering.kmeans.labels,
        )
        np.testing.assert_array_equal(
            first.clustering.decoded_centroids.decoded_centers,
            other.clustering.decoded_centroids.decoded_centers,
        )
        assert first.clustering.temporal_anchors == other.clustering.temporal_anchors


def test_only_post_event_significance_is_insufficient_for_clustering():
    significance = make_full_significance()
    mask = significance.significance_mask.copy()
    mask[:31] = 0
    with pytest.raises(ValueError, match="Not enough"):
        run_clustering_workflow(replace(significance, significance_mask=mask))


@pytest.mark.parametrize("days", [
    [], [-4, -3, -2, -1], [1, 2, 3, 4, 5], [-4, -3, -2, -1, 0, 1],
    [-4, -3, -2, 0, 1], [-2, -1, -1, 0, 1], [0, -1, -2],
    [-2, -1, 0.5], [-2, -1, np.nan], [-2, -1, np.inf],
    [-2 + 0j, -1 + 0j, 0j], [False, True], ["-2", "-1", "0"],
])
def test_invalid_or_incomplete_day_axes_fail_explicitly(days):
    with pytest.raises(ValueError, match="relative_days"):
        select_pre_event_clustering_window(np.zeros((len(days), 24)), np.array(days))


@pytest.mark.parametrize("observation_days", [-1, True, 2.5, 3])
def test_invalid_or_inconsistent_observation_days(observation_days):
    with pytest.raises(ValueError, match="observation_days"):
        run_clustering_workflow(
            make_full_significance(2), observation_days=observation_days,
        )


def test_two_dimensional_day_axis_is_rejected():
    with pytest.raises(ValueError, match="relative_days"):
        select_pre_event_clustering_window(np.zeros((3, 24)), np.array([[-2, -1, 0]]))


def test_zero_observation_days_keeps_day_zero():
    mask = np.ones((1, 24), dtype=np.int8)
    selected_mask, days = select_pre_event_clustering_window(
        mask, np.array([0]), observation_days=0,
    )
    np.testing.assert_array_equal(selected_mask, mask)
    np.testing.assert_array_equal(days, [0])
