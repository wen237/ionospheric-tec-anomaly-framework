"""Historical TEC input preparation for Framework B+C."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import numpy as np

from src.statistical_clustering.historical_tec import (
    HourlyTECResult,
    interpolate_hourly_tec,
)


@dataclass(frozen=True)
class HistoricalDailyTECResult:
    """Calendar-aligned historical TEC and provenance metadata."""

    daily_tec: np.ndarray
    start_date: date
    end_date: date
    hourly_result: HourlyTECResult
    n_days: int


def prepare_historical_daily_tec(
    epochs,
    tec,
    *,
    start_date: date,
    end_date: date,
    allow_interpolation: bool = False,
) -> HistoricalDailyTECResult:
    """Prepare a complete daily TEC matrix from naive UTC epochs.

    The requested interval includes both start_date and end_date.
    Each calendar day contains 24 hourly TEC samples.

    Missing internal hourly samples may be interpolated only when
    allow_interpolation=True. Extrapolation is never permitted.
    """

    if not isinstance(start_date, date) or isinstance(
        start_date, datetime
    ):
        raise TypeError("start_date must be a date object.")

    if not isinstance(end_date, date) or isinstance(
        end_date, datetime
    ):
        raise TypeError("end_date must be a date object.")

    if start_date > end_date:
        raise ValueError("start_date must not exceed end_date.")

    if type(allow_interpolation) is not bool:
        raise TypeError("allow_interpolation must be a boolean.")

    epochs = np.asarray(epochs, dtype=object)
    tec = np.asarray(tec, dtype=np.float64)

    if epochs.ndim != 1 or tec.ndim != 1:
        raise ValueError("epochs and tec must be one-dimensional.")

    if len(epochs) != len(tec):
        raise ValueError("epochs and tec must have equal lengths.")

    if len(epochs) < 2:
        raise ValueError("At least two TEC samples are required.")

    if not all(isinstance(epoch, datetime) for epoch in epochs):
        raise TypeError("epochs must contain datetime objects.")

    if any(epoch.tzinfo is not None for epoch in epochs):
        raise ValueError("epochs must use naive UTC datetimes.")

    if any(
        epoch.minute != 0
        or epoch.second != 0
        or epoch.microsecond != 0
        for epoch in epochs
    ):
        raise ValueError("epochs must align with hourly boundaries.")

    # Exact requested calendar-day interval.
    first_epoch = datetime.combine(start_date, time.min)
    last_epoch = datetime.combine(end_date, time(23, 0))

    # This adapter accepts only observations within the requested
    # historical analysis interval.
    if epochs[0] < first_epoch or epochs[-1] > last_epoch:
        raise ValueError(
            "Input epochs must lie within the requested date interval."
        )

    # Delegate chronological and duplicate validation to the
    # existing validated interpolation function.
    hourly_result = interpolate_hourly_tec(
        epochs=epochs,
        tec=tec,
        start_time=first_epoch,
        end_time=last_epoch,
    )

    expected_days = (end_date - start_date).days + 1
    expected_hours = expected_days * 24

    if len(hourly_result.epochs) != expected_hours:
        raise ValueError("Unexpected hourly TEC sequence length.")

    expected_epochs = np.asarray(
        [
            first_epoch + timedelta(hours=i)
            for i in range(expected_hours)
        ],
        dtype=object,
    )

    if not np.array_equal(hourly_result.epochs, expected_epochs):
        raise ValueError("Historical TEC hourly timestamps are invalid.")

    if not np.all(np.isfinite(hourly_result.tec)):
        raise ValueError(
            "Historical TEC contains unresolved missing values."
        )

    if (
        not allow_interpolation
        and np.any(hourly_result.interpolated_mask)
    ):
        raise ValueError(
            "Historical TEC requires interpolation, "
            "but allow_interpolation is False."
        )

    daily_tec = hourly_result.tec.reshape(
        expected_days,
        24,
    ).copy()

    return HistoricalDailyTECResult(
        daily_tec=daily_tec,
        start_date=start_date,
        end_date=end_date,
        hourly_result=hourly_result,
        n_days=expected_days,
    )
