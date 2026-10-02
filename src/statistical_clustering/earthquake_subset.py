"""TEC anomaly statistics around earthquake events."""

from dataclasses import dataclass
from datetime import date, datetime

import numpy as np


@dataclass(frozen=True)
class EarthquakeSubsetResult:
    """TEC anomaly results for an earthquake subset."""

    positive_counts: np.ndarray
    negative_counts: np.ndarray
    delta_tec: np.ndarray
    relative_days: np.ndarray

    earthquake_dates: np.ndarray
    observation_days: int
    reference_days: int
    threshold_multiplier: float


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    raise TypeError(
        "Dates must be datetime.date or datetime.datetime objects."
    )


def compute_earthquake_subset_anomalies(
    tec: np.ndarray,
    start_date,
    earthquake_dates: np.ndarray,
    observation_days: int = 30,
    reference_days: int = 15,
    threshold_multiplier: float = 3.0,
) -> EarthquakeSubsetResult:
    """Compute TEC anomaly counts around earthquake events.

    Each target day from -observation_days through
    +observation_days is evaluated using the preceding
    reference_days at the same hour.
    """

    tec = np.asarray(
        tec,
        dtype=np.float64,
    )

    earthquake_dates = np.asarray(
        earthquake_dates,
        dtype=object,
    )

    if tec.ndim != 2:
        raise ValueError(
            "tec must have shape (n_days, n_hours)."
        )

    if earthquake_dates.ndim != 1:
        raise ValueError(
            "earthquake_dates must be one-dimensional."
        )

    if len(earthquake_dates) == 0:
        raise ValueError(
            "At least one earthquake is required."
        )

    if observation_days < 0:
        raise ValueError(
            "observation_days must be non-negative."
        )

    if reference_days <= 0:
        raise ValueError(
            "reference_days must be positive."
        )

    if threshold_multiplier < 0:
        raise ValueError(
            "threshold_multiplier must be non-negative."
        )

    start_date = _to_date(
        start_date
    )

    earthquake_dates = np.asarray(
        [
            _to_date(value)
            for value in earthquake_dates
        ],
        dtype=object,
    )

    n_days, n_hours = tec.shape
    n_events = len(earthquake_dates)

    n_relative_days = (
        2 * observation_days + 1
    )

    relative_days = np.arange(
        -observation_days,
        observation_days + 1,
        dtype=int,
    )

    delta_tec = np.empty(
        (
            n_relative_days,
            n_hours,
            n_events,
        ),
        dtype=np.float64,
    )

    positive_events = np.zeros(
        (
            n_relative_days,
            n_hours,
            n_events,
        ),
        dtype=bool,
    )

    negative_events = np.zeros_like(
        positive_events
    )

    for event_index, event_date in enumerate(
        earthquake_dates
    ):

        event_day_index = (
            event_date - start_date
        ).days

        first_target_index = (
            event_day_index
            - observation_days
        )

        first_reference_index = (
            first_target_index
            - reference_days
        )

        last_target_index = (
            event_day_index
            + observation_days
        )

        if first_reference_index < 0:
            raise ValueError(
                f"Earthquake {event_date} does not have "
                "sufficient preceding reference data."
            )

        if last_target_index >= n_days:
            raise ValueError(
                f"Earthquake {event_date} does not have "
                "sufficient following observation data."
            )

        event_window = tec[
            first_reference_index:
            last_target_index + 1,
            :
        ]

        for relative_index in range(
            n_relative_days
        ):

            reference_start = (
                relative_index
            )

            reference_end = (
                reference_start
                + reference_days
            )

            target_index = (
                reference_end
            )

            reference = event_window[
                reference_start:
                reference_end,
                :
            ]

            observed = event_window[
                target_index,
                :
            ]

            q1 = np.percentile(
                reference,
                25,
                axis=0,
            )

            median = np.percentile(
                reference,
                50,
                axis=0,
            )

            q3 = np.percentile(
                reference,
                75,
                axis=0,
            )

            upper_bound = (
                median
                + threshold_multiplier
                * (q3 - median)
            )

            lower_bound = (
                median
                - threshold_multiplier
                * (median - q1)
            )

            delta_tec[
                relative_index,
                :,
                event_index,
            ] = (
                observed - median
            )

            positive_events[
                relative_index,
                :,
                event_index,
            ] = (
                observed > upper_bound
            )

            negative_events[
                relative_index,
                :,
                event_index,
            ] = (
                observed < lower_bound
            )

    positive_counts = np.sum(
        positive_events,
        axis=2,
    )

    negative_counts = np.sum(
        negative_events,
        axis=2,
    )

    return EarthquakeSubsetResult(
        positive_counts=positive_counts,
        negative_counts=negative_counts,
        delta_tec=delta_tec,
        relative_days=relative_days,
        earthquake_dates=earthquake_dates,
        observation_days=observation_days,
        reference_days=reference_days,
        threshold_multiplier=threshold_multiplier,
    )