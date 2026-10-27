"""End-to-end synthetic integration tests for Framework B+C."""

from datetime import date, datetime, timedelta

import numpy as np

from src.workflow.historical_input_adapter import (
    prepare_historical_daily_tec,
)
from src.workflow.statistical_analysis_adapter import (
    run_statistical_analysis,
)
from src.workflow.statistical_significance_adapter import (
    run_statistical_significance,
)
from src.workflow.clustering_adapter import (
    run_clustering_workflow,
)


N_DAYS = 400
START = datetime(2022, 1, 1)

EVENT_INDICES = [70, 160, 250, 340]

POSITIVE_DAY = -8
POSITIVE_HOUR = 4

NEGATIVE_DAY = -22
NEGATIVE_HOUR = 16


def make_synthetic_historical_data():
    """Build deterministic hourly TEC with injected anomalies."""

    daily = np.full((N_DAYS, 24), 10.0, dtype=float)

    # Small, deterministic background variation.
    for day in range(N_DAYS):
        daily[day, :] += (day % 7) * 0.1

    # Rare positive/negative background anomalies.
    # These ensure both null probabilities are nonzero.
    for day in range(20, N_DAYS):
        if day % 37 == 0:
            daily[day, 9] += 4.0

        if day % 41 == 0:
            daily[day, 19] -= 4.0

    # Event-related anomalies at fixed relative days/hours.
    for event_index in EVENT_INDICES:
        daily[
            event_index + POSITIVE_DAY,
            POSITIVE_HOUR,
        ] += 10.0

        daily[
            event_index + NEGATIVE_DAY,
            NEGATIVE_HOUR,
        ] -= 10.0

        # Day 0 belongs to the pre-event calendar-day selection. Post-event
        # signals must remain in B diagnostics without entering C.
        daily[event_index, 21] += 10.0
        daily[event_index + 8, 6] += 10.0
        daily[event_index + 22, 18] -= 10.0

    epochs = np.asarray(
        [
            START + timedelta(hours=i)
            for i in range(N_DAYS * 24)
        ],
        dtype=object,
    )

    event_dates = np.asarray(
        [
            (START + timedelta(days=i)).date()
            for i in EVENT_INDICES
        ],
        dtype=object,
    )

    magnitudes = np.asarray(
        [6.1, 6.3, 6.5, 6.7],
        dtype=float,
    )

    end_date = (
        START + timedelta(days=N_DAYS - 1)
    ).date()

    return epochs, daily.reshape(-1), event_dates, magnitudes, end_date


def run_full_workflow():
    """Execute the complete B+C workflow using public adapters."""

    (
        epochs,
        tec,
        event_dates,
        magnitudes,
        end_date,
    ) = make_synthetic_historical_data()

    historical = prepare_historical_daily_tec(
        epochs=epochs,
        tec=tec,
        start_date=date(2022, 1, 1),
        end_date=end_date,
        allow_interpolation=False,
    )

    analysis = run_statistical_analysis(
        historical=historical,
        event_dates=event_dates,
        magnitudes=magnitudes,
        minimum_magnitude=6.0,
        observation_days=30,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    significance = run_statistical_significance(
        analysis=analysis,
        critical_z=1.96,
    )

    clustering = run_clustering_workflow(
        significance=significance,
        n_clusters=2,
        random_state=42,
    )

    return historical, analysis, significance, clustering


def test_full_workflow_contract():
    historical, analysis, significance, clustering = (
        run_full_workflow()
    )

    assert historical.daily_tec.shape == (N_DAYS, 24)
    assert historical.n_days == N_DAYS

    assert analysis.n_events == 4

    assert analysis.earthquake_subset.positive_counts.shape == (
        61, 24
    )

    assert analysis.earthquake_subset.negative_counts.shape == (
        61, 24
    )

    assert significance.significance_mask.shape == (61, 24)
    np.testing.assert_array_equal(significance.relative_days, np.arange(-30, 31))
    np.testing.assert_array_equal(clustering.clustering_relative_days, np.arange(-30, 1))
    np.testing.assert_array_equal(clustering.clustering_mask, significance.significance_mask[:31])
    assert clustering.significance is significance

    assert clustering.n_clusters == 2
    assert clustering.n_significant_cells >= 2

    assert len(clustering.clustering.temporal_anchors) == 2


def test_post_event_and_day_zero_signals_across_real_scientific_stages():
    _, analysis, significance, clustering = run_full_workflow()
    assert significance.significance_mask[30, 21] == 1  # Day 0.
    assert significance.significance_mask[38, 6] == 1  # Day +8.
    assert significance.significance_mask[52, 18] == -1  # Day +22.

    features = clustering.clustering.clustering_features.raw_features
    expected = {
        (hour, row - 30, int(significance.significance_mask[row, hour]))
        for row, hour in np.argwhere(significance.significance_mask[:31] != 0)
    }
    assert {tuple(cell) for cell in features} == expected
    assert (21, 0, 1) in expected
    assert np.all(features[:, 1] <= 0)

    # C must not mutate any full-window B array, including z-score and overlap
    # diagnostics. Re-run C on the same objects and compare byte-for-byte values.
    objects = (analysis.earthquake_subset, significance, significance.z_test)
    snapshots = [
        {name: value.copy() for name, value in vars(obj).items()
         if isinstance(value, np.ndarray)}
        for obj in objects
    ]
    run_clustering_workflow(significance, observation_days=30)
    for obj, snapshot in zip(objects, snapshots):
        for name, original in snapshot.items():
            np.testing.assert_array_equal(getattr(obj, name), original)


def test_population_probabilities():
    _, analysis, _, _ = run_full_workflow()

    population = analysis.population

    assert 0 < population.positive_probability < 1
    assert 0 < population.negative_probability < 1

    assert population.valid_sample_count == (
        (N_DAYS - 15) * 24
    )


def test_injected_anomaly_significance():
    _, analysis, significance, _ = run_full_workflow()

    relative_days = analysis.earthquake_subset.relative_days

    positive_index = int(
        np.where(relative_days == POSITIVE_DAY)[0][0]
    )

    negative_index = int(
        np.where(relative_days == NEGATIVE_DAY)[0][0]
    )

    # All four earthquakes contain the injected anomalies.
    assert (
        analysis.earthquake_subset.positive_counts[
            positive_index, POSITIVE_HOUR
        ]
        == 4
    )

    assert (
        analysis.earthquake_subset.negative_counts[
            negative_index, NEGATIVE_HOUR
        ]
        == 4
    )

    assert significance.significance_mask[
        positive_index, POSITIVE_HOUR
    ] == 1

    assert significance.significance_mask[
        negative_index, NEGATIVE_HOUR
    ] == -1

    assert significance.z_test.positive_z[
        positive_index, POSITIVE_HOUR
    ] > 1.96

    assert significance.z_test.negative_z[
        negative_index, NEGATIVE_HOUR
    ] > 1.96


def test_clustering_reproducibility():
    _, _, first_significance, first = run_full_workflow()

    _, _, second_significance, second = run_full_workflow()

    np.testing.assert_array_equal(
        first_significance.significance_mask,
        second_significance.significance_mask,
    )

    np.testing.assert_array_equal(
        first.clustering.kmeans.labels,
        second.clustering.kmeans.labels,
    )

    np.testing.assert_allclose(
        first.clustering.decoded_centroids.decoded_centers,
        second.clustering.decoded_centroids.decoded_centers,
    )

    assert (
        first.clustering.temporal_anchors
        == second.clustering.temporal_anchors
    )
