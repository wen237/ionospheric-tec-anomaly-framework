"""Utilities for selecting and combining daily TEC time-series segments.

Daily GIM/IONEX products may include an additional epoch at 00:00 UT of
the following calendar day. For day-based workflows, ``select_calendar_day``
retains only samples belonging to the requested date before multiple daily
segments are combined.

This module handles temporal organization of extracted TEC time series only.
TEC grid-point extraction and temporal anomaly detection are handled elsewhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import numpy as np

from tec_timeseries import TECTimeSeries


def _same_longitude(
    longitude_a: float,
    longitude_b: float,
    *,
    atol: float = 1e-10,
) -> bool:
    """Return whether two longitudes represent the same meridian."""

    difference = (
        longitude_a
        - longitude_b
        + 180.0
    ) % 360.0 - 180.0

    return bool(
        np.isclose(
            difference,
            0.0,
            rtol=0.0,
            atol=atol,
        )
    )


def _validate_series(
    series: TECTimeSeries,
) -> None:
    """Validate one TEC time-series segment."""

    epochs = np.asarray(
        series.epochs,
        dtype=object,
    )

    tec = np.asarray(
        series.tec,
        dtype=float,
    )

    if epochs.ndim != 1:
        raise ValueError(
            "TECTimeSeries epochs must be one-dimensional."
        )

    if tec.ndim != 1:
        raise ValueError(
            "TECTimeSeries tec must be one-dimensional."
        )

    if len(epochs) != len(tec):
        raise ValueError(
            "TECTimeSeries epochs and tec must have equal lengths."
        )

    if len(epochs) == 0:
        raise ValueError(
            "TECTimeSeries must not be empty."
        )

    if len(set(epochs)) != len(epochs):
        raise ValueError(
            "Each individual TECTimeSeries must not contain "
            "duplicate timestamps."
        )

    if any(
        epochs[i] >= epochs[i + 1]
        for i in range(len(epochs) - 1)
    ):
        raise ValueError(
            "Each individual TECTimeSeries must be "
            "strictly chronological."
        )


def _validate_metadata(
    series: TECTimeSeries,
    reference: TECTimeSeries,
) -> None:
    """Validate location and grid-point compatibility between two segments."""

    if not np.isclose(
        series.requested_latitude,
        reference.requested_latitude,
        rtol=0.0,
        atol=1e-10,
    ):
        raise ValueError(
            "All series must use the same requested latitude."
        )

    if not _same_longitude(
        series.requested_longitude,
        reference.requested_longitude,
    ):
        raise ValueError(
            "All series must use the same requested longitude."
        )

    if not np.isclose(
        series.grid_latitude,
        reference.grid_latitude,
        rtol=0.0,
        atol=1e-10,
    ):
        raise ValueError(
            "All series must use the same grid latitude."
        )

    if not _same_longitude(
        series.grid_longitude,
        reference.grid_longitude,
    ):
        raise ValueError(
            "All series must use the same grid longitude."
        )


def select_calendar_day(
    series: TECTimeSeries,
    target_date: date,
) -> TECTimeSeries:
    """Select TEC samples belonging to a specified calendar date.

    This function is useful when a daily data product contains epochs beyond
    its nominal calendar day, such as an additional 00:00 UT epoch from the
    following day in some GIM/IONEX products. Only epochs whose calendar date
    equals ``target_date`` are retained.

    Parameters
    ----------
    series
        TEC time series from which samples are selected.
    target_date
        Calendar date whose samples should be retained.

    Returns
    -------
    TECTimeSeries
        TEC time series containing only samples from ``target_date``.

    Raises
    ------
    ValueError
        If the input series is invalid or contains no samples from
        ``target_date``.
    """

    _validate_series(series)

    mask = np.asarray(
        [
            epoch.date() == target_date
            for epoch in series.epochs
        ],
        dtype=bool,
    )

    if not np.any(mask):
        raise ValueError(
            f"No TEC samples found for target date {target_date}."
        )

    selected_epochs = np.asarray(
        series.epochs,
        dtype=object,
    )[mask]

    selected_tec = np.asarray(
        series.tec,
        dtype=float,
    )[mask]

    return TECTimeSeries(
        epochs=selected_epochs,
        tec=selected_tec,
        requested_latitude=series.requested_latitude,
        requested_longitude=series.requested_longitude,
        grid_latitude=series.grid_latitude,
        grid_longitude=series.grid_longitude,
        latitude_index=series.latitude_index,
        longitude_index=series.longitude_index,
    )


def combine_tec_timeseries(
    series_list: Sequence[TECTimeSeries],
) -> TECTimeSeries:
    """Combine non-overlapping TEC time-series segments.

    All input segments must represent the same requested location and
    geographic grid point. Segments are sorted chronologically after
    concatenation, and duplicate timestamps are treated as an error.

    For daily GIM/IONEX workflows, overlapping boundary epochs should be
    removed with ``select_calendar_day`` before calling this function.

    Parameters
    ----------
    series_list
        Sequence of non-overlapping TEC time-series segments.

    Returns
    -------
    TECTimeSeries
        Combined strictly chronological TEC time series.

    Raises
    ------
    ValueError
        If the input sequence is empty, an input series is invalid,
        location or grid-point metadata are inconsistent, or duplicate
        timestamps remain after concatenation.
    """

    if len(series_list) == 0:
        raise ValueError(
            "series_list must contain at least one TECTimeSeries."
        )

    reference = series_list[0]

    for series in series_list:
        _validate_series(series)
        _validate_metadata(
            series,
            reference,
        )

    epochs = np.concatenate(
        [
            np.asarray(
                series.epochs,
                dtype=object,
            )
            for series in series_list
        ]
    )

    tec = np.concatenate(
        [
            np.asarray(
                series.tec,
                dtype=float,
            )
            for series in series_list
        ]
    )

    order = np.argsort(
        epochs,
        kind="stable",
    )

    epochs = epochs[order]
    tec = tec[order]

    if len(set(epochs)) != len(epochs):
        raise ValueError(
            "Duplicate timestamps remain after combining TEC "
            "time-series segments. Remove overlapping daily "
            "boundary samples before combining."
        )

    if any(
        epochs[i] >= epochs[i + 1]
        for i in range(len(epochs) - 1)
    ):
        raise ValueError(
            "Combined TEC epochs must be strictly increasing."
        )

    return TECTimeSeries(
        epochs=np.asarray(
            epochs,
            dtype=object,
        ),
        tec=np.asarray(
            tec,
            dtype=float,
        ),
        requested_latitude=reference.requested_latitude,
        requested_longitude=reference.requested_longitude,
        grid_latitude=reference.grid_latitude,
        grid_longitude=reference.grid_longitude,
        latitude_index=reference.latitude_index,
        longitude_index=reference.longitude_index,
    )
