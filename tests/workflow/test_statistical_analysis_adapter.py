"""Tests for population and earthquake-subset workflow integration."""

from datetime import date, datetime, timedelta

import numpy as np
import pytest

from src.workflow.historical_input_adapter import (
    prepare_historical_daily_tec,
)
from src.workflow.statistical_analysis_adapter import (
    run_statistical_analysis,
)


def make_historical():
    start = datetime(2022, 1, 1)
    n_days = 100
    n_hours = n_days * 24

    epochs = np.asarray(
        [start + timedelta(hours=i) for i in range(n_hours)],
        dtype=object,
    )

    # Deterministic daily TEC variation.
    daily = np.full((n_days, 24), 10.0)

    for day in range(n_days):
        daily[day, :] += (day % 7) * 0.1

    return prepare_historical_daily_tec(
        epochs,
        daily.reshape(-1),
        start_date=date(2022, 1, 1),
        end_date=date(2022, 4, 10),
    )


def test_statistical_analysis_integration():
    historical = make_historical()

    result = run_statistical_analysis(
        historical=historical,
        event_dates=np.asarray(
            [
                date(2022, 2, 20),
                date(2022, 3, 10),
                date(2022, 3, 20),
            ],
            dtype=object,
        ),
        magnitudes=np.asarray([6.2, 5.5, 6.5]),
        minimum_magnitude=6.0,
        observation_days=10,
        reference_days=5,
        threshold_multiplier=3.0,
    )

    assert result.n_events == 2

    assert len(
        result.earthquake_samples.selected_dates
    ) == 2

    assert result.earthquake_subset.positive_counts.shape == (
        21, 24
    )

    assert result.earthquake_subset.negative_counts.shape == (
        21, 24
    )

    assert result.earthquake_subset.delta_tec.shape == (
        21, 24, 2
    )

    np.testing.assert_array_equal(
        result.earthquake_subset.relative_days,
        np.arange(-10, 11),
    )

    assert result.population.valid_sample_count == (
        (100 - 5) * 24
    )

    assert result.population.reference_days == 5
    assert result.earthquake_subset.reference_days == 5

    assert result.population.threshold_multiplier == 3.0
    assert result.earthquake_subset.threshold_multiplier == 3.0


def test_no_eligible_earthquakes():
    historical = make_historical()

    with pytest.raises(ValueError, match="No eligible"):
        run_statistical_analysis(
            historical,
            event_dates=[date(2022, 2, 20)],
            magnitudes=[5.0],
            observation_days=10,
            reference_days=5,
        )


def test_reject_invalid_historical_type():
    with pytest.raises(TypeError, match="HistoricalDailyTECResult"):
        run_statistical_analysis(
            historical=np.ones((100, 24)),
            event_dates=[date(2022, 2, 20)],
            magnitudes=[6.5],
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("observation_days", -1),
        ("observation_days", 1.5),
        ("reference_days", 0),
        ("reference_days", 2.5),
        ("minimum_magnitude", -1.0),
        ("minimum_magnitude", np.nan),
        ("threshold_multiplier", -1.0),
        ("threshold_multiplier", np.inf),
    ],
)
def test_reject_invalid_parameters(field, value):
    historical = make_historical()

    options = {
        "observation_days": 10,
        "reference_days": 5,
        "minimum_magnitude": 6.0,
        "threshold_multiplier": 3.0,
    }

    options[field] = value

    with pytest.raises(ValueError):
        run_statistical_analysis(
            historical,
            event_dates=[date(2022, 2, 20)],
            magnitudes=[6.5],
            **options,
        )


def test_reject_nonfinite_historical_tec():
    historical = make_historical()

    historical.daily_tec[0, 0] = np.nan

    with pytest.raises(ValueError, match="finite"):
        run_statistical_analysis(
            historical,
            event_dates=[date(2022, 2, 20)],
            magnitudes=[6.5],
            observation_days=10,
            reference_days=5,
        )
