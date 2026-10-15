"""Population and earthquake-subset integration for Framework B+C."""

from dataclasses import dataclass

import numpy as np

from src.statistical_clustering.population_anomaly import (
    PopulationAnomalyResult,
    compute_population_anomaly_probability,
)
from src.statistical_clustering.earthquake_samples import (
    EarthquakeSampleResult,
    select_earthquake_samples,
)
from src.statistical_clustering.earthquake_subset import (
    EarthquakeSubsetResult,
    compute_earthquake_subset_anomalies,
)

from .historical_input_adapter import HistoricalDailyTECResult


@dataclass(frozen=True)
class StatisticalAnalysisResult:
    """Historical population and earthquake-subset results."""

    population: PopulationAnomalyResult
    earthquake_samples: EarthquakeSampleResult
    earthquake_subset: EarthquakeSubsetResult
    n_events: int


def run_statistical_analysis(
    historical: HistoricalDailyTECResult,
    event_dates,
    magnitudes,
    *,
    minimum_magnitude: float = 6.0,
    observation_days: int = 30,
    reference_days: int = 15,
    threshold_multiplier: float = 3.0,
) -> StatisticalAnalysisResult:
    """Run the validated population and earthquake-subset analyses."""

    if not isinstance(historical, HistoricalDailyTECResult):
        raise TypeError(
            "historical must be a HistoricalDailyTECResult."
        )

    if type(observation_days) is not int or observation_days < 0:
        raise ValueError(
            "observation_days must be a non-negative integer."
        )

    if type(reference_days) is not int or reference_days <= 0:
        raise ValueError(
            "reference_days must be a positive integer."
        )

    if not np.isfinite(minimum_magnitude) or minimum_magnitude < 0:
        raise ValueError(
            "minimum_magnitude must be finite and non-negative."
        )

    if not np.isfinite(threshold_multiplier) or threshold_multiplier < 0:
        raise ValueError(
            "threshold_multiplier must be finite and non-negative."
        )

    daily_tec = np.asarray(historical.daily_tec)

    if daily_tec.ndim != 2 or daily_tec.shape[1] != 24:
        raise ValueError(
            "Historical TEC must have shape (n_days, 24)."
        )

    expected_days = (
        historical.end_date - historical.start_date
    ).days + 1

    if daily_tec.shape[0] != expected_days:
        raise ValueError(
            "Historical TEC does not match its calendar date range."
        )

    if not np.all(np.isfinite(daily_tec)):
        raise ValueError(
            "Historical TEC must contain only finite values."
        )

    if expected_days <= reference_days:
        raise ValueError(
            "Historical TEC must exceed the reference period."
        )

    # 1. Historical background anomaly probabilities.
    population = compute_population_anomaly_probability(
        tec=daily_tec,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
    )

    # 2. Select eligible earthquake events.
    samples = select_earthquake_samples(
        event_dates=np.asarray(event_dates, dtype=object),
        magnitudes=np.asarray(magnitudes),
        analysis_start=historical.start_date,
        analysis_end=historical.end_date,
        minimum_magnitude=minimum_magnitude,
        observation_days=observation_days,
        reference_days=reference_days,
    )

    n_events = len(samples.selected_dates)

    if n_events == 0:
        raise ValueError(
            "No eligible earthquake events were selected."
        )

    # 3. Compute event-centered anomaly counts.
    subset = compute_earthquake_subset_anomalies(
        tec=daily_tec,
        start_date=historical.start_date,
        earthquake_dates=samples.selected_dates,
        observation_days=observation_days,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
    )

    return StatisticalAnalysisResult(
        population=population,
        earthquake_samples=samples,
        earthquake_subset=subset,
        n_events=n_events,
    )
