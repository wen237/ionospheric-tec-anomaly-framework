"""Earthquake sample selection for historical statistical analysis."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np


@dataclass(frozen=True)
class EarthquakeSampleResult:
    """Result of earthquake sample selection."""

    event_dates: np.ndarray
    magnitudes: np.ndarray
    selected_mask: np.ndarray
    selected_dates: np.ndarray
    selected_magnitudes: np.ndarray

    analysis_start: date
    analysis_end: date
    minimum_magnitude: float
    observation_days: int
    reference_days: int


def _to_date(value):
    """Convert a date-like value to a calendar date."""

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    raise TypeError(
        "Date values must be datetime.date or datetime.datetime objects."
    )


def select_earthquake_samples(
    event_dates: np.ndarray,
    magnitudes: np.ndarray,
    analysis_start,
    analysis_end,
    minimum_magnitude: float = 6.0,
    observation_days: int = 30,
    reference_days: int = 15,
) -> EarthquakeSampleResult:
    """Select earthquakes eligible for historical statistical analysis.

    An earthquake is retained when:

    1. magnitude >= minimum_magnitude;
    2. its date provides sufficient preceding data for both the
       observation and reference periods;
    3. its date provides sufficient following observation data.

    Selection is performed by calendar date, consistent with the
    day-based historical analysis.
    """

    event_dates = np.asarray(
        event_dates,
        dtype=object,
    )

    magnitudes = np.asarray(
        magnitudes,
        dtype=np.float64,
    )

    # ------------------------------------------------------
    # Input validation
    # ------------------------------------------------------

    if event_dates.ndim != 1:
        raise ValueError(
            "event_dates must be one-dimensional."
        )

    if magnitudes.ndim != 1:
        raise ValueError(
            "magnitudes must be one-dimensional."
        )

    if len(event_dates) != len(magnitudes):
        raise ValueError(
            "event_dates and magnitudes must have the same length."
        )

    if len(event_dates) == 0:
        raise ValueError(
            "At least one earthquake event is required."
        )

    if not np.all(np.isfinite(magnitudes)):
        raise ValueError(
            "magnitudes must contain only finite values."
        )

    if minimum_magnitude < 0:
        raise ValueError(
            "minimum_magnitude must be non-negative."
        )

    if observation_days < 0:
        raise ValueError(
            "observation_days must be non-negative."
        )

    if reference_days < 0:
        raise ValueError(
            "reference_days must be non-negative."
        )

    analysis_start = _to_date(
        analysis_start
    )

    analysis_end = _to_date(
        analysis_end
    )

    if analysis_start > analysis_end:
        raise ValueError(
            "analysis_start must not be later than analysis_end."
        )

    normalized_dates = np.asarray(
        [
            _to_date(value)
            for value in event_dates
        ],
        dtype=object,
    )

    # ------------------------------------------------------
    # Eligible date interval
    # ------------------------------------------------------

    earliest_event_date = (
        analysis_start
        + timedelta(
            days=(
                observation_days
                + reference_days
            )
        )
    )

    latest_event_date = (
        analysis_end
        - timedelta(
            days=observation_days
        )
    )

    # ------------------------------------------------------
    # Selection
    # ------------------------------------------------------

    magnitude_mask = (
        magnitudes
        >= minimum_magnitude
    )

    lower_date_mask = np.asarray(
        [
            event_date >= earliest_event_date
            for event_date in normalized_dates
        ],
        dtype=bool,
    )

    upper_date_mask = np.asarray(
        [
            event_date <= latest_event_date
            for event_date in normalized_dates
        ],
        dtype=bool,
    )

    selected_mask = (
        magnitude_mask
        & lower_date_mask
        & upper_date_mask
    )

    return EarthquakeSampleResult(
        event_dates=normalized_dates,
        magnitudes=magnitudes,
        selected_mask=selected_mask,
        selected_dates=normalized_dates[
            selected_mask
        ],
        selected_magnitudes=magnitudes[
            selected_mask
        ],
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        minimum_magnitude=float(
            minimum_magnitude
        ),
        observation_days=int(
            observation_days
        ),
        reference_days=int(
            reference_days
        ),
    )