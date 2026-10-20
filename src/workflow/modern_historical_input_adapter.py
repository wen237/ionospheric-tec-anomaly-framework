"""Opt-in modern GIM adapter for Framework B+C historical daily TEC.

Each UTC date owns hours 00..23 of its own IONEX file. The 25th map
is discarded upstream by modern_gim_series. No interpolation or scaling.
"""
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from src.data.modern_gim_series import load_modern_gim_series
from src.temporal_anomaly.tec_timeseries import extract_tec_timeseries
from src.workflow.historical_input_adapter import (
    HistoricalDailyTECResult,
    prepare_historical_daily_tec,
)


def load_historical_daily_tec_from_modern_gim(
    file_paths: Sequence[str | Path],
    *,
    start_date: date,
    end_date: date,
    latitude: float,
    longitude: float,
) -> HistoricalDailyTECResult:
    """Select complete UTC calendar days at nearest grid point for B+C.

    Requires every selected TEC sample to be finite. NaNs are never
    interpolated or silently filled; choose another interval or handle
    missing observations explicitly in a separate scientific workflow.
    """
    for name, value in (("start_date", start_date), ("end_date", end_date)):
        if not isinstance(value, date) or isinstance(value, datetime):
            raise TypeError(f"{name} must be a date, not datetime.")
    if start_date > end_date:
        raise ValueError("start_date must not exceed end_date.")

    series = load_modern_gim_series(file_paths)
    first = np.datetime64(start_date.isoformat(), "s")
    last_exclusive = np.datetime64((end_date + timedelta(days=1)).isoformat(), "s")
    indices = np.flatnonzero((series.epochs >= first) & (series.epochs < last_exclusive))
    n_hours = ((end_date - start_date).days + 1) * 24
    expected = first + np.arange(n_hours).astype("timedelta64[h]")
    if indices.size != n_hours or not np.array_equal(series.epochs[indices], expected):
        raise ValueError("Modern GIM files do not cover every requested UTC hour.")

    first_hour = datetime.combine(start_date, datetime.min.time())
    epochs = tuple(first_hour + timedelta(hours=i) for i in range(n_hours))
    selected = extract_tec_timeseries(
        tec=series.tec[indices], epochs=epochs,
        latitudes=series.lat, longitudes=series.lon,
        latitude=latitude, longitude=longitude,
    )
    if not np.all(np.isfinite(selected.tec)):
        raise ValueError("Selected historical TEC contains NaN; interpolation is not permitted.")

    return prepare_historical_daily_tec(
        epochs=selected.epochs, tec=selected.tec,
        start_date=start_date, end_date=end_date,
        allow_interpolation=False,
    )
