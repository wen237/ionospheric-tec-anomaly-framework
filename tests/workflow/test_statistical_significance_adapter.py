"""Tests for the Framework B+C significance adapter."""

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from src.statistical_clustering.population_anomaly import (
    PopulationAnomalyResult,
)
from src.statistical_clustering.earthquake_samples import (
    EarthquakeSampleResult,
)
from src.statistical_clustering.earthquake_subset import (
    EarthquakeSubsetResult,
)

from src.workflow.statistical_analysis_adapter import (
    StatisticalAnalysisResult,
)
from src.workflow.statistical_significance_adapter import (
    run_statistical_significance,
)


def make_analysis(
    positive_counts=None,
    negative_counts=None,
    positive_p0=0.1,
    negative_p0=0.1,
    n_events=100,
):
    if positive_counts is None:
        positive_counts = np.array(
            [[30, 5, 30, 5]],
            dtype=int,
        )

    if negative_counts is None:
        negative_counts = np.array(
            [[5, 30, 30, 5]],
            dtype=int,
        )

    relative_days = np.array([-3], dtype=int)

    population = PopulationAnomalyResult(
        positive_count=10,
        negative_count=10,
        valid_sample_count=100,
        positive_probability=positive_p0,
        negative_probability=negative_p0,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    samples = EarthquakeSampleResult(
        event_dates=np.array([date(2022, 1, 1)], dtype=object),
        magnitudes=np.array([6.5]),
        selected_mask=np.array([True]),
        selected_dates=np.array([date(2022, 1, 1)], dtype=object),
        selected_magnitudes=np.array([6.5]),
        analysis_start=date(2021, 1, 1),
        analysis_end=date(2023, 1, 1),
        minimum_magnitude=6.0,
        observation_days=3,
        reference_days=15,
    )

    subset = EarthquakeSubsetResult(
        positive_counts=np.asarray(positive_counts),
        negative_counts=np.asarray(negative_counts),
        delta_tec=np.zeros((1, 4, 1)),
        relative_days=relative_days,
        earthquake_dates=samples.selected_dates,
        observation_days=3,
        reference_days=15,
        threshold_multiplier=3.0,
    )

    return StatisticalAnalysisResult(
        population=population,
        earthquake_samples=samples,
        earthquake_subset=subset,
        n_events=n_events,
    )


def test_significance_and_overlap():
    analysis = make_analysis()

    result = run_statistical_significance(analysis)

    np.testing.assert_array_equal(
        result.significance_mask,
        np.array([[1, -1, 0, 0]], dtype=np.int8),
    )

    np.testing.assert_array_equal(
        result.overlap_mask,
        np.array([[False, False, True, False]]),
    )

    assert result.overlap_count == 1
    assert result.n_events == 100
    assert result.critical_z == 1.96

    np.testing.assert_array_equal(
        result.relative_days,
        np.array([-3]),
    )

    assert result.z_test.positive_z[0, 0] > 1.96
    assert result.z_test.negative_z[0, 1] > 1.96


def test_zero_overlap():
    analysis = make_analysis(
        positive_counts=np.array([[30, 5]]),
        negative_counts=np.array([[5, 30]]),
    )

    result = run_statistical_significance(analysis)

    assert result.overlap_count == 0
    assert not np.any(result.overlap_mask)


@pytest.mark.parametrize(
    "critical_z",
    [-1.0, np.nan, np.inf, "1.96", True],
)
def test_reject_invalid_critical_z(critical_z):
    with pytest.raises(ValueError, match="critical_z"):
        run_statistical_significance(
            make_analysis(),
            critical_z=critical_z,
        )


@pytest.mark.parametrize(
    "positive_p0,negative_p0",
    [
        (0.0, 0.1),
        (1.0, 0.1),
        (0.1, 0.0),
        (0.1, 1.0),
        (np.nan, 0.1),
        (0.1, np.inf),
    ],
)
def test_reject_invalid_population_probability(
    positive_p0,
    negative_p0,
):
    analysis = make_analysis(
        positive_p0=positive_p0,
        negative_p0=negative_p0,
    )

    with pytest.raises(ValueError, match="probability"):
        run_statistical_significance(analysis)


def test_reject_invalid_analysis_type():
    with pytest.raises(TypeError, match="StatisticalAnalysisResult"):
        run_statistical_significance(None)


@pytest.mark.parametrize(
    "positive_counts,negative_counts",
    [
        (np.array([[-1, 0]]), np.array([[0, 0]])),
        (np.array([[101, 0]]), np.array([[0, 0]])),
        (np.array([[1.5, 0]]), np.array([[0, 0]])),
        (np.array([[np.nan, 0]]), np.array([[0, 0]])),
        (np.array([[np.inf, 0]]), np.array([[0, 0]])),
    ],
)
def test_reject_invalid_counts(
    positive_counts,
    negative_counts,
):
    analysis = make_analysis(
        positive_counts=positive_counts,
        negative_counts=negative_counts,
    )

    with pytest.raises(ValueError):
        run_statistical_significance(analysis)


def test_reject_invalid_relative_days():
    analysis = make_analysis()

    bad_subset = replace(
        analysis.earthquake_subset,
        relative_days=np.array([-3, -2]),
    )

    analysis = replace(
        analysis,
        earthquake_subset=bad_subset,
    )

    with pytest.raises(ValueError, match="relative_days"):
        run_statistical_significance(analysis)
