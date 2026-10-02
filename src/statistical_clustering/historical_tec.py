"""Historical TEC temporal normalization utilities.

This module converts an irregular or lower-cadence TEC time series to a
complete hourly time series for statistical earthquake analysis.

Data loading, GIM grid-point extraction, earthquake selection, and
statistical testing are handled elsewhere.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np


@dataclass(frozen=True)
class HourlyTECResult:
    """Hourly TEC time series produced by temporal interpolation."""

    epochs: np.ndarray
    tec: np.ndarray
    observed_mask: np.ndarray
    interpolated_mask: np.ndarray


def interpolate_hourly_tec(
    epochs: np.ndarray,
    tec: np.ndarray,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> HourlyTECResult:
    """Convert a TEC time series to a complete hourly cadence.

    Existing hourly observations are preserved. Missing hourly samples
    between valid observations are filled by linear interpolation.

    Interpolation is performed only within the temporal range covered by
    the original observations. No extrapolation is performed outside the
    first and last input epochs.

    Parameters
    ----------
    epochs
        One-dimensional sequence of datetime objects.
    tec
        One-dimensional TEC values corresponding to ``epochs``.

    Returns
    -------
    HourlyTECResult
        Hourly epochs, hourly TEC values, and masks identifying original
        and interpolated samples.
    """

    epochs = np.asarray(epochs, dtype=object)
    tec = np.asarray(tec, dtype=np.float64)

    _validate_inputs(
        epochs=epochs,
        tec=tec,
    )

    start = (
        epochs[0]
        if start_time is None
        else start_time
    )

    end = (
        epochs[-1]
        if end_time is None
        else end_time
    )

    if not isinstance(start, datetime):
        raise TypeError(
            "start_time must be a datetime object or None."
        )

    if not isinstance(end, datetime):
        raise TypeError(
            "end_time must be a datetime object or None."
        )

    if start > epochs[0]:
        raise ValueError(
            "start_time must not be later than the first input epoch."
        )

    if end < epochs[-1]:
        raise ValueError(
            "end_time must not be earlier than the last input epoch."
        )

    if start >= end:
        raise ValueError(
            "start_time must be earlier than end_time."
        )

    if (
        start.minute != 0
        or start.second != 0
        or start.microsecond != 0
    ):
        raise ValueError(
            "start_time must fall on an exact hourly boundary."
        )

    if (
        end.minute != 0
        or end.second != 0
        or end.microsecond != 0
    ):
        raise ValueError(
            "end_time must fall on an exact hourly boundary."
        )

    total_hours = int(
        (end - start).total_seconds() / 3600
    )

    hourly_epochs = np.asarray(
        [
            start + timedelta(hours=i)
            for i in range(total_hours + 1)
        ],
        dtype=object,
    )

    hourly_tec = np.full(
        len(hourly_epochs),
        np.nan,
        dtype=np.float64,
    )

    observed_mask = np.zeros(
        len(hourly_epochs),
        dtype=bool,
    )

    epoch_to_index = {
        epoch: index
        for index, epoch in enumerate(hourly_epochs)
    }

    for epoch, value in zip(epochs, tec):

        if epoch not in epoch_to_index:
            raise ValueError(
                "All input epochs must fall on exact hourly boundaries."
            )

        index = epoch_to_index[epoch]

        hourly_tec[index] = value
        observed_mask[index] = np.isfinite(value)

    valid = np.isfinite(hourly_tec)

    valid_indices = np.flatnonzero(valid)

    if len(valid_indices) < 2:
        raise ValueError(
            "At least two finite TEC observations are required "
            "for interpolation."
        )

    all_indices = np.arange(
        len(hourly_tec)
    )

    first_valid = valid_indices[0]
    last_valid = valid_indices[-1]

    interpolation_range = (
        (all_indices >= first_valid)
        & (all_indices <= last_valid)
    )

    missing_internal = (
        interpolation_range
        & ~valid
    )

    hourly_tec[missing_internal] = np.interp(
        all_indices[missing_internal],
        valid_indices,
        hourly_tec[valid_indices],
    )

    interpolated_mask = (
        missing_internal
        & np.isfinite(hourly_tec)
    )

    return HourlyTECResult(
        epochs=hourly_epochs,
        tec=hourly_tec,
        observed_mask=observed_mask,
        interpolated_mask=interpolated_mask,
    )


def _validate_inputs(
    epochs: np.ndarray,
    tec: np.ndarray,
) -> None:
    """Validate TEC time-series inputs."""

    if epochs.ndim != 1:
        raise ValueError(
            "epochs must be one-dimensional."
        )

    if tec.ndim != 1:
        raise ValueError(
            "tec must be one-dimensional."
        )

    if len(epochs) != len(tec):
        raise ValueError(
            "epochs and tec must have the same length."
        )

    if len(epochs) == 0:
        raise ValueError(
            "epochs and tec must not be empty."
        )

    if not all(
        isinstance(epoch, datetime)
        for epoch in epochs
    ):
        raise TypeError(
            "epochs must contain datetime objects."
        )

    if len(set(epochs.tolist())) != len(epochs):
        raise ValueError(
            "epochs must not contain duplicate timestamps."
        )

    if not all(
        epochs[i] < epochs[i + 1]
        for i in range(len(epochs) - 1)
    ):
        raise ValueError(
            "epochs must be strictly increasing."
        )

    if any(
        epoch.minute != 0
        or epoch.second != 0
        or epoch.microsecond != 0
        for epoch in epochs
    ):
        raise ValueError(
            "epochs must fall on exact hourly boundaries."
        )